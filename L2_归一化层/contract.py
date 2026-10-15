"""L2 → L3 契约：`Panel`。

按架构文档第 4 节，契约由**生产者层**定义 —— `Panel` 是 L2 的产物，所以它住在 L2。

`Panel` 是一张长表：`(date, series_key, value, unit, fill_flag, source_as_of)`。
它的存在意义是让下游**看得见每个值的来历**：哪一天的值、真实数据日是哪天、
这个值是不是被填充出来的。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from L0_基元层.units import registered

# 长表的列顺序，也是落盘顺序。改这里就等于改落盘格式，别乱动。
COLUMNS: tuple[str, ...] = (
    "date",
    "series_key",
    "value",
    "unit",
    "fill_flag",
    "source_as_of",
)


class PanelError(ValueError):
    """面板违反不变量。一律 fail fast —— 面板是下游全部统计的地基。"""


@dataclass(frozen=True, slots=True)
class PanelRow:
    date: date
    series_key: str
    value: Decimal
    unit: str
    fill_flag: bool
    source_as_of: date


@dataclass(frozen=True, slots=True)
class Panel:
    as_of: date
    rows: tuple[PanelRow, ...]

    def series_keys(self) -> tuple[str, ...]:
        return tuple(sorted({row.series_key for row in self.rows}))

    def rows_of(self, series_key: str) -> tuple[PanelRow, ...]:
        return tuple(row for row in self.rows if row.series_key == series_key)


def _check_rows(rows: tuple[PanelRow, ...], *, as_of: date) -> None:
    seen: set[tuple[str, date]] = set()
    units_by_series: dict[str, str] = {}
    for row in rows:
        key = (row.series_key, row.date)
        if key in seen:
            raise PanelError(f"同一 series_key 同一日期出现多条：{row.series_key} @ {row.date}")
        seen.add(key)

        if row.unit not in registered():
            raise PanelError(f"{row.series_key} 的单位未登记：{row.unit!r}")
        if not row.value.is_finite():
            raise PanelError(f"{row.series_key} @ {row.date} 的值不是有限数：{row.value}")
        if row.date > as_of:
            raise PanelError(f"{row.series_key} @ {row.date} 超出面板 as_of={as_of}")
        if row.source_as_of > row.date:
            raise PanelError(
                f"{row.series_key} @ {row.date} 的 source_as_of={row.source_as_of} 晚于该行日期"
            )

        # 核心不变量：fill_flag 与 "date != source_as_of" 必须**互为充要条件**。
        # 这一条把"填充点伪装成真实观测"变成结构上不可能，而不是靠自觉。
        if row.fill_flag != (row.date != row.source_as_of):
            raise PanelError(
                f"{row.series_key} @ {row.date}：fill_flag={row.fill_flag} 与 "
                f"source_as_of={row.source_as_of} 不一致（填充点必须打标，非填充点不得打标）"
            )

        # 同一 series_key 内单位必须唯一。
        # 注意：**不是**"整个面板一个单位" —— 面板里同时有 USD / PERCENT / INDEX_POINT，
        # 而 L0 units 禁止跨族换算，所以全局单一单位按字面不可能成立。
        previous = units_by_series.setdefault(row.series_key, row.unit)
        if previous != row.unit:
            raise PanelError(
                f"{row.series_key} 出现两种单位：{previous} 与 {row.unit}"
            )


def make_panel(rows: list[PanelRow], *, as_of: date) -> Panel:
    """把若干行装订成面板：先按 (date, series_key) 排序保证可复现，再校验不变量。"""
    ordered = tuple(sorted(rows, key=lambda row: (row.date, row.series_key)))
    _check_rows(ordered, as_of=as_of)
    return Panel(as_of=as_of, rows=ordered)
