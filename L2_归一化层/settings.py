"""L2 配置加载与校验。

职责边界：只读 `config/normalization.toml`，**只校验形状**，不做任何计算。
缺键 / 取值越界 / 未知策略一律抛 `SettingsError`（fail fast），不提供任何默认值兜底。

本模块是 L2 的**层内共享叶子模块**（另一个是 `contract.py`）：
它不 import 本层任何其它模块，而本层其它模块可以 import 它。
`tools/check_layering.py` 会机械校验这条声明（见 `SHARED_MODULES`），声明不实即报错。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from L0_基元层 import clock
from L0_基元层.config import REPO_ROOT
from L0_基元层.units import registered

# 本层配置文件的仓库内位置。这是**结构常量**，不是业务默认值。
NORMALIZATION_PATH = REPO_ROOT / "config" / "normalization.toml"

# 目前唯一支持的频率对齐策略。加新策略必须同时加对齐实现，否则等于静默降级。
ALIGN_POLICIES: tuple[str, ...] = ("forward_fill",)
RULE_KINDS: tuple[str, ...] = ("fixed", "nth", "last", "easter_offset")


class SettingsError(RuntimeError):
    """归一化配置缺失或不合法。不静默兜底，直接失败。"""


@dataclass(frozen=True, slots=True)
class SeriesSpec:
    series_key: str
    target_unit: str
    max_staleness_trading_days: int


@dataclass(frozen=True, slots=True)
class CalendarRule:
    name: str
    kind: str
    month: int | None = None
    day: int | None = None
    weekday: str | None = None
    n: int | None = None
    offset_days: int | None = None
    observed: bool = False
    saturday_shift: bool = True
    from_year: int | None = None


@dataclass(frozen=True, slots=True)
class NormalizationSettings:
    align_policy: str
    panel_dir: Path
    min_real_observations: int
    exchange: str
    series: tuple[SeriesSpec, ...]
    pending: tuple[tuple[str, str], ...]
    rules: tuple[CalendarRule, ...]
    adhoc: tuple[tuple[date, str], ...]

    def series_map(self) -> dict[str, SeriesSpec]:
        return {spec.series_key: spec for spec in self.series}

    def pending_map(self) -> dict[str, str]:
        return dict(self.pending)

    def staleness_limits(self) -> dict[str, int]:
        return {spec.series_key: spec.max_staleness_trading_days for spec in self.series}


def _table(raw: Any, key: str) -> dict:
    if key not in raw:
        raise SettingsError(f"配置缺少 [{key}] 段：{NORMALIZATION_PATH}")
    value = raw[key]
    if not isinstance(value, dict):
        raise SettingsError(f"[{key}] 必须是表，收到 {type(value).__name__}")
    return value


def _text(raw: dict, key: str, *, where: str) -> str:
    if key not in raw:
        raise SettingsError(f"{where} 缺少键 {key}")
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"{where}.{key} 必须是非空字符串，收到 {value!r}")
    return value


def _positive_int(raw: dict, key: str, *, where: str, minimum: int) -> int:
    if key not in raw:
        raise SettingsError(f"{where} 缺少键 {key}")
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"{where}.{key} 必须是整数，收到 {value!r}")
    if value < minimum:
        raise SettingsError(f"{where}.{key} 必须 >= {minimum}，收到 {value}")
    return value


def _optional_int(raw: dict, key: str, *, where: str) -> int | None:
    if key not in raw:
        return None
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingsError(f"{where}.{key} 必须是整数，收到 {value!r}")
    return value


def _reject_extra(raw: dict, allowed: set[str], *, where: str) -> None:
    """未知键必须报错 —— 打错一个键名（如 observedd）如果被忽略，就等于规则悄悄失效。"""
    extra = set(raw) - allowed
    if extra:
        raise SettingsError(f"{where} 出现未登记的键：{sorted(extra)}（可用 {sorted(allowed)}）")


def _parse_series(series_key: str, raw: Any) -> SeriesSpec:
    where = f'[series."{series_key}"]'
    if not series_key.strip():
        raise SettingsError("[series.*] 出现空 series_key")
    if not isinstance(raw, dict):
        raise SettingsError(f"{where} 必须是表")
    _reject_extra(raw, {"target_unit", "max_staleness_trading_days"}, where=where)
    target_unit = _text(raw, "target_unit", where=where)
    if target_unit not in registered():
        raise SettingsError(f"{where}.target_unit 未登记：{target_unit!r}")
    limit = _positive_int(raw, "max_staleness_trading_days", where=where, minimum=1)
    return SeriesSpec(
        series_key=series_key,
        target_unit=target_unit,
        max_staleness_trading_days=limit,
    )


def _parse_rule(raw: Any, *, index: int) -> CalendarRule:
    where = f"calendar.rules[{index}]"
    if not isinstance(raw, dict):
        raise SettingsError(f"{where} 必须是表")
    _reject_extra(
        raw,
        {
            "name", "kind", "month", "day", "weekday", "n",
            "offset_days", "observed", "saturday_shift", "from_year",
        },
        where=where,
    )
    name = _text(raw, "name", where=where)
    kind = _text(raw, "kind", where=where)
    if kind not in RULE_KINDS:
        raise SettingsError(f"{where}.kind 未登记：{kind!r}（可用 {RULE_KINDS}）")

    rule = CalendarRule(
        name=name,
        kind=kind,
        month=_optional_int(raw, "month", where=where),
        day=_optional_int(raw, "day", where=where),
        weekday=raw.get("weekday"),
        n=_optional_int(raw, "n", where=where),
        offset_days=_optional_int(raw, "offset_days", where=where),
        observed=bool(raw.get("observed", False)),
        saturday_shift=bool(raw.get("saturday_shift", True)),
        from_year=_optional_int(raw, "from_year", where=where),
    )
    _check_rule_shape(rule, where=where)
    return rule


def _check_rule_shape(rule: CalendarRule, *, where: str) -> None:
    """按 kind 校验必填字段。字段缺了不报错的话，规则会被静默跳过。"""
    need_month = rule.kind in ("fixed", "nth", "last")
    if need_month and (rule.month is None or not 1 <= rule.month <= 12):
        raise SettingsError(f"{where}.month 必须是 1..12，收到 {rule.month!r}")
    if rule.kind == "fixed":
        if rule.day is None or not 1 <= rule.day <= 31:
            raise SettingsError(f"{where}.day 必须是 1..31，收到 {rule.day!r}")
    if rule.kind in ("nth", "last"):
        if not isinstance(rule.weekday, str):
            raise SettingsError(f"{where}.weekday 必须是字符串，收到 {rule.weekday!r}")
        try:
            clock.weekday_index(rule.weekday)
        except clock.ClockError as exc:
            raise SettingsError(f"{where}.weekday 不合法：{exc}") from None
    if rule.kind == "nth" and (rule.n is None or rule.n < 1):
        raise SettingsError(f"{where}.n 必须 >= 1，收到 {rule.n!r}")
    if rule.kind == "easter_offset" and rule.offset_days is None:
        raise SettingsError(f"{where}.offset_days 必须给出（耶稣受难日 = -2）")
    # 与 kind 无关的字段出现即报错：写错 kind 时不会"看起来生效了"。
    if rule.kind != "fixed" and (rule.day is not None or rule.observed):
        raise SettingsError(f"{where} 是 {rule.kind}，不得出现 day / observed")
    if rule.kind != "easter_offset" and rule.offset_days is not None:
        raise SettingsError(f"{where} 是 {rule.kind}，不得出现 offset_days")


def load_settings(path: Path | None = None) -> NormalizationSettings:
    """加载并校验归一化配置。任何形状问题都在这里拦住，不留到下游。"""
    target = Path(path) if path is not None else NORMALIZATION_PATH
    if not target.is_file():
        raise SettingsError(f"配置文件不存在：{target}")
    with target.open("rb") as handle:
        raw = tomllib.load(handle)

    align = _table(raw, "align")
    _reject_extra(align, {"policy"}, where="[align]")
    policy = _text(align, "policy", where="[align]")
    if policy not in ALIGN_POLICIES:
        raise SettingsError(
            f"[align].policy 未登记：{policy!r}（可用 {ALIGN_POLICIES}）"
            " —— 不支持的策略一律报错，不做静默降级"
        )

    panel = _table(raw, "panel")
    _reject_extra(panel, {"dir", "min_real_observations"}, where="[panel]")
    panel_dir = REPO_ROOT / _text(panel, "dir", where="[panel]")
    min_real = _positive_int(
        panel, "min_real_observations", where="[panel]", minimum=1
    )

    series_raw = _table(raw, "series")
    series: list[SeriesSpec] = []
    for key in series_raw:
        series.append(_parse_series(key, series_raw[key]))
    if not series:
        raise SettingsError("[series.*] 为空 —— 面板没有任何序列")

    pending_raw = _table(raw, "pending")
    pending: list[tuple[str, str]] = []
    for key in pending_raw:
        reason = pending_raw[key]
        if not isinstance(reason, str) or not reason.strip():
            raise SettingsError(f'[pending]."{key}" 必须给出非空原因')
        pending.append((key, reason))
    overlap = {spec.series_key for spec in series} & {key for key, _ in pending}
    if overlap:
        raise SettingsError(f"以下序列同时出现在 [series.*] 与 [pending]：{sorted(overlap)}")

    cal = _table(raw, "calendar")
    _reject_extra(cal, {"exchange", "rules", "adhoc"}, where="[calendar]")
    exchange = _text(cal, "exchange", where="[calendar]")
    rules_raw = cal.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise SettingsError("[calendar] 缺少 rules，或 rules 为空")
    rules = tuple(_parse_rule(item, index=index) for index, item in enumerate(rules_raw))

    adhoc_raw = cal.get("adhoc", [])
    if not isinstance(adhoc_raw, list):
        raise SettingsError("[calendar.adhoc] 必须是数组")
    adhoc: list[tuple[date, str]] = []
    for index, item in enumerate(adhoc_raw):
        where = f"calendar.adhoc[{index}]"
        if not isinstance(item, dict):
            raise SettingsError(f"{where} 必须是表")
        _reject_extra(item, {"date", "reason"}, where=where)
        raw_day = _text(item, "date", where=where)
        try:
            day = date.fromisoformat(raw_day)
        except ValueError as exc:
            raise SettingsError(f"{where}.date 不是 ISO 日期：{raw_day!r}（{exc}）") from None
        adhoc.append((day, _text(item, "reason", where=where)))

    return NormalizationSettings(
        align_policy=policy,
        panel_dir=panel_dir,
        min_real_observations=min_real,
        exchange=exchange,
        series=tuple(sorted(series, key=lambda spec: spec.series_key)),
        pending=tuple(sorted(pending)),
        rules=rules,
        adhoc=tuple(sorted(adhoc)),
    )
