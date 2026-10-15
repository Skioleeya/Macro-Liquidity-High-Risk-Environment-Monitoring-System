"""NYSE 交易日轴（L2）。

职责边界：把 `config/normalization.toml` 里的日历**规则数据**求值成"哪些天开市"。
不做任何业务判断 —— "OPEX 算不算风险""FOMC 静默期要不要计分"属于 L3/L4。

假期规则本身是**数据**（交易所会增删规则、会临时休市），所以住在配置里；
`L0_基元层/clock.py` 只提供求值这些规则所需的纯日期算术（第 N 个星期几、复活节、顺延）。
这样切的好处：改一条假期规则不触碰任何代码，也不会让日历模块同时被上下两层依赖。

纯函数 + 显式日期参数：本模块不读"现在"。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from L0_基元层 import clock
from L2_归一化层.settings import CalendarRule, NormalizationSettings


class CalendarError(ValueError):
    """日历规则不合法，或所求日期不存在（如某月没有第 5 个周一）。"""


def resolve_rule(rule: CalendarRule, year: int) -> date | None:
    """把一条规则在该年求值成一个休市日。返回 None 表示该年此规则不生效。

    返回 None 的两种情形（必须区分清楚，别混成"没假期"）：
      1. `from_year` 晚于该年 —— 规则还没生效；
      2. 固定日落在周六且 `saturday_shift = false` —— 当天本来就休市，
         不额外把休市挪到周五（NYSE 元旦特例）。
    """
    if rule.from_year is not None and year < rule.from_year:
        return None

    if rule.kind == "fixed":
        base = date(year, rule.month, rule.day)
        if not rule.observed:
            return base
        if base.weekday() == 5:  # 周六
            return None if not rule.saturday_shift else base - timedelta(days=1)
        if base.weekday() == 6:  # 周日
            return base + timedelta(days=1)
        return base

    if rule.kind == "nth":
        try:
            return clock.nth_weekday(year, rule.month, rule.weekday, rule.n)
        except clock.ClockError as exc:
            # 规则本身合法（settings 已校验形状），但该年凑不出这个日期。
            # 报错而不是跳过：静默跳过等于那条规则凭空消失。
            raise CalendarError(f"规则 {rule.name!r} 在 {year} 年无法求值：{exc}") from None

    if rule.kind == "last":
        return clock.last_weekday(year, rule.month, rule.weekday)

    if rule.kind == "easter_offset":
        return clock.easter_sunday(year) + timedelta(days=rule.offset_days)

    raise CalendarError(f"未登记的规则种类：{rule.kind!r}")


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    exchange: str
    rules: tuple[CalendarRule, ...]
    adhoc: tuple[tuple[date, str], ...]

    def holidays(self, year: int) -> dict[date, str]:
        """该年所有**落在工作日**的休市日 -> 原因串。

        必须把**相邻年份**的规则也求一遍：带 `observed` 的固定日可能被顺延到
        上一年（元旦 1/1 落在周六 -> 提前到上一年的 12/31）。只求本年规则的话，
        这个休市日会永远查不到 —— 而这正是"周六顺延"最容易漏的一格。

        周末落点不列入：周末本来就休市，列进去会让"休市日"这个概念变糊。
        """
        found: dict[date, str] = {}
        for rule_year in (year - 1, year, year + 1):
            for rule in self.rules:
                day = resolve_rule(rule, rule_year)
                if day is None or day.year != year or clock.is_weekend(day):
                    continue
                found[day] = f"rule:{rule.name}"
        for day, reason in self.adhoc:
            if day.year == year and not clock.is_weekend(day):
                found[day] = f"adhoc:{reason}"
        return found

    def is_trading_day(self, day: date) -> bool:
        if clock.is_weekend(day):
            return False
        return day not in self.holidays(day.year)

    def trading_days(self, start: date, end: date) -> list[date]:
        """闭区间 [start, end] 内的交易日，升序。start > end 时返回空表。"""
        if start > end:
            return []
        cache: dict[int, dict[date, str]] = {}
        result: list[date] = []
        for day in clock.date_range(start, end):
            if clock.is_weekend(day):
                continue
            table = cache.get(day.year)
            if table is None:
                table = cache[day.year] = self.holidays(day.year)
            if day not in table:
                result.append(day)
        return result


def from_settings(cfg: NormalizationSettings) -> TradingCalendar:
    return TradingCalendar(exchange=cfg.exchange, rules=cfg.rules, adhoc=cfg.adhoc)
