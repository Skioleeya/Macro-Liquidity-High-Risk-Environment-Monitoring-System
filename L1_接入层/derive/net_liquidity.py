"""维度一原语：货币财政净流动性（L1 派生原语）。

白皮书原文写作 `WALCL - WTREGEN - RRPONTSYD`，但三者单位并不一致：
前两者是百万美元，RRPONTSYD 是十亿美元。直接相减在 RRP 处于低位时
误差可忽略，一旦 RRP 回到 2022 年量级（约 2 万亿）误差就达约 2 万亿。

本模块一律先换算到目标单位再运算，不提供"直接相减"的入口。

分层位置说明：此处只输出"公式级"的量，不带窗口、不标准化，因此属于 L1
派生原语；L3 因子层将来在此之上做滚动标准化并输出 FactorReading。
"""

from __future__ import annotations

from decimal import Decimal

from L0_基元层.units import convert

SIGN_PLUS = 1
SIGN_MINUS = -1


def net_liquidity(terms: list[tuple[object, str, int]], *, target: str) -> Decimal:
    """terms = [(值, 单位, 符号)]，符号取 +1 或 -1。

    目标单位由配置给出（config/sources.toml 的 units.net_liquidity_target），
    不在此处硬编码。
    """
    result = Decimal(0)
    for value, unit, sign in terms:
        if sign not in (SIGN_PLUS, SIGN_MINUS):
            raise ValueError(f"符号只能是 +1 / -1，收到 {sign!r}")
        result += convert(value, unit, target) * sign
    return result
