"""L2 归一化层 —— 尚未实现。

计划职责：把异构观测对齐成可比面板，并做新鲜度门禁。
计划模块：align（时间轴对齐）/ convert（单位归一）/ staleness（新鲜度门禁）/ panel_store。
产物：Panel —— 长表 (date, series_key, value, unit, fill_flag, source_as_of)。

依赖：只依赖 L0、L1。
硬约束：纯函数 + 显式日期参数，不得读"现在"（重放/回测的前提）。
"""
