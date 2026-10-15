"""L2 端到端检查（需要落盘数据）。

为什么单独成文件：这类检查的**前置条件**与其它检查不同 —— 它要读 `data/raw/` 下的真实落盘
数据、走完整的 L1 -> L2 链路。和纯函数检查混在一个文件里，会让"能不能跑"取决于有没有取过数。

由 `tools/selfcheck_l2.py` 统一调用（`--skip-e2e` 可跳过）。三个反证都用真实数据做，
不用构造数据 —— 构造数据只能证明代码自洽，证明不了它对真实源成立。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

from L1_接入层.contract import make_observation
from L1_接入层.observations import collect
from L2_归一化层 import staleness
from L2_归一化层.pipeline import build_panel
from tools.build_panel import latest_raw_dir


def check_end_to_end(sources: dict, cfg) -> str:
    """用最新一份落盘数据建面板，并做三类反证。任一不成立即抛 AssertionError。"""
    directory = latest_raw_dir()
    as_of = date.fromisoformat(directory.name)
    observations = collect(directory, sources)
    panel = build_panel(observations, cfg, as_of=as_of)

    if panel.series_keys() != tuple(sorted(cfg.series_map())):
        raise AssertionError("面板序列与配置声明不一致")
    thinnest = min(
        sum(1 for row in panel.rows_of(key) if not row.fill_flag) for key in panel.series_keys()
    )
    if thinnest < cfg.min_real_observations:
        raise AssertionError(f"最薄的序列只有 {thinnest} 条真实观测")

    # 反证一：抽掉一个已声明序列的全部观测 -> 必须报错（缺一列的"面板"不是面板）
    try:
        build_panel([o for o in observations if o.series_key != "cboe:vix"], cfg, as_of=as_of)
    except RuntimeError:
        pass
    else:
        raise AssertionError("缺一个已声明序列竟然建成了面板")

    # 反证二：塞一个未声明的序列 -> 必须报错（新序列必须先在配置里表态）
    ghost = make_observation(
        series_key="t:ghost",
        day=as_of,
        value="1",
        unit="INDEX_POINT",
        source="selftest",
        retrieved_at=datetime(2026, 10, 15, 21, 0, tzinfo=timezone.utc),
    )
    try:
        build_panel([*observations, ghost], cfg, as_of=as_of)
    except RuntimeError:
        pass
    else:
        raise AssertionError("未声明序列竟然被静默接受")

    # 反证三：把 WALCL 的上限压到 1 个交易日 -> 必须 fail-closed
    tight = replace(
        cfg,
        series=tuple(
            replace(spec, max_staleness_trading_days=1)
            if spec.series_key == "fred:walcl"
            else spec
            for spec in cfg.series
        ),
    )
    try:
        build_panel(observations, tight, as_of=as_of)
    except staleness.StalenessError:
        pass
    else:
        raise AssertionError("把上限压到 1 后 WALCL 的滞后竟然没被拒（门禁空转）")

    return (
        f"{len(panel.series_keys())} 序列 / {len(panel.rows)} 行 / 观测 {len(observations)} 条"
        f" / 最薄序列真实观测 {thinnest} 条；三类反证全部报红"
    )
