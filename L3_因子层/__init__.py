"""L3 因子层 —— 尚未实现。

计划职责：每个物理维度一个模块，从 Panel 算出原始因子值（不是分数）。
计划模块：factors/net_liquidity.py、factors/gamma_proxy.py、factors/credit_stress.py、factors/calendar.py。
产物：FactorReading(factor_key, value, unit, as_of, window, inputs)。

依赖：只依赖 L0、L1、L2。
硬约束：四个维度之间零依赖；窗口不足必须抛错，不得用部分窗口凑。
"""
