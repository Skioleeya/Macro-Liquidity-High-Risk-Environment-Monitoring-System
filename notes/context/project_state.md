LAST_UPDATED: 2026-10-15

CURRENT_STATE:
- 阶段：正式分层目录已落地；**L0 / L1 / L2 可用**；**L3–L7 与重放骨架未开始。**
- 可运行代码在正式分层目录：`L0_基元层/` + `L1_接入层/` + `L2_归一化层/`。
  驱动与校验命令一律在**仓库根目录**执行：
  `python -m tools.fetch_all`（3/3）、`python -m tools.build_panel`（15 序列 / 194 行）、
  `python -m tools.selfcheck`（9/9）、`python -m tools.selfcheck_l2`（11/11）、
  `python -m tools.check_layering`（28 文件 0 违规）。
- 数据流已打通：`data/raw/<date>/` → L1 `Observation` 流 → L2 `Panel` → `data/panel/panel_<date>.csv`。
  `Panel` 列：`(date, series_key, value, unit, fill_flag, source_as_of)`。
- **版本控制已就位**：`origin` = `git@github.com:Skioleeya/Macro-Liquidity-High-Risk-Environment-Monitoring-System.git`
  （公开仓库）。`.env` / `data/` 已确认未进仓库。换行由 `.gitattributes` 钉为 LF。
  ⚠️ 本环境每次推进式 push 后 `origin/main` 会静默陈旧，**推送一律用 `git psh`**（本机 alias）。
- `mvp/` **已裁定保留、冻结勿改**（KAI 2026-10-15）：它是 `artifacts/port_fidelity.py` 的唯一参照实现。
- 正式项目架构总纲：`docs/正式项目分层架构设计.md`（**改架构先改它**，第 9 节是落地状态）。

NEXT:
- 先由 KAI 裁定 `docs/正式项目分层架构设计.md` 第 10 节的 5 项前置决策。
  最紧两条：**三套阈值口径以哪套为准**、**回测窗口**（ICE BofA 仅 3 年）。这两条不定，L4 无法开工。
- 然后建 **重放骨架**（架构文档第 6 节阶段 2，**必须早于 L3/L4**）。
  它要解决的第一件事是"历史回补"——现有取数配置（FRED 10 条 / Yahoo 5d / CBOE 末 5 行）
  远不够 L3 的 60D 窗口，详见 L2 会话 handoff 的 OPEN-RISKS 第 1 条。
