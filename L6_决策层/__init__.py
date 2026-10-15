"""L6 决策层 —— 尚未实现。

计划职责：把 CRSReport 映射成执行动作。只做映射，不做计算。
计划模块：playbook/positions.py、playbook/structures.py、playbook/t1_protocol.py。
产物：ActionPlan(positions, structures, stops, max_risk, rationale)。

依赖：只依赖 L0–L5。
硬约束：Max Risk 超限即报错；不假设无人值守。
"""
