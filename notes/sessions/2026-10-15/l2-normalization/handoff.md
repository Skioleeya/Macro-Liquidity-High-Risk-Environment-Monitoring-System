```text
TASK-ID: l2-normalization
DATE: 2026-10-15
TIER: T2
STATUS: complete
CHANGE-ID: N/A:本仓库未启用 OpenSpec
```

# Handoff — L2 归一化层

## CHANGED-PATHS

新增（L0/L1 前置与契约）：
- `L0_基元层/clock.py` — 纯日期基元，**不含任何假期数据表**
- `L1_接入层/contract.py` — L1→L2 契约 `Observation` + `make_observation`
- `L1_接入层/observations.py` — payload → `Observation` 通道；`series_key` 约定的唯一实现

新增（L2 本体）：
- `L2_归一化层/contract.py` — L2→L3 契约 `Panel` / `PanelRow` / `make_panel` / `COLUMNS`
- `L2_归一化层/settings.py` — 读并校验 `normalization.toml`（共享叶子）
- `L2_归一化层/calendar.py` — 由配置规则求值 NYSE 交易日轴
- `L2_归一化层/convert.py` — 单位归一（只走 L0 `units.convert`）
- `L2_归一化层/align.py` — 投到交易日轴 + 前向填充 + 打 `fill_flag`
- `L2_归一化层/staleness.py` — 尾部滞后门禁，超限 fail-closed
- `L2_归一化层/panel_store.py` — 面板 CSV 落盘 / 读取（读回时重新校验不变量）
- `L2_归一化层/pipeline.py` — 组装入口 `build_panel` / `build_and_store`（层内编排，唯一）

新增（配置与工具）：
- `config/normalization.toml` — 填充策略、目标单位、新鲜度上限、`[pending]`、NYSE 日历规则
- `tools/checkkit.py` — 两个自检脚本共用的检查骨架（含"检查器空转"自测）
- `tools/selfcheck_l2.py` — L2 自检入口
- `tools/l2_e2e_check.py` — L2 端到端检查（需落盘数据）
- `tools/build_panel.py` — 面板构建驱动（非分层）

修改：
- `L2_归一化层/__init__.py` — 从"尚未实现"改为模块职责表 + 层内依赖规则声明
- `tools/check_layering.py` — 新增 `SHARED_MODULES` / `ORCHESTRATORS` 两类声明及其机械校验
- `tools/selfcheck.py` — 检查骨架抽到 `checkkit.py`（214 行，原 240 行）
- `notes/sessions/2026-10-15/crs100-bootstrap/artifacts/port_fidelity.py` — 修连带误报；新增 `EVOLVED_MODULES`

## VALIDATION-SUMMARY

| 命令 | 结果 |
|---|---|
| `python -m tools.check_layering` | RC=0 — 28 文件 0 违规 |
| `python -m tools.selfcheck_l2` | RC=0 — 11/11 |
| `python -m tools.selfcheck`（含联网） | RC=0 — 9/9 |
| `python -m tools.fetch_all` | RC=0 — 3/3 |
| `python -m tools.build_panel` | RC=0 — 15 序列 / 194 行 |
| `python notes/.../port_fidelity.py` | RC=0 — 625 组行为全等 |
| 变异反证（临时改坏 2 处） | RC=1 ×2，文件已逐字节还原 |

## COMMAND-EVIDENCE

`python -m tools.check_layering` → `RC=0`
```text
[PASS] 分析函数自测  —— 违规 2 条全检出 / 合规 0 误报 / 三类例外各恰好生效
扫描分层文件 28 个，跨层导入边：{'L1 -> L0': 6, 'L2 -> L1': 3, 'L2 -> L0': 6}
已声明的层内例外：{'L1': ['contract'], 'L2': ['contract', 'pipeline', 'settings']}
扫描 28 个文件，0 条违规
```

`python -m tools.selfcheck_l2` → `RC=0`，11 项全通过。其中带反证的关键项：
```text
[PASS] NYSE 日历：配置篡改必须改变结果（反证） —— 2 处配置篡改都改变了结果（配置确实被读）
[PASS] 新鲜度门禁（含反证） —— lag==limit 放行、lag>limit 拒绝、新鲜序列滞后 0、轴过短拒绝、序列不匹配拒绝
[PASS] 面板落盘往返与不变量复核（含反证） —— 往返一致；篡改 fill_flag / 表头 / 文件名 三类都报错
[PASS] 端到端：真实数据建面板（含 3 类反证） —— 15 序列 / 194 行 / 观测 97 条 / 最薄序列真实观测 4 条；三类反证全部报红
```

`python -m tools.build_panel` → `RC=0`。真实面板形状（`as_of=2026-10-15`）：
```text
fred:walcl      行= 51  真实= 10  填充= 41  单位=USD_MILLION     尾部数据日=2026-10-07
fred:rrpontsyd  行= 11  真实=  9  填充=  2  单位=USD_MILLION     尾部数据日=2026-10-14
yahoo:CL=F      行=  4  真实=  4  填充=  0  单位=USD_PER_BARREL  尾部数据日=2026-10-15
```
`fred:rrpontsyd` 10 条观测里只有 9 条真实：`2026-10-12`（哥伦布日，NYSE 开市但纽约联储休市）
FRED 返回缺失标记 `'.'`，被 `observations.from_fred` 跳过 —— 该日因此在面板上是**填充点**，
正是 `fill_flag` 要暴露的东西。

