"""L2 编排（集成点）：把 L1 观测流组装成 `Panel`。

这是 L2 对外的**唯一装配入口**，也是本层唯一允许 import 本层其它模块的文件
（`tools/check_layering.py` 的 `ORCHESTRATORS` 声明，且校验"没人 import 它"）。

四步，顺序即依赖：

  1. **声明校验** —— 每个观测的 `series_key` 必须已在 `[series.*]` 声明；
     在 `[pending]` 里的是**显式排除**（理由记录在配置里），不是被悄悄丢掉；
     声明了但没观测的序列直接报错 —— 缺一列的"面板"不是面板。
  2. **单位归一** —— `convert`，走 L0 units，跨族即炸。
  3. **交易日轴 + 前向填充打标** —— `calendar` 出轴，`align` 填充并打 `fill_flag`。
  4. **三重门禁**（全部 fail-closed）
     a. 结构不变量：`make_panel` 校验 `fill_flag` 与 `source_as_of` 的充要关系、单位唯一等；
     b. 真实观测下限：`min_real_observations` —— 防止整列都是填充值；
     c. 新鲜度：`staleness` —— 尾部滞后超限即整体失败。

纯函数 + 显式 `as_of`：本模块不读"现在"，所以同一个 `as_of` 永远得到同一个面板
（重放/回测成立的前提）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Sequence

from L1_接入层.contract import Observation
from L2_归一化层 import align, calendar, convert, panel_store, staleness
from L2_归一化层.contract import Panel, make_panel
from L2_归一化层.settings import NormalizationSettings


class PipelineError(RuntimeError):
    """组装前提不满足。一律 fail-closed。"""


def build_panel(
    observations: Sequence[Observation],
    cfg: NormalizationSettings,
    *,
    as_of: date,
) -> Panel:
    """把观测流组装成 `as_of` 当日的面板。任何前提不满足即抛错。"""
    trading = calendar.from_settings(cfg)
    if not trading.is_trading_day(as_of):
        raise PipelineError(f"as_of={as_of} 不是 {cfg.exchange} 交易日，不能出面板")

    specs = cfg.series_map()
    pending = cfg.pending_map()

    grouped: dict[str, list[Observation]] = {}
    for obs in observations:
        key = obs.series_key
        if key in pending:
            continue  # 显式排除，理由在配置的 [pending] 里
        if key not in specs:
            raise PipelineError(
                f"观测的序列 {key!r} 既未在 [series.*] 声明、也未列入 [pending]"
                " —— 新增序列必须先在 config/normalization.toml 里表态"
            )
        grouped.setdefault(key, []).append(obs)

    missing = sorted(set(specs) - set(grouped))
    if missing:
        raise PipelineError(f"以下已声明序列没有任何观测：{missing}")

    converted = convert.convert_all(
        [obs for group in grouped.values() for obs in group],
        {key: spec.target_unit for key, spec in specs.items()},
    )
    by_series: dict[str, list[Observation]] = {}
    for obs in converted:
        by_series.setdefault(obs.series_key, []).append(obs)

    start = min(obs.date for obs in converted)
    axis = trading.trading_days(start, as_of)
    if not axis:
        raise PipelineError(f"{start}..{as_of} 之间没有 {cfg.exchange} 交易日")

    panel = make_panel(align.align_all(by_series, axis, as_of=as_of), as_of=as_of)

    _check_real_observations(panel, minimum=cfg.min_real_observations)
    findings = staleness.check_staleness(
        panel, axis=axis, limits=cfg.staleness_limits()
    )
    staleness.enforce(findings)
    return panel


def build_and_store(
    observations: Sequence[Observation],
    cfg: NormalizationSettings,
    *,
    as_of: date,
) -> tuple[Panel, Path]:
    """组装并落盘。先过完全部门禁再写文件 —— 门禁失败时不留下任何产物。"""
    panel = build_panel(observations, cfg, as_of=as_of)
    return panel, panel_store.write_panel(panel, directory=cfg.panel_dir)


def _check_real_observations(panel: Panel, *, minimum: int) -> None:
    """每个序列至少要有 N 条**真实**观测（非填充）。

    只看总行数没有意义：前向填充会把任何一条真实观测复制成很多行，
    总行数几乎恒等于时间轴长度。真正要防的是"整列都是搬运来的值"。
    """
    thin = []
    for key in panel.series_keys():
        real = sum(1 for row in panel.rows_of(key) if not row.fill_flag)
        if real < minimum:
            thin.append(f"{key} 只有 {real} 条")
    if thin:
        raise PipelineError(
            f"真实观测不足（下限 {minimum} 条）：{'；'.join(thin)}"
            " —— 检查该源的取数窗口（sources.toml）是否过窄"
        )
