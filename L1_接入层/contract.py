"""L1 → L2 契约：`Observation`。

按架构文档第 4 节，**契约由生产者层定义** —— `Observation` 是 L1 的产物，
所以它住在 L1。消费者（L2）只读不写。

一个 `Observation` 回答的是："**某个序列在某一天的真实取值**"，
并且必须带上单位（不能靠猜）、来源（可追责）、取回时刻（可审计新鲜度）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from L0_基元层.units import registered


class ObservationError(ValueError):
    """观测不合法。一律 fail fast，不做任何默认值兜底。"""


@dataclass(frozen=True, slots=True)
class Observation:
    series_key: str
    date: date
    value: Decimal
    unit: str
    source: str
    retrieved_at: datetime


def make_observation(
    *,
    series_key: str,
    day: date,
    value: object,
    unit: str,
    source: str,
    retrieved_at: datetime,
) -> Observation:
    """构造并校验一个 Observation。任何一项不合格即报错。

    刻意收得比较紧：
      - `unit` 必须是 L0 已登记的令牌 —— 拼错单位比取错数更难发现，这里先拦住；
      - `value` 走 `Decimal(str(...))`，**不用 float 直接构造** ——
        `Decimal(0.1)` 会得到 0.1000000000000000055511151231257827021181583404541015625；
      - `retrieved_at` 必须带时区 —— 裸时间戳无法判断是哪天的数据。
    """
    if not series_key or not series_key.strip():
        raise ObservationError("series_key 不能为空")
    if not isinstance(day, date):
        raise ObservationError(f"day 必须是 datetime.date，收到 {type(day).__name__}")
    if isinstance(value, bool):
        raise ObservationError("value 不接受布尔值")
    if not unit or unit not in registered():
        raise ObservationError(f"未登记的单位令牌：{unit!r}")
    if not source or not source.strip():
        raise ObservationError("source 不能为空")
    if not isinstance(retrieved_at, datetime):
        raise ObservationError(f"retrieved_at 必须是 datetime，收到 {type(retrieved_at).__name__}")
    if retrieved_at.tzinfo is None:
        raise ObservationError("retrieved_at 必须带时区（裸时间戳无法判断是哪天的数据）")

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ObservationError(f"value 无法转成 Decimal：{value!r}（{exc}）") from None
    if not decimal_value.is_finite():
        raise ObservationError(f"value 必须是有限数，收到 {value!r}")

    return Observation(
        series_key=series_key,
        date=day,
        value=decimal_value,
        unit=unit,
        source=source,
        retrieved_at=retrieved_at,
    )
