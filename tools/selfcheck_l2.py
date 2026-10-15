"""L2 归一化层自检（验证入口，非分层）。

用法（在**仓库根目录**下）：
    python -m tools.selfcheck_l2
    python -m tools.selfcheck_l2 --skip-e2e     # 跳过需要落盘数据的端到端检查

退出码：任一检查失败即 1。端到端部分在 `tools/l2_e2e_check.py`。

**非空转原则**：每一类检查都配了反证 ——
配置覆盖核对要能报出人为漏掉的键；日历事实要能被人为篡改的配置推翻；
填充打标要能被契约拒绝；门禁要能被故意做坏的输入触发。
只"跑通"不算证据，"摘掉它就会红"才算。
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from L0_基元层.config import load_sources
from L1_接入层.contract import make_observation
from L1_接入层.observations import (
    series_key_cboe_index,
    series_key_cboe_ratio,
    series_key_fred,
    series_key_yahoo,
)
from L2_归一化层 import align, calendar, convert, panel_store, staleness
from L2_归一化层.contract import PanelError, PanelRow, make_panel
from L2_归一化层.settings import NORMALIZATION_PATH, load_settings
from tools.checkkit import CheckKit
from tools.l2_e2e_check import check_end_to_end

STAMP = datetime(2026, 10, 15, 21, 0, tzinfo=timezone.utc)
DEMO_AXIS = [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15)]
DEMO_AS_OF = DEMO_AXIS[-1]


def _obs(key: str, day: str, value: object, unit: str = "INDEX_POINT"):
    return make_observation(
        series_key=key,
        day=date.fromisoformat(day),
        value=value,
        unit=unit,
        source="selftest",
        retrieved_at=STAMP,
    )


def _demo_rows() -> list[PanelRow]:
    """两个真实观测（10-13 / 10-15）落在 4 天轴上 -> 10-14 必须是填充点。"""
    return align.align_series(
        [_obs("t:demo", "2026-10-13", "1"), _obs("t:demo", "2026-10-15", "3")],
        DEMO_AXIS,
        as_of=DEMO_AS_OF,
    )


def _stale_rows() -> list[PanelRow]:
    """最后一条真实观测停在 10-13 -> 尾部 10-14 / 10-15 都是填充点，滞后 2 个交易日。"""
    return align.align_series([_obs("t:stale", "2026-10-13", "1")], DEMO_AXIS, as_of=DEMO_AS_OF)


# --- 配置覆盖：sources.toml 声明的序列，必须逐条在 normalization.toml 里有交代 ---

def _declared_keys(sources: dict) -> set[str]:
    keys = {series_key_fred(alias) for alias in sources["fred"]["series"]}
    keys |= {series_key_cboe_index(name) for name in sources["cboe"]["index_csv_files"]}
    keys |= {series_key_cboe_ratio(name) for name in sources["cboe"]["ratios"]["labels"]}
    keys |= {series_key_yahoo(symbol) for symbol in sources["yahoo"]["symbols"]}
    return keys


def _gaps(declared: set[str], covered: set[str]) -> list[str]:
    """declared 里有、covered 里没有的键。纯函数，便于反证。"""
    return sorted(declared - covered)


def _check_coverage_harness() -> str:
    """反证：漏掉一个键必须被检出；对齐全覆盖时必须不报。"""
    if _gaps({"a", "b"}, {"a"}) != ["b"]:
        raise AssertionError("覆盖核对空转：漏掉的键没被检出")
    if _gaps({"a"}, {"a", "b"}) != []:
        raise AssertionError("覆盖核对空转：多出的键被误判成缺口")
    return "漏键可检出、全覆盖不误报"


def _check_coverage(sources: dict, cfg) -> str:
    declared = _declared_keys(sources)
    covered = set(cfg.series_map()) | set(cfg.pending_map())
    missing = _gaps(declared, covered)
    if missing:
        raise AssertionError(
            f"以下序列在 sources.toml 里取了数，却在 normalization.toml 里没有交代：{missing}"
        )
    stale = _gaps(covered, declared)
    if stale:
        raise AssertionError(
            f"以下序列在 normalization.toml 里有条目，但 sources.toml 里并不存在：{stale}"
        )
    return (
        f"{len(declared)} 个序列双向对齐"
        f"（进面板 {len(cfg.series_map())}，显式 pending {len(cfg.pending_map())}）"
    )


# --- 日历：用外部已知事实断言，再用人为篡改的配置反证"配置真的被读了" ---

# 这些是公开的交易所事实，不是从本实现推出来的。
KNOWN_CLOSED = {
    "2026-01-01": "元旦",
    "2026-04-03": "耶稣受难日（复活节 2026-04-05）",
    "2026-07-03": "独立日顺延（07-04 是周六）",
    "2026-11-26": "感恩节",
    "2022-06-20": "Juneteenth 顺延（06-19 是周日）",
    "2025-01-09": "临时休市：卡特国葬",
}
KNOWN_OPEN = {
    "2021-12-31": "元旦 2022-01-01 是周六，NYSE 不提前到周五（跨年顺延的最易漏一格）",
    "2021-06-18": "Juneteenth 2022 年才生效，2021 年照常交易",
    "2026-10-12": "哥伦布日：联邦假日但 NYSE 开市",
    "2026-11-27": "感恩节次日：NYSE 开市（提前收盘）",
}


def _check_calendar_facts(cal: calendar.TradingCalendar) -> str:
    for raw, why in KNOWN_CLOSED.items():
        if cal.is_trading_day(date.fromisoformat(raw)):
            raise AssertionError(f"{raw} 应休市（{why}），却被判为交易日")
    for raw, why in KNOWN_OPEN.items():
        if not cal.is_trading_day(date.fromisoformat(raw)):
            raise AssertionError(f"{raw} 应开市（{why}），却被判为休市")
    return f"已知休市 {len(KNOWN_CLOSED)} 天、已知开市 {len(KNOWN_OPEN)} 天全部吻合"


def _tampered(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"篡改锚点 {old!r} 在配置里出现 {text.count(old)} 次，不唯一")
    return text.replace(old, new)


def _check_calendar_reads_config() -> str:
    """反证：改配置必须改变结果。若不变，说明日历是硬编码的，配置形同虚设。"""
    original = NORMALIZATION_PATH.read_text(encoding="utf-8")
    cases = [
        (_tampered(original, "saturday_shift = false", "saturday_shift = true"),
         "2021-12-31", "把元旦的 saturday_shift 改成 true"),
        (_tampered(original, "from_year = 2022\n", ""),
         "2021-06-18", "去掉 Juneteenth 的 from_year"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for index, (text, day, why) in enumerate(cases):
            path = Path(tmp) / f"norm_{index}.toml"
            path.write_text(text, encoding="utf-8")
            if calendar.from_settings(load_settings(path)).is_trading_day(date.fromisoformat(day)):
                raise AssertionError(f"{why} 后 {day} 仍判为开市 —— 日历没有读配置")
    return f"{len(cases)} 处配置篡改都改变了结果（配置确实被读）"


# --- 单位归一 ---

def _check_convert() -> str:
    rrp = _obs("fred:rrpontsyd", "2026-10-14", "0.201", unit="USD_BILLION")
    got = convert.convert_observation(rrp, target_unit="USD_MILLION")
    if got.value != Decimal("201"):
        raise AssertionError(f"0.201 十亿应等于 201 百万，得到 {got.value}")
    if got.unit != "USD_MILLION":
        raise AssertionError(f"单位未改写：{got.unit}")
    if convert.convert_observation(got, target_unit="USD_MILLION") is not got:
        raise AssertionError("单位已一致时不应重建对象（会引入无意义的 Decimal 往返）")

    for build, why in [
        (lambda: convert.convert_observation(rrp, target_unit="PERCENT"), "跨族换算"),
        (lambda: convert.convert_all([rrp], {}), "序列缺目标单位"),
    ]:
        try:
            build()
        except convert.ConvertError:
            continue
        raise AssertionError(f"{why}竟然通过了")
    return "0.201 十亿 -> 201 百万；跨族被拒；缺目标单位被拒"


# --- 对齐：填充打标 ---

def _check_align() -> str:
    rows = _demo_rows()
    got = [(row.date, str(row.value), row.fill_flag, row.source_as_of) for row in rows]
    expected = [
        (date(2026, 10, 13), "1", False, date(2026, 10, 13)),
        (date(2026, 10, 14), "1", True, date(2026, 10, 13)),
        (date(2026, 10, 15), "3", False, date(2026, 10, 15)),
    ]
    if got != expected:
        raise AssertionError(f"对齐结果不符：\n  期望 {expected}\n  实际 {got}")
    if any(row.date == date(2026, 10, 12) for row in rows):
        raise AssertionError("第一条真实观测之前不应造行（禁止向后填充）")

    for build, why in [
        (lambda: align.align_series([_obs("t:demo", "2026-10-16", "1")], DEMO_AXIS, as_of=DEMO_AS_OF),
         "观测晚于 as_of"),
        (lambda: align.align_series([], [date(2026, 10, 15)], as_of=date(2026, 10, 14)),
         "轴末元素不等于 as_of"),
        (lambda: align.align_series([], [date(2026, 10, 15), date(2026, 10, 14)],
                                    as_of=date(2026, 10, 15)),
         "轴非升序"),
        (lambda: align.align_series(
            [_obs("t:a", "2026-10-15", "1"), _obs("t:b", "2026-10-15", "1")],
            DEMO_AXIS, as_of=DEMO_AS_OF),
         "单序列接口收到两个序列"),
    ]:
        try:
            build()
        except align.AlignError:
            continue
        raise AssertionError(f"应报错但通过了：{why}")
    return "填充打标精确匹配、起点前不造行，4 类非法输入全部被拒"


def _check_fill_flag_contract() -> str:
    """反证：把 fill_flag 写反，契约必须拦住 —— 否则"填充伪装成观测"就没防线。"""
    rows = _demo_rows()
    tampered = [
        replace(row, fill_flag=not row.fill_flag) if row.date == date(2026, 10, 14) else row
        for row in rows
    ]
    try:
        make_panel(tampered, as_of=DEMO_AS_OF)
    except PanelError:
        pass
    else:
        raise AssertionError("fill_flag 与 source_as_of 不一致竟然通过了契约校验")
    make_panel(rows, as_of=DEMO_AS_OF)  # 未篡改的必须通过
    return "篡改 fill_flag 被拒，原样通过"


# --- 新鲜度门禁 ---

def _check_staleness() -> str:
    panel = make_panel(_stale_rows(), as_of=DEMO_AS_OF)
    ok = staleness.check_staleness(panel, axis=DEMO_AXIS, limits={"t:stale": 2})
    staleness.enforce(ok)  # lag == limit 不算超限
    if ok[0].lag_trading_days != 2:
        raise AssertionError(f"滞后应为 2 个交易日，得到 {ok[0].lag_trading_days}")

    # 反证：尾部就在 as_of 当天的序列，滞后必须是 0（否则门禁对新鲜数据也报红）
    fresh = staleness.check_staleness(
        make_panel(_demo_rows(), as_of=DEMO_AS_OF), axis=DEMO_AXIS, limits={"t:demo": 2}
    )
    if fresh[0].lag_trading_days != 0:
        raise AssertionError(f"尾部数据日就是 as_of 时滞后应为 0，得到 {fresh[0].lag_trading_days}")

    cases = [
        ({"t:stale": 1}, staleness.StalenessError, "滞后 2 > 上限 1"),
        ({"t:stale": 5}, staleness.StalenessError, "轴只有 4 天、上限 5 天时无法判定"),
        ({"t:other": 2}, staleness.StalenessError, "序列与上限不匹配"),
    ]
    for limits, error, why in cases:
        try:
            staleness.enforce(staleness.check_staleness(panel, axis=DEMO_AXIS, limits=limits))
        except error:
            continue
        raise AssertionError(f"{why}竟然通过了")
    return "lag==limit 放行、lag>limit 拒绝、新鲜序列滞后 0、轴过短拒绝、序列不匹配拒绝"


# --- 面板落盘 ---

def _check_panel_store() -> str:
    panel = make_panel(_demo_rows(), as_of=DEMO_AS_OF)
    with tempfile.TemporaryDirectory() as tmp:
        path = panel_store.write_panel(panel, directory=Path(tmp))
        if panel_store.read_panel(path) != panel:
            raise AssertionError("落盘往返不一致")

        # 篡改一：把一条真实观测谎报成填充点。
        # 文件名必须仍合规，否则测的是文件名而不是不变量。
        bad = path.read_text(encoding="utf-8").splitlines()
        for index in range(1, len(bad)):
            cells = bad[index].split(",")
            if cells[4] == "0":
                cells[4] = "1"
                bad[index] = ",".join(cells)
                break
        else:
            raise AssertionError("构造用例失败：面板里没有 fill_flag=0 的行")
        tamper_dir = Path(tmp) / "tampered"
        tamper_dir.mkdir()
        (tamper_dir / path.name).write_text("\n".join(bad) + "\n", encoding="utf-8")
        # 篡改二：表头不对
        (tamper_dir / "panel_2026-10-14.csv").write_text("date,series_key\n", encoding="utf-8")

        for target, why in [
            (tamper_dir / path.name, "被篡改 fill_flag"),
            (tamper_dir / "panel_2026-10-14.csv", "表头不对"),
            (Path(tmp) / "not_a_panel.csv", "文件名不含 as_of"),
        ]:
            try:
                panel_store.read_panel(target)
            except panel_store.PanelStoreError:
                continue
            raise AssertionError(f"{why}竟然读成功了")
    return "往返一致；篡改 fill_flag / 表头 / 文件名 三类都报错"


def main() -> int:
    parser = argparse.ArgumentParser(description="L2 归一化层自检")
    parser.add_argument("--skip-e2e", action="store_true", help="跳过需要落盘数据的端到端检查")
    args = parser.parse_args()

    kit = CheckKit("L2 归一化层自检")
    print("=== L2 归一化层自检 ===")
    kit.check("检查器非空转自测", kit.selftest)

    try:
        sources = load_sources()
        cfg = load_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] 加载配置  —— {type(exc).__name__}: {exc}")
        return 1

    kit.check("配置覆盖双向核对（反证）", _check_coverage_harness)
    kit.check("sources.toml 与 normalization.toml 序列对齐", lambda: _check_coverage(sources, cfg))

    cal = calendar.from_settings(cfg)
    kit.check("NYSE 日历：已知休市/开市日期", lambda: _check_calendar_facts(cal))
    kit.check("NYSE 日历：配置篡改必须改变结果（反证）", _check_calendar_reads_config)

    kit.check("单位归一", _check_convert)
    kit.check("时间轴对齐与填充打标", _check_align)
    kit.check("fill_flag 契约：篡改必须被拒（反证）", _check_fill_flag_contract)
    kit.check("新鲜度门禁（含反证）", _check_staleness)
    kit.check("面板落盘往返与不变量复核（含反证）", _check_panel_store)

    if args.skip_e2e:
        print("（已跳过端到端检查）")
    else:
        kit.check(
            "端到端：真实数据建面板（含 3 类反证）",
            lambda: check_end_to_end(sources, cfg),
        )

    return kit.report()


if __name__ == "__main__":
    sys.exit(main())
