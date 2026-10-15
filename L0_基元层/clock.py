"""日期基元（L0）。只做纯日期算术，不含任何市场判断，也**不含任何假期数据表**。

为什么不含假期数据：假期规则是**数据**（交易所会临时休市、规则会增删），
数据属于配置；本层只提供"求值这些规则"所需的通用算术
（第 N 个星期几、复活节、周六周日顺延）。

本层不知道什么是"交易日"，也不知道什么是 NYSE —— 那些是 L2 的组装职责。
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

# date.weekday() 的取值是 Mon=0 … Sun=6，这里给出与配置里书写的对应关系。
WEEKDAY_NAMES: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class ClockError(ValueError):
    """日期参数不合法，或所求的日期不存在（如某月没有第 5 个周一）。"""


def weekday_index(name: str) -> int:
    """把 "MON" 这类写法转成 date.weekday() 的索引。不认识的写法直接报错。"""
    key = name.strip().upper()
    if key not in WEEKDAY_NAMES:
        raise ClockError(f"未登记的星期写法：{name!r}（可用 {WEEKDAY_NAMES}）")
    return WEEKDAY_NAMES.index(key)


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def nth_weekday(year: int, month: int, weekday: str, n: int) -> date:
    """某年某月的第 n 个「星期几」。n 从 1 起；该月没有第 n 个则报错。"""
    if n < 1:
        raise ClockError(f"n 必须 >= 1，收到 {n}")
    target = weekday_index(weekday)
    first = date(year, month, 1)
    day = 1 + (target - first.weekday()) % 7 + (n - 1) * 7
    if day > calendar.monthrange(year, month)[1]:
        raise ClockError(f"{year}-{month:02d} 没有第 {n} 个 {weekday.upper()}")
    return date(year, month, day)


def last_weekday(year: int, month: int, weekday: str) -> date:
    """某年某月最后一个「星期几」。"""
    target = weekday_index(weekday)
    last_day = calendar.monthrange(year, month)[1]
    tail = date(year, month, last_day)
    return date(year, month, last_day - (tail.weekday() - target) % 7)


def easter_sunday(year: int) -> date:
    """复活节（Anonymous Gregorian 算法）。仅用于推导耶稣受难日。"""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    j = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * j) // 451
    month, day = divmod(h + j - 7 * m + 114, 31)
    return date(year, month, day + 1)


def good_friday(year: int) -> date:
    """耶稣受难日 = 复活节前的星期五。"""
    return easter_sunday(year) - timedelta(days=2)


def observed(day: date) -> date:
    """美式顺延规则：落在周六的假日提前到周五，落在周日的顺延到周一，其余原样。"""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def date_range(start: date, end: date) -> list[date]:
    """闭区间 [start, end] 的逐日列表。start > end 时返回空表（不是报错）。"""
    if start > end:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]
