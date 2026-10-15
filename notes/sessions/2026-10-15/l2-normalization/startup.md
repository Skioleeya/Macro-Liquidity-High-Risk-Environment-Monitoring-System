STARTUP-PROOF: 本文件写于任何 L2 代码之前。基线为 git `0bdae39`（工作区干净）、
`tools/check_layering` 17 文件 0 违规、`tools/fetch_all` 3/3、`tools/selfcheck` 9/9，全部 RC=0。
`L2_归一化层/` 当时只有 1 个占位 `__init__.py`，无任何代码。

# Startup — L2 归一化层

## Session

- 任务：实现 CRS-100 的 L2 归一化层（把 L1 取回的异构观测对齐成可比面板）。
- 依据：`docs/正式项目分层架构设计.md` 第 3 节 L2 定义 + 第 4 节层间契约 + 第 5 节依赖规则。
- 上一会话：`notes/sessions/2026-10-15/crs100-bootstrap/`（STATUS: complete）。
  其 handoff 明令"下一个会话根必须带 `startup.md`"，本文件即履行该约定。

## Scope Understanding

- **In scope**
  - L2 的四个职责模块：`align`（时间轴对齐 + 填充打标）、`convert`（单位归一）、
    `staleness`（新鲜度门禁）、`panel_store`（面板落盘/读取）
  - L2 的两端契约：入 `Observation`（L1 产出）、出 `Panel`（L2 产出）
  - NYSE 交易日轴构建
  - L0 前置补齐：`clock.py`（纯日期基元）—— 架构文档第 3 节列出，且是 L2 的前置
  - `config/normalization.toml`
  - L2 自检 + 非空转反证
- **Out of scope**
  - L3 及以上的任何因子计算、阈值、打分（尤其"周度 Δ 定义在哪个节点"是 L3 的决策，
    L2 只负责把 `fill_flag` 与 `source_as_of` 暴露出来，让 L3 有依据可判）
  - 不改 `mvp/`（已裁定冻结）
  - 不改 L1 三个源适配器的解析逻辑（只新增契约模块，不重写适配器）

## Prior Context Read

- `docs/正式项目分层架构设计.md` → 取到的约束：L2–L5 必须**纯函数 + 显式日期参数，不读"现在"**；
  面板必须带 `fill_flag` 与 `source_as_of`；新鲜度超限要 **fail-closed 而非警告**。
- `notes/sessions/2026-10-15/crs100-bootstrap/handoff.md` → 取到的约束：
  ① `mvp/` 冻结，不要改；② 动 L2 之前先补 L0 的 `clock`；
  ③ 本环境推送一律用 `git psh`（git 跟踪引用会静默陈旧）；④ 结论必须有可复现命令证据。
- `notes/context/open_tasks.md` → 取到的约束：L2 含交易日轴、频率对齐（`fill_flag`）、
  单位归一、新鲜度门禁；周度序列的 Δ 定义节点**不在 L2 定**。

## Recent Git Context

- Key commits reviewed: `0bdae39`（三条裁定落地）、`7c5f8f4`（纠正 git 引用"耐久"错误结论）、
  `60ce516`、`20f9734`（初始化分层仓库）。工作区干净，无未提交改动。

## Worker Readiness

- **Risks noticed**
  1. **架构文档有一处内部矛盾**：第 3 节把"交易日、假期"列在 L0 `clock` 下，但同节的 L0 配置行
     写"无（仅 `.env` 提供密钥）"。假期规则是**数据**，L0 无配置就没地方放。
     → 本会话的处置见 `project_state.md` 第 1 节（不静默选一边，明确裁定并记理由）。
  2. **"同层内模块不得互相 import" 与"契约由生产者层定义"会打架**：
     `Panel` 由 L2 定义，则 `panel_store` 读它必然是同层 import。
     → 本会话的处置见 `project_state.md` 第 2 节。
  3. **架构文档"面板内所有值单位一致"按字面无法成立**：面板里同时有 USD 与 PERCENT 与
     INDEX_POINT，而 L0 `units` 禁止跨族换算。→ 按"同一 series_key 内单位一致"实现，并记理由。
  4. `max_staleness_days` 的取值是**政策**不是推导值，写进配置并声明，不假装它算出来的。
- **Blockers noticed**
  - 无硬阻塞。L4 的阈值裁定与回测窗口仍是 L4 的前置，不影响 L2 开工。
