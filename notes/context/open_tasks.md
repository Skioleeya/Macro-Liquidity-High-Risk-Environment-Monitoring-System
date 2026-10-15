# Open Tasks

- Archive: N/A:尚无归档（本会话为项目首次记录）

## Active

- [ ] **【阻塞 L4】裁定阈值方案** —— 走"绝对阈值 + 滚动分位"混合，还是全量分位。全量分会丢失绝对水平信息、把参数问题搬到窗口长度、趋势 regime 下失效。理由见 `docs/Gemini建议评估_以实测为准.md` 第 4 节。
- [ ] **【阻塞 L4】确定回测窗口** —— ICE BofA 仅剩 3 年（2023-10-16 起）。若用 HYG/LQD 代理，须先定久期错配处理方式，并声明"代理回测结论不可迁移实盘"。
- [ ] **【阻塞 L4】阈值标定** —— 用重放骨架在历史上定阈值与分数段插值规则。白皮书零验证，此项无捷径。
- [ ] **建重放骨架** —— 必须早于 L3/L4。前提：L2–L5 为纯函数 + 显式日期参数。
- [ ] **建 L2 归一化层** —— 含交易日轴、频率对齐（`fill_flag` 打标）、单位归一、新鲜度门禁。周度序列的 Δ 定义节点待定。
- [ ] **决定 TGA 取 FRED 周频还是财政部日频** —— 财政部 Fiscal Data API 实测可用且日频，但口径与 FRED 不同（同日差异 ±3 万百万美元摆动），切换会产生口径断点。
- [ ] **决定输出是否对外** —— 决定 L7 分发边界的严格程度（ICE BofA 禁止再分发）。已采纳 Gemini 的"只输出 0–100 得分、不直显 HY OAS 基点"。
- [ ] **建 CBOE PCR 离线样例回归** —— 端点靠解析 RSC payload（**不是** `__NEXT_DATA__`），CBOE 改版即失效。已排除 Yahoo 备选（无 PCR 代码）。
- [ ] **删除 Flip Point 相关设计** —— CBOE PCR 无行权价 / 到期日 / 持仓分布，该指标不可计算。
- [ ] **决定 `mvp/` 去留** —— 已随首条提交进 git（可恢复），现在只剩"是否现在就 `git rm -r mvp/`"。删掉会让 `artifacts/port_fidelity.py` 变成不可运行的参照脚本；不删则正式层与它继续互为重复拷贝。**不自行删除。**
- [ ] **补 L0 的 `clock`** —— 交易日 / 假期 / 第 N 个周五等纯日期基元。**是 L2 的前置**，L2 开工前必须补。
- [ ] **补 L0 的 `log`** —— 架构文档第 3 节列出，尚未实现。
- [ ] **补 `L1_接入层/sources/fed_calendar.py`** —— FOMC 日程适配器，L3 日历因子需要。
- [ ] **可选：加 `.gitattributes`** —— 钉 `* text=auto eol=lf`，消除 `core.autocrlf=true` 带来的跨平台换行歧义。当前仓库内 blob 已是 LF，非阻塞。
- [ ] **可选：把 `gc.auto=0` 写进仓库配置** —— 防 `git commit` 触发 auto-gc 挂住命令。本次未复现该问题。

## Stale / Needs Verification

- [ ] Yahoo Finance 作为数据源 —— 非官方接口，实测已出现 429 限流。需评估是否换源或加兜底。
- [ ] 本环境 git 建不了 `.git/refs/` 二级子目录 —— 已实测确认并绕过（`pack-refs --all`）。**未在沙箱外复跑，环境层面的根因未查明。**

## Closed in session

- [x] `units_selfcheck` 改名 → `tools/selfcheck.py`（迁移时一并做掉）
- [x] 是否 `git init` —— 已 init，远端 `git@github.com:Skioleeya/Macro-Liquidity-High-Risk-Environment-Monitoring-System.git`，`main` = `20f9734`，已推送
