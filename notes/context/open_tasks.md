# Open Tasks

- Archive: N/A:尚无归档

## Active

- [ ] **【阻塞 L4】裁定阈值方案** —— 走"绝对阈值 + 滚动分位"混合，还是全量分位。全量分会丢失绝对水平信息、把参数问题搬到窗口长度、趋势 regime 下失效。理由见 `docs/Gemini建议评估_以实测为准.md` 第 4 节。
- [ ] **【阻塞 L4】确定回测窗口** —— ICE BofA 仅剩 3 年（2023-10-16 起）。若用 HYG/LQD 代理，须先定久期错配处理方式，并声明"代理回测结论不可迁移实盘"。
- [ ] **【阻塞 L4】阈值标定** —— 用重放骨架在历史上定阈值与分数段插值规则。白皮书零验证，此项无捷径。
- [ ] **建重放骨架** —— 必须早于 L3/L4。前提：L2–L5 为纯函数 + 显式日期参数（L2 已满足）。**它要解决的第一件事是历史回补**：现有取数配置（FRED `default_limit=10`、Yahoo `range=5d`、CBOE 只留末 5 行）远不够 L3 的 60D 窗口，见 `notes/sessions/2026-10-15/l2-normalization/handoff.md` OPEN-RISKS 第 1 条。
- [ ] **补 CBOE PCR 页面日期解析** —— 页面上的交易日未被解析，导致 PCR 无法进面板（现列 `[pending]`）。不补就只能用落盘目录名冒充日期。
- [ ] **给 `[pending]` 加滞留守卫** —— 自检只核对"是否被交代过"，不检查 pending 条目是否长期滞留。
- [ ] **决定 TGA 取 FRED 周频还是财政部日频** —— 财政部 Fiscal Data API 实测可用且日频，但口径与 FRED 不同（同日差异 ±3 万百万美元摆动），切换会产生口径断点。
- [ ] **决定输出是否对外** —— 决定 L7 分发边界的严格程度（ICE BofA 禁止再分发）。已采纳 Gemini 的"只输出 0–100 得分、不直显 HY OAS 基点"。
- [ ] **建 CBOE PCR 离线样例回归** —— 端点靠解析 RSC payload（**不是** `__NEXT_DATA__`），CBOE 改版即失效。已排除 Yahoo 备选（无 PCR 代码）。
- [ ] **删除 Flip Point 相关设计** —— CBOE PCR 无行权价 / 到期日 / 持仓分布，该指标不可计算。
- [ ] **补 L0 的 `log`** —— 架构文档第 3 节列出，尚未实现。
- [ ] **补 `L1_接入层/sources/fed_calendar.py`** —— FOMC 日程适配器，L3 日历因子需要。
- [ ] **可选：把 `gc.auto=0` 写进仓库配置** —— 防 `git commit` 触发 auto-gc 挂住命令。本次未复现该问题。

## Stale / Needs Verification

- [ ] Yahoo Finance 作为数据源 —— 非官方接口，实测已出现 429 限流。需评估是否换源或加兜底。
- [ ] 本环境 git 写不了 `.git/refs/` 下第 3 层及更深的路径 —— 已实测确认（≤2 层可写、≥3 层被静默吞掉，提前建父目录也失败），并已修复当前值。**但修复不是根治，每次推进式 push 后须重跑；拦截者是谁未查明，未在沙箱外复跑。** 已用仓库级 alias `git psh` 缓解（推送+修引用一步到位），**但该 alias 只在本机 `.git/config` 里，换机器要重建**。

## Closed in session

（本会话：`notes/sessions/2026-10-15/l2-normalization/`）

- [x] **建 L2 归一化层** —— 七个模块 + 两端契约；真实数据端到端出面板（15 序列 / 194 行）。
- [x] **补 L0 的 `clock`** —— 纯日期基元，**不含假期数据表**（假期规则是数据，进 `config/normalization.toml`）。
- [x] 打通 L1 → L2 通道 —— `L1_接入层/observations.py`；`series_key` 约定收敛到唯一实现。
- [x] `check_layering` 支持层内例外声明 —— `SHARED_MODULES` / `ORCHESTRATORS`，且声明本身被双向机械校验。
- [x] 抽出 `tools/checkkit.py` —— 两个自检脚本共用检查骨架，"检查器是否空转"只有一个真值。
- [x] 修 `port_fidelity.py` 连带误报 —— 去掉 `continue`；新增 `EVOLVED_MODULES` 区分"有意演化"与"未申报偷改"。

（上一会话：`notes/sessions/2026-10-15/crs100-bootstrap/`）

- [x] `units_selfcheck` 改名 → `tools/selfcheck.py`（迁移时一并做掉）
- [x] 是否 `git init` —— 已 init，远端 `git@github.com:Skioleeya/Macro-Liquidity-High-Risk-Environment-Monitoring-System.git`，已推送
- [x] `mvp/` 去留 —— **裁定：保留不删**（KAI 2026-10-15）。它是迁移保真审计的唯一参照；`mvp/` 从此冻结，不要改
- [x] 加 `.gitattributes` 统一换行 —— 已加 `* text=auto eol=lf`；实测仓库 blob 与工作区都是纯 LF
- [x] 加仓库 alias 合成"推送 + 修引用" —— 已加 `git psh`（定义见该会话 handoff 阶段 8）
