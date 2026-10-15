"""新鲜度门禁（L2）。超限即 **fail-closed** —— 不是警告、不是降级、不是打个标记继续。

度量口径：**交易日**（配置键 `max_staleness_trading_days`）。
为什么不用自然日：日频序列在周末与长周末会被自然日口径误判为"陈旧"。
例：周五的值到周一，自然日是 3 天；若上限写成 3 就每周一都报警。
交易日口径下这个滞后是 1，且与"这个值被前向搬运了几个交易日"直接对应。

为什么需要一个足够长的轴：滞后只能被"轴"度量。轴比最大上限还短时本模块**报错**，
而不是判定通过 —— **判定不了的检查必须失败，不能沉默**（否则门禁等于空转）。
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence

from L2_归一化层.contract import Panel


class StalenessError(RuntimeError):
    """新鲜度超限，或无法判定新鲜度。两者都是失败。"""


@dataclass(frozen=True, slots=True)
class StalenessFinding:
    series_key: str
    source_as_of: date
    lag_trading_days: int
    limit_trading_days: int

    @property
    def exceeded(self) -> bool:
        return self.lag_trading_days > self.limit_trading_days


def lag_trading_days(
    axis: Sequence[date], *, source_as_of: date, as_of: date
) -> int:
    """轴上落在 `(source_as_of, as_of]` 区间内的交易日数。

    用 bisect 而不是"数一遍"：轴升序，两次二分即得，且不依赖 source_as_of 本身落在轴上
    （FRED 的周度值偶尔会落在休市日）。
    """
    return bisect_right(axis, as_of) - bisect_right(axis, source_as_of)


def check_staleness(
    panel: Panel,
    *,
    axis: Sequence[date],
    limits: Mapping[str, int],
) -> tuple[StalenessFinding, ...]:
    """逐序列算尾部滞后。返回全部结论，**不抛超限异常** —— 由 `enforce` 统一裁决。"""
    if not limits:
        raise StalenessError("没有任何序列声明新鲜度上限")
    if not panel.rows:
        raise StalenessError("面板没有任何行，无法判定新鲜度")

    max_limit = max(limits.values())
    if len(axis) < max_limit + 1:
        raise StalenessError(
            f"时间轴只有 {len(axis)} 个交易日，不足以判定最大上限 {max_limit} 个交易日 —— "
            f"需要至少 {max_limit + 1} 个，否则超限永远测不出来，门禁等于空转"
        )

    declared = set(panel.series_keys())
    undeclared = sorted(declared - set(limits))
    if undeclared:
        raise StalenessError(f"以下序列没有声明新鲜度上限：{undeclared}")
    absent = sorted(set(limits) - declared)
    if absent:
        raise StalenessError(f"以下序列声明了上限但不在面板里：{absent}")

    findings: list[StalenessFinding] = []
    for key in panel.series_keys():
        tail = max(panel.rows_of(key), key=lambda row: row.date)
        findings.append(
            StalenessFinding(
                series_key=key,
                source_as_of=tail.source_as_of,
                lag_trading_days=lag_trading_days(
                    axis, source_as_of=tail.source_as_of, as_of=panel.as_of
                ),
                limit_trading_days=limits[key],
            )
        )
    return tuple(findings)


def enforce(findings: Sequence[StalenessFinding]) -> None:
    """任一序列超限即整体失败。没有"部分可用"这种中间态。"""
    exceeded = [item for item in findings if item.exceeded]
    if not exceeded:
        return
    detail = "；".join(
        f"{item.series_key} 滞后 {item.lag_trading_days} 交易日 > 上限 {item.limit_trading_days}"
        for item in exceeded
    )
    raise StalenessError(f"新鲜度门禁失败（fail-closed）：{detail}")
