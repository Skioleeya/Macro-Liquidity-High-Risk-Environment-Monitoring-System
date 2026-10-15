"""L5 合成层 —— 尚未实现。

计划职责：加权融合 + 状态机 + 分级。只做合成，不引入新的物理判断。
计划模块：composite/weights.py、composite/regime.py、composite/grading.py。
产物：CRSReport(crs, level, regime, subscores, fired_rules, as_of)。

依赖：只依赖 L0–L4。
硬约束：权重和必须严格 = 100.00%，不等即拒绝启动。
"""
