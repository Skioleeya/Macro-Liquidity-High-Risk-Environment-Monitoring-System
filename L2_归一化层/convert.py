"""单位归一（L2）。把 L1 观测换算到配置声明的目标单位。

铁律：换算只走 `L0_基元层.units.convert`，本层不得自行乘除任何系数。
跨物理量族（如 USD -> PERCENT）由 L0 直接拒绝 —— 这里不捕获成"跳过"、不做兜底。

为什么这一步必须在 L2 而不是 L3：白皮书把 WALCL/WTREGEN（百万）与 RRPONTSYD（十亿）
直接相减。这个错误如果拖到 L3，L3 的输入就已经是错的了，后面全白做。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping

from L0_基元层.units import UnitError, convert
from L1_接入层.contract import Observation


class ConvertError(ValueError):
    """序列没有声明目标单位，或换算本身不成立。"""


def convert_observation(obs: Observation, *, target_unit: str) -> Observation:
    """返回单位换成 `target_unit` 的新观测。

    单位已一致时原样返回：不做无谓的 Decimal 往返，也避免把 `Decimal("30.00")`
    规范化成 `Decimal("30.0")` 这种"看起来没变其实变了"的差异。
    """
    if obs.unit == target_unit:
        return obs
    try:
        value = convert(obs.value, obs.unit, target_unit)
    except UnitError as exc:
        raise ConvertError(f"{obs.series_key} @ {obs.date}：{exc}") from exc
    return replace(obs, value=value, unit=target_unit)


def convert_all(
    observations: Iterable[Observation], targets: Mapping[str, str]
) -> list[Observation]:
    """按 `series_key -> target_unit` 批量换算。缺目标单位即报错（不猜、不跳过）。"""
    out: list[Observation] = []
    for obs in observations:
        if obs.series_key not in targets:
            raise ConvertError(f"序列 {obs.series_key} 没有声明目标单位")
        out.append(convert_observation(obs, target_unit=targets[obs.series_key]))
    return out
