"""L2 归一化层 —— 把异构观测对齐成可比面板，并做新鲜度门禁。

产物：`Panel` —— 长表 `(date, series_key, value, unit, fill_flag, source_as_of)`。

模块与职责（单一职能）：

| 模块 | 职责 | 层内角色 |
|---|---|---|
| `settings.py` | 读并校验 `config/normalization.toml`，只校验形状不算数 | 共享叶子 |
| `contract.py` | L2 → L3 契约 `Panel` / `PanelRow` 及其不变量 | 共享叶子 |
| `calendar.py` | 由配置里的假期规则数据求值出 NYSE 交易日轴 | 计算 |
| `convert.py` | 单位归一，只走 L0 `units.convert` | 计算 |
| `align.py` | 投到交易日轴 + 前向填充 + 打 `fill_flag` | 计算 |
| `staleness.py` | 尾部滞后门禁，超限 fail-closed | 计算 |
| `panel_store.py` | 面板 CSV 落盘 / 读取（读回时重新校验不变量） | 持久化 |
| `pipeline.py` | 组装入口 `build_panel` / `build_and_store` | **层内编排（唯一）** |

依赖：只依赖 L0 与 L1。硬约束：纯函数 + 显式日期参数，不读"现在"（重放/回测的前提）。

层内依赖规则（由 `tools/check_layering.py` 机械校验，声明不实即报错）：
  - `settings.py` / `contract.py` 是**共享叶子**，不得 import 本层任何其它模块；
  - `pipeline.py` 是**层内编排**，可以 import 本层其它模块，但**不得被本层任何模块 import**；
  - 其余模块之间不得互相 import。
"""

from __future__ import annotations

__all__ = [
    "align",
    "calendar",
    "contract",
    "convert",
    "panel_store",
    "pipeline",
    "settings",
    "staleness",
]
