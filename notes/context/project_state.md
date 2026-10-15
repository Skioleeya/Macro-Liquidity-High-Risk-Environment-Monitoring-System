LAST_UPDATED: 2026-10-15

CURRENT_STATE:
- 阶段：正式分层目录已落地 + L0/L1 已迁入并验证。**L2–L7 与重放骨架均未开始。**
- 可运行代码在正式分层目录：`L0_基元层/` + `L1_接入层/`。驱动与校验命令在**仓库根目录**执行：
  `python -m tools.fetch_all`（3/3 通过）、`python -m tools.selfcheck`（9/9 通过）、
  `python -m tools.check_layering`（17 文件 0 违规）。
- `mvp/` 保留为迁移差分参照，**与正式分层是同一套逻辑的两份拷贝**，去留待 KAI 裁定。
- 正式项目架构总纲：`docs/正式项目分层架构设计.md`（**改架构先改它**，第 9 节是落地状态）。
- 仓库无 git（`git rev-parse` → not a repository）。

NEXT:
- 先由 KAI 裁定 `docs/正式项目分层架构设计.md` 第 10 节的 5 项前置决策。
  最紧两条：**三套阈值口径以哪套为准**、**回测窗口**（ICE BofA 仅 3 年）。这两条不定，L4 无法开工。
- 另需裁定：`mvp/` 去留、是否 `git init`（建议先 init 再删，否则不可恢复）。
- 然后开 **L2 归一化层**会话，必须带 `startup.md`；动 L2 之前先补 L0 的 `clock`。
