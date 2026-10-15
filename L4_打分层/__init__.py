"""L4 打分层 —— 尚未实现（且必须等阈值标定完成后再写）。

计划职责：把物理量按规则映射成 0–100 的分项得分。纯规则映射，不做计算。
计划模块：scoring/rules.py、scoring/thresholds.py、scoring/interpolate.py。
产物：SubScore(dimension, score, band, fired_rule_ids)。

依赖：只依赖 L0–L3。
硬约束：阈值只存在于本层配置；输出必须是确定点值，不得是区间。
"""