`port_fidelity.py` → `RC=0`：结构层 4 处差异全部在白名单内 + 1 个声明为"有意演化"的模块；
行为层 625 组新旧返回值全等。

变异反证（证明审计不是空转，跑完即还原，`与原文一致：True`）：
- 把 `net_liquidity` 的 `+=` 改成 `-=` → `RC=1`，结构层 + 行为层同时报红
- 把 `units.convert` 的跨族拦截去掉 → `RC=1`，421 项失败

## HARNESS-IMPROVEMENT

- 抽出 `tools/checkkit.py`：原先 `selfcheck.py` 自带一套"检查器空转自测"骨架，
  L2 自检若再写一套就有两个实现、两处腐化点。抽出后"检查器是否空转"只有一个真值。
- `check_layering.py` 的白名单从"只声明"升级为"声明 + 双向机械校验"，防止白名单腐化。
- `port_fidelity.py` 的 `EVOLVED_MODULES`：把"迁移后有意演化"与"未申报偷改"区分开，
  且声明本身也被反向校验（声明了演化却查不出集合变化即报 FAIL）。

## FAST-FAIL-CHECK

对齐/门禁/落盘全部 fail-closed，无静默降级：
- `as_of` 非交易日、序列未声明、已声明序列缺观测、观测晚于 `as_of`、时间轴非升序或末元素不是 `as_of`
  → 全部抛错
- 新鲜度超限 → 抛 `StalenessError`；**时间轴短到无法判定新鲜度也抛错**（判定不了必须失败）
- `[pending]` 是显式排除，不是静默丢弃

## NO-FALLBACK-BEHAVIOR

- 单位换算不提供"直接相减"入口；跨族由 L0 直接拒绝，L2 不捕获成"跳过"
- 禁止向后填充：序列第一条真实观测之前的轴日不产生任何行
- `panel_store.read_panel` 读回时重新过 `make_panel`，被手改坏的文件立刻报错

## NO-PATCH-BANDAGE

三处缺陷都改在正确层级，未加兼容分支：
- 跨年顺延漏检 → 改 `calendar.holidays` 的求值范围（不是给 2021-12-31 打特例）
- `panel_store` 异常类型不实 → 包成声明的类型并保留原因链（不是让调用方多 catch 一种）
- `port_fidelity` 连带误报 → 去掉 `continue` 并单独判定集合差异（不是把白名单改成"任意差异"）

## NOTES-PATHS

- `notes/sessions/2026-10-15/l2-normalization/startup.md`（本会话开工前写）
- `notes/sessions/2026-10-15/l2-normalization/project_state.md`
- `notes/sessions/2026-10-15/l2-normalization/handoff.md`（本文件）
- `notes/context/project_state.md` · `notes/context/handoff.md` · `notes/context/open_tasks.md`
- `docs/正式项目分层架构设计.md` §9

## Closed in session

- L2 归一化层七个模块 + 两端契约落地，端到端可跑（真实数据 15 序列 / 194 行）
- L0 `clock.py` 补齐（L2 的前置）
- L1 → L2 通道 `observations.py` 打通，`series_key` 约定收敛到唯一实现
- `check_layering.py` 支持并校验层内例外声明
- 修掉三处缺陷：日历跨年顺延漏检、`panel_store` 异常类型不实、`port_fidelity` 连带误报

## OPEN-RISKS

1. **取数窗口不足以支撑 L3。** 当前 `sources.toml`：FRED `default_limit=10`、Yahoo `range=5d`、
   CBOE 只留 `rows[-5:]`。面板因此最长 51 行、Yahoo 序列只有 4–5 条真实观测。
   L3 要 60D/20D Z-Score，**现有取数配置根本不够**。需要一条与"每日取最新"不同的历史回补路径，
   且回补属于 L1/重放骨架的职责 —— 本轮未做。
2. **CBOE PCR 缺日期解析。** 页面上的交易日未被解析，导致 PCR 无法进入面板（现列 `[pending]`）。
   要解除 pending 必须先补这一步，否则只能用落盘目录名冒充日期。
3. **`[pending]` 的三个键没有自动守卫。** 自检只核对"是否被交代过"，不检查 pending 条目是否长期滞留。
4. **面板 `min_real_observations = 3` 的余量很薄**（实测最薄 4 条，来自 `yahoo:CL=F` / `DX-Y.NYB`）。
   若哪天 Yahoo 只回 3 根日线，门禁就会红 —— 这是设计意图（宁可红也不要用 3 条数据算 Z-Score），
   但要预期它会红，且正确的处置是加宽取数窗口而不是下调门禁。
5. **`[pending]` 的三个键没有自动守卫**（与第 3 条同源，合并计一条）。
6. 承接上一会话的未决项（阈值口径、回测窗口、重放骨架必须先于 L3/L4）仍然未决。

已核实**不是**风险：`data/panel/` 已被 `.gitignore` 的 `data/` 覆盖
（`git check-ignore -v` → `.gitignore:2:data/`），面板不会误入版本库。
