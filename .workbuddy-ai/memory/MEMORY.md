# MEMORY.md — CRS-100 项目路由器

LAST_UPDATED: 2026-10-15

本文件只做三件事：**指路**、**记当前状态指针**、**记时间戳**。
不写经验、不写规则条文、不写清单 —— 那些各有归属（见路由表）。

## 当前状态指针

- 阶段：正式分层目录已落地 + L0/L1 已迁入并验证；**L2–L7 与重放骨架未开始**。
- 版本控制：`origin` = `git@github.com:Skioleeya/Macro-Liquidity-High-Risk-Environment-Monitoring-System.git`（公开），`main` = `60ce516`。
  ⚠️ 本环境每次推进式 push 后 `origin/main` 会**静默陈旧**，`git status` 谎报 `[ahead N]` ——
  远端其实是对的，**不要重推/不要 --force**。修法与取证见 skill `git-tracking-ref-stale`。
- 详情、待办、最近交接统一在 `notes/context/` 下，本文件不复述。

## 路由表

| 要找什么 | 去哪 |
|---|---|
| 当前状态 | `notes/context/project_state.md` |
| 待办 | `notes/context/open_tasks.md` |
| 最近交接 | `notes/context/handoff.md` |
| 某次会话做了什么 | `notes/sessions/YYYY-MM-DD/<task-id>/handoff.md` |
| 设计取舍 / 被否决方案 / 踩过的坑 | 同目录 `project_state.md` |
| 会话的原始命令输出 / 审计脚本 | 同目录 `artifacts/` |
| **架构总纲（改架构先改它）** | `docs/正式项目分层架构设计.md` |
| 白皮书拆解结论与缺陷清单 | `docs/CRS-100_白皮书摘要与要点总结.md` |
| 数据源账户需求与端点实测 | `docs/数据源接入清单_账户与端点核查.md` |
| 外部建议裁定与理由 | `docs/Gemini建议评估_以实测为准.md` |
| 可运行代码（正式） | `L0_基元层/` · `L1_接入层/` |
| 驱动 / 自检 / 分层校验 | `tools/`（非分层；`fetch_all.py` · `selfcheck.py` · `check_layering.py`） |
| 数据源结构常量（端点 / 序列 / 单位） | `config/sources.toml` |
| MVP 参照实现（**迁移差分用，去留待裁定**） | `mvp/` |
| 会话记录该怎么写 | skill `notes-session-records` |
| 回归是否在空转 | skill `harness-silent-pass-audit` |
| 移植/拆文件后如何证明行为没变 | skill `code-port-fidelity-audit` |
| `git status` 报 `[gone]` / ahead-behind 与实际不符 | skill `git-tracking-ref-stale` |

## 项目级约定（仅指针，条文不在此处）

- 工程约束（文件 < 400 行、单一职能、禁止硬编码、严格分层、配置互不引用）继承用户级 `~/.workbuddy-ai/MEMORY.md`，本项目不重复。
- 本项目的机械校验：`python -m tools.check_layering`（层级单向依赖）、`python -m tools.selfcheck`（单位 + 脱敏，9 项，含对照组与变异自测）。**均在仓库根目录执行。**
- git 提交身份为**仓库级**：`Skioleeya` / `Skioleeya@users.noreply.github.com`（刻意不用真实邮箱，因为远端是公开仓库）。


