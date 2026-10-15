"""单位换算（L0）。全系统唯一的换算真值来源。

铁律：任何调用方都不得自行乘除换算系数，一律走 convert()。
跨物理量族换算直接抛错，不做隐式兜底。
数值一律用 Decimal，避免大数相减时的浮点误差。
"""

from __future__ import annotations

from decimal import Decimal

# 同一物理量族内的单位倍率（相对族基准，族基准倍率 = 1）。
_FAMILIES: dict[str, dict[str, Decimal]] = {
    "USD": {
        "USD": Decimal(1),
        "USD_THOUSAND": Decimal(10) ** 3,
        "USD_MILLION": Decimal(10) ** 6,
        "USD_BILLION": Decimal(10) ** 9,
        "USD_TRILLION": Decimal(10) ** 12,
    },
}

_UNIT_FAMILY: dict[str, str] = {
    unit: family for family, members in _FAMILIES.items() for unit in members
}

# 无量纲或自成一族的单位。彼此之间以及与 USD 族之间都不得互转。
_STANDALONE: tuple[str, ...] = (
    "RATIO",
    "INDEX_POINT",
    "PERCENT",
    "JPY_PER_USD",
    "USD_PER_BARREL",
)


class UnitError(ValueError):
    """单位未登记，或发生了跨族换算。一律 fail fast。"""


def registered() -> set[str]:
    """所有已登记的单位令牌。配置里出现的单位必须落在这个集合内。"""
    return set(_UNIT_FAMILY) | set(_STANDALONE)


def family_of(unit: str) -> str:
    if unit in _UNIT_FAMILY:
        return _UNIT_FAMILY[unit]
    if unit in _STANDALONE:
        return unit
    raise UnitError(f"未登记的单位令牌：{unit!r}")


def convert(value: object, src: str, dst: str) -> Decimal:
    """把 value 从 src 单位换算成 dst 单位。跨族即报错。"""
    if src == dst:
        family_of(src)
        return Decimal(str(value))
    family_src, family_dst = family_of(src), family_of(dst)
    if family_src != family_dst:
        raise UnitError(f"拒绝跨族换算：{src} ({family_src}) -> {dst} ({family_dst})")
    return Decimal(str(value)) * _FAMILIES[family_src][src] / _FAMILIES[family_src][dst]


def total(terms: list[tuple[object, str]], *, target: str) -> Decimal:
    """把 [(值, 单位)] 全部换算到 target 后求和。

    存在的意义：调用方无法"忘记"换算某一项。
    """
    return sum((convert(value, unit, target) for value, unit in terms), Decimal(0))
