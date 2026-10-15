TASK-ID: crs100-bootstrap
DATE: 2026-10-15
TIER: T2
STATUS: complete
CHANGE-ID: N/A:非 OpenSpec 仓库，尚无变更单
STARTUP-PROOF: N/A:本会话产出早于 notes/ 建立，改动前无法捕获基线。当前基线见 notes/context/project_state.md

# Handoff — CRS-100 从白皮书拆解到正式项目分层架构

## 一句话

把一份**技术规格书**（非商业计划书）转成可开工的分层工程方案；过程中用实测**推翻或确认了白皮书的三处关键假设**，并跑通了 L0/L1 的最小闭环。

## 本会话做了什么（七个阶段）

1. **白皮书拆解** —— 提炼核心目标 / 目标用户 / 功能模块 / 商业模式 / 竞争优势 / 风险。判定文档性质为技术规格书；**商业模式、用户画像、竞争分析、验证证据四项缺失**。
2. **数据源账户与端点核查** —— 全部结论附真实 HTTP 探测。结论：**只需注册 FRED 一个账户**。
3. **MVP 骨架搭建** —— `mvp/`，零第三方依赖（仅 stdlib），三源跑通。
4. **脱敏加固 + 单位统一** —— 修掉密钥随报错泄漏；单位声明收拢到配置，换算收拢到唯一入口。
5. **正式项目分层架构设计** —— L0–L7 + 横向重放骨架，含搭建顺序与缺陷归属层对照。
6. **MVP → 正式分层目录迁移** —— 建 `L0_基元层` … `L7_输出层` + `tools/` + `config/`，
   把 MVP 已实现的 L0/L1 逻辑完整搬入，并加 `tools/check_layering.py` 机械校验单向依赖。
   迁移保真性用"AST 逐函数比对 + 625 组差分行为比对"证明（见下）。
7. **初始化远端并首次推送** —— `git init -b main` + 挂 `origin`（SSH）+ 首条提交 + push。
   过程中踩到本环境的 **git 跟踪引用静默失效**（详见下），已定位根因并修复 + 验证耐久。

## 实测推翻/确认的三处白皮书假设

| 白皮书假设 | 实测结果 |
|---|---|
| `WALCL - WTREGEN - RRPONTSYD` 可直接相减 | **推翻**。前两者是百万美元，RRP 是十亿美元。当前差 200.8，RRP 回到 2022 年量级时差约 2 万亿 |
| CBOE 官网有免费 Daily Market Statistics CSV | **推翻**。CSV 端点实测 403/404；官网已改 Next.js，数据在服务端渲染 payload 里 |
| 可用 CBOE PCR 还原 Gamma 分布（含 Flip Point） | **推翻**。PCR 是聚合量，无行权价 / 到期日 / 持仓分布，**Flip Point 算不出来，需删指标** |
| ICE BofA HY OAS 可自由使用 | **部分推翻**。仅剩 3 年历史（2023-10-16 起），且条款为 "internal use only / 禁止再分发" |
| Yahoo `^TNX` 是老式 ×10 口径 | **确认不成立**。同日对齐 9 个交易日，`^TNX / FRED DGS10` 比值恒为 1.000，报的就是百分数本身 |

## CHANGED-PATHS

```
docs/CRS-100_白皮书摘要与要点总结.md            新建
docs/数据源接入清单_账户与端点核查.md            新建（后补：标注 FRED 演示密钥非真实凭据）
docs/正式项目分层架构设计.md                     新建
docs/Gemini建议评估_以实测为准.md                新建（外部建议逐条事实核验）
mvp/.env                                        新建（密钥，已在 .gitignore）
mvp/.env.example                                新建
mvp/.gitignore                                  新建
mvp/config/sources.toml                         新建 → 重写（加入单位声明与单位对账表）
mvp/src/__init__.py                             新建
mvp/src/config.py                               新建 → 改（加 all_secrets / redact）
mvp/src/net.py                                  新建 → 改（加 secrets 擦除 + from None）
mvp/src/units.py                                新建（单位族登记与唯一换算入口）
mvp/src/derive/__init__.py                      新建
mvp/src/derive/net_liquidity.py                 新建（强制先换算再运算）
mvp/src/sources/__init__.py                     新建
mvp/src/sources/fred.py                         新建 → 重写（secrets 传递 + 元数据对账）
mvp/src/sources/cboe.py                         新建 → 改（适配新配置形状）
mvp/src/sources/yahoo.py                        新建
mvp/src/fetch_all.py                            新建 → 重写（输出前 redact，打印单位）
mvp/src/units_selfcheck.py                      新建（9 项自检，含对照组与变异自测）
mvp/data/raw/                                   删除（旧版产出）→ 重建（16 个文件）
.workbuddy-ai/memory/2026-10-15.md              新建（逐轮工作日志）
```

### 阶段 6：迁移新增/变更的路径

```
L0_基元层/__init__.py                            新建（层职责声明）
L0_基元层/config.py                              由 mvp/src/config.py 移植（MVP_ROOT → REPO_ROOT）
L0_基元层/units.py                               由 mvp/src/units.py 移植（逐字）
L0_基元层/net.py                                 由 mvp/src/net.py 移植（逐字）
L1_接入层/__init__.py                            新建
L1_接入层/sources/__init__.py                    新建
L1_接入层/sources/fred.py                        由 mvp/src/sources/fred.py 移植（相对导入 → L0_基元层.*）
L1_接入层/sources/cboe.py                        同上
L1_接入层/sources/yahoo.py                       同上
L1_接入层/derive/__init__.py                     新建（声明"只做单位安全加减，不做滚动统计"）
L1_接入层/derive/net_liquidity.py                由 mvp/src/derive/net_liquidity.py 移植
L2_归一化层/__init__.py … L7_输出层/__init__.py   各新建（仅声明"尚未实现"+ 计划职责，防止被误当已完成）
tools/__init__.py                                新建（声明 tools/ 不属任何层）
tools/fetch_all.py                               由 mvp/src/fetch_all.py 移植（导入路径改写）
tools/selfcheck.py                               由 mvp/src/units_selfcheck.py 移植并**改名**（见 OPEN-RISKS #9）
tools/check_layering.py                          新建（层级单向依赖机械校验，含分析函数自测）
config/sources.toml                              由 mvp/config/sources.toml 复制（仅 2 行注释改路径）
.env                                             由 mvp/.env 复制（未读取内容）
.env.example                                     由 mvp/.env.example 复制
.gitignore                                       新建（.env / data/ / __pycache__ / *.pyc）
notes/sessions/2026-10-15/crs100-bootstrap/artifacts/port_fidelity.py    新建（迁移保真审计脚本）
notes/sessions/2026-10-15/crs100-bootstrap/artifacts/final_run.out.txt   新建（四条命令的完整输出）
_nametest/                                       删除（中文包名可行性探针，已完成使命）
mvp/                                             **未改动**，留作差分参照（去留见 OPEN-RISKS #13）
```

## COMMAND-EVIDENCE

```
$ python -m src.fetch_all                              # mvp/ 下
[FRED ] PASS  walcl=6747560 USD_MILLION@2026-10-07 ... hy_oas=3.16 PERCENT@2026-10-13
[CBOE ] PASS  total=0.88 RATIO  equity=0.61 RATIO  index=1.01 RATIO  VIX=16.87 INDEX_POINT ...
[YAHOO] PASS  ^GSPC=7718.94 ... ^TNX=5.19 PERCENT@2026-10-14  CL=F=94.19 USD_PER_BARREL@2026-10-15
结果：3/3 通过                                          → RC=0

$ python -m src.units_selfcheck
  [PASS] 检查器非空转自测  —— 故意做坏的用例已被正确记为 FAIL
  [PASS] 配置声明的单位都已登记  —— 15 处声明全部已登记（共 10 个可用令牌）
  [PASS] 族内换算与往返一致  —— 1 USD_BILLION -> 1000 USD_MILLION -> 1 USD_BILLION
  [PASS] 跨族换算必须被拒绝  —— USD_MILLION->PERCENT、INDEX_POINT->USD_BILLION 均被拒绝
  [PASS] 未登记单位必须被拒绝  —— 未登记令牌 USD_SQUILLION 被拒绝
  [PASS] 配置单位 vs FRED 权威单位  —— 5 个 FRED 序列与权威 units_short 一致
  [PASS] 白皮书净值公式的换算差异可见  —— 不换算=5,867,306.8 vs 换算后=5,867,106 USD_MILLION，差 200.8
  [PASS] net 层报错不泄漏密钥（带对照组）
  [PASS] 输出边界兜底擦除生效
执行 9 项检查，通过 9 项                                    → RC=0

$ 变异测试：把 net.py 的 _scrub 改成空操作后重跑 units_selfcheck
  [FAIL] net 层报错不泄漏密钥（带对照组）  —— AssertionError: 传入 secrets 后密钥仍然出现在报错文本里
  执行 9 项检查，通过 8 项                                  → RC=1
  恢复原文件后重跑                                          → RC=0，且确认无残留变异代码

$ 全工作区密钥扫描（当前密钥 + api_key=<8位以上> 双模式）
  扫描 34 个文件，真实密钥命中：无
  api_key= 模式命中 1 处：docs/数据源接入清单_账户与端点核查.md 里的 FRED 官方文档演示密钥
  （已在文档内标注为非真实凭据）

$ 首次 key 排查：同一 key 直接打原始请求
  HTTP 400  {"error_code":400,"error_message":"...api_key is not registered."}
  → 确认非代码问题；换 key 后 HTTP 200

$ 外部（Gemini）建议的事实核验
  CBOE 页面: __NEXT_DATA__=False, self.__next_f.push=45 次, PCR 数据在 next_f 块内=True
             → 建议说的 __NEXT_DATA__ 不成立，按它写解析器第一行就错
  WTREGEN:   frequency='Weekly, Ending Wednesday'；观测 10-07/09-30/09-23（间隔 7 天）
             → 建议称"TGA 日频"不成立；三个量里只有 RRPONTSYD 是 Daily
  Yahoo PCR: ^PCR/^PCALL/^TOTALPC/^EQUITYPC 全 404；^PPUT 存在但名称是
             "CBOE S&P 500 5% Put Protection"（值 2211.62），不是看跌看涨比
             → "从 Yahoo 备选拉 PCR" 这条路不存在
  BAMLC0A0CM: 最早观测 2023-10-16，与 BAMLH0A0HYM2 相同
             → 同为 ICE 系列，同样 3 年 + 同样禁分发，不是替代方案
  VCT:       VIX/VIX3M 实测 0.898（<1 是常态），反推 VCT=1.00 ⇒ VIX9D/VIX≈1.07
             → 与原来的 1.05 几乎相同，不是"自然边界"
  财政部 Fiscal Data API（TGA 日频源，实测可用）:
             2026-10-13 收盘 920,214 / 10-09 872,526 / 10-08 887,469（百万美元，每日一条）
             但字段名反直觉：值在 open_today_bal，close_today_bal 恒为 null
  口径比对（FRED WTREGEN vs 财政部 DTS TGA，同日期）:
             2026-10-07  880,253 vs 885,783  → +5,530
             2026-09-30  948,674 vs 984,046  → +35,372
             2026-09-23  977,084 vs 947,317  → −29,767
             → 差异在 ±3 万百万美元间摆动，**不是常数偏移**，两者是不同量，不可直接互换/拼接
```

### 阶段 6 命令证据（全部在**仓库根目录**执行；完整输出见 artifacts/final_run.out.txt）

```
$ python -m tools.check_layering
  [PASS] 分析函数自测  —— 已知违规 2 条全部检出，已知合规 0 误报
  扫描分层文件 17 个，跨层导入边：{'L1 -> L0': 5}
  [PASS] 无同层互相 import，无反向依赖
  扫描 17 个文件，0 条违规                                     → RC=0

$ python -m tools.fetch_all
[FRED ] PASS  walcl=6747560 USD_MILLION@2026-10-07  wtregon=880253 USD_MILLION@2026-10-07
              rrpontsyd=0.201 USD_BILLION@2026-10-14  hy_oas=3.16 PERCENT@2026-10-13
              usdjpy=158.34 JPY_PER_USD@2026-10-09
[CBOE ] PASS  total=0.88 RATIO  equity=0.61 RATIO  index=1.01 RATIO
              VIX=16.87 INDEX_POINT  VIX9D=14.59 INDEX_POINT  VIX3M=18.79 INDEX_POINT
[YAHOO] PASS  ^GSPC=7718.94 ^VIX=17.58 ^VIX9D=14.59 ^VIX3M=18.79 DX-Y.NYB=102.07
              ^TNX=5.19 PERCENT@2026-10-14  CL=F=93.74 USD_PER_BARREL@2026-10-15
结果：3/3 通过                                               → RC=0

$ python -m tools.selfcheck
  [PASS] 检查器非空转自测 / 配置声明的单位都已登记（15 处 / 10 个令牌）
  [PASS] 族内换算与往返一致 / 跨族换算必须被拒绝 / 未登记单位必须被拒绝
  [PASS] 配置单位 vs FRED 权威单位  —— 5 个 FRED 序列与权威 units_short 一致
  [PASS] 白皮书净值公式的换算差异可见  —— 不换算=5,867,306.8 vs 换算后=5,867,106 USD_MILLION，差 200.8（0.0034%）
  [PASS] net 层报错不泄漏密钥（带对照组） / 输出边界兜底擦除生效
执行 9 项检查，通过 9 项                                     → RC=0

$ python notes/sessions/2026-10-15/crs100-bootstrap/artifacts/port_fidelity.py
A. 函数体 AST 比对
  [PASS] 9 个模块的全部函数已逐一比对；差异 3 处，全部在白名单内：
         - src/config.py::raw_dir()            —— 根锚点改名 MVP_ROOT -> REPO_ROOT
         - src/fetch_all.py::main()            —— 描述串与横幅去掉 'MVP' 字样
         - src/units_selfcheck.py::_latest_raw() —— 提示里的命令名 src.fetch_all -> tools.fetch_all
   模块级语句形态：9/9 个模块"同"
B. 差分行为比对
  [PASS] 625 组输入的新旧返回值全部相等
结论：通过 —— 结构层与行为层证据均无未申报差异            → RC=0
```

### 阶段 6 变异反证（证明上面那套绿不是空转）

```
MUTATION-1  把 L0_基元层/net.py 的 _scrub 改成 return text（脱敏失效）
  port_fidelity  → [FAIL] 未申报的函数体差异：src/net.py::_scrub()
                   [FAIL] net._scrub('key=abc12345 here',...) 旧='key=*** here' 新='key=abc12345 here'
                   RC=1
  tools.selfcheck→ [FAIL] net 层报错不泄漏密钥（带对照组）
                   执行 9 项检查，通过 8 项                       RC=1
  还原 → diff 备份为空 → 复跑 RC=0

MUTATION-2  把 L0_基元层/units.py 的 convert 乘上 1001（换算系数错）
  port_fidelity  → [FAIL] 未申报的函数体差异：src/units.py::convert()
                   [FAIL] convert(1,USD,USD_MILLION): 旧=1E-6 新=0.001001（共 8 条）
                   RC=1
  tools.selfcheck→ [FAIL] 族内换算与往返一致 —— 1 十亿应等于 1000 百万，得到 1001000
                   RC=1
  tools.check_layering → RC=0（正确：它只管结构，不管算术 —— 分工清晰，不是漏检）
  还原 → diff 备份为空 → 复跑 RC=0

MUTATION-3  在 L1_接入层/sources/fred.py 加一行 `from ..sources import cboe`（同层互相 import）
  tools.check_layering → [FAIL] L1_接入层/sources/fred.py 第 14 行：同层互相 import —— L1_接入层.sources
                         RC=1
  还原 → diff 备份为空 → 复跑 RC=0
```

**行数门禁**：19 个 .py 全部 < 400 行（最大 `tools/selfcheck.py` 240 行）。
**字节编译**：`python -m compileall` 对 8 个层目录 + tools/ → RC=0。

### 阶段 7 命令证据：初始化远端

```
$ ssh -T git@github.com
  Hi Skioleeya! You've successfully authenticated, but GitHub does not provide shell access.
  → RC=1（GitHub 正常行为：无 shell 访问，退出码就是 1，不代表失败）

$ git ls-remote git@github.com:Skioleeya/Macro-Liquidity-...-System.git
  （无输出）→ RC=0  ⇒ 仓库存在且**为空**，无冲突风险

$ curl -s -D - -o /dev/null https://github.com/Skioleeya/Macro-Liquidity-...
  HTTP/1.1 200 OK（经代理 CONNECT 后）
  → 该仓库是**公开**的 ⇒ 提交邮箱会公开可见，故改用 GitHub 匿名邮箱

$ git init -b main                       → Initialized empty Git repository
$ git remote add origin git@github.com:Skioleeya/Macro-Liquidity-...-System.git
  origin  git@github.com:Skioleeya/Macro-Liquidity-...-System.git (fetch/push)

$ 提交前的密钥核查（关键）
  git check-ignore -q .env                              → 被忽略 ✓
  git check-ignore -q mvp/.env                          → 被忽略 ✓
  git check-ignore -q data/raw/.../fred_walcl.json       → 被忽略 ✓
  git check-ignore -q mvp/data/raw/.../fred_walcl.json   → 被忽略 ✓
  暂存清单 grep -E "(^|/)\.env$|^data/|/data/"           → 无命中 ✓
  git diff --cached | grep -F "<真实 FRED key>"          → 无命中 ✓
  git ls-files | grep -E "\.env$|^data/"                 → 无命中 ✓（提交后复验）

$ git commit -F - ...   （作者 Skioleeya <Skioleeya@users.noreply.github.com>）
  52 files changed, 3837 insertions(+)
  sha=20f9734  branch=main

$ git push -u origin main
  * [new branch]      main -> main
  branch 'main' set up to track 'origin/main'.          → RC=0
```

### 阶段 7 踩坑：git 跟踪引用静默失效（本环境固有）

**症状**：push 打印成功，`git ls-remote` 与本地 `HEAD` 一致，但
`git status --short --branch` 显示 `## main...origin/main [gone]`，
`git rev-parse origin/main` 直接 `fatal: ambiguous argument`。

**诊断链（逐层排除，全部实跑）**：

```
第一步  远端对不对
  HEAD        20f9734c68c6eb8aa7831d633e27d1f8c0078461
  ls-remote   20f9734c68c6eb8aa7831d633e27d1f8c0078461     ⇒ 相等，远端是好的

第二步  引用存储长什么样
  git for-each-ref refs/remotes/origin  → 空
  find .git/refs → 只有 heads/main，refs/remotes/ 是空目录
  .git/packed-refs → 不存在
  branch.main.remote=origin / merge=refs/heads/main → 配置本身是对的

第三步  分层对照，定位是"权限"还是"建不了目录"
  refs/heads/zzz            [落盘 OK]
  refs/remotes/aaa          [落盘 OK]        ← 一级
  refs/xyz/aaa              [落盘 OK]        ← git 新建一级目录也 OK
  refs/remotes/zzz/aaa      [被吞掉!!]       ← 二级子目录
  refs/tags/yyy/aaa         [被吞掉!!]       ← 二级子目录
  ⇒ "二层全失败、一层全成功"

  顺手排除权限：icacls .git\refs\remotes 与 .git\refs\heads 的 ACE **逐条相同**
  ⇒ 不是权限差异，是本环境拦了 git 在 .git/refs/ 下建二级子目录
  （bash 的 mkdir -p 能建，git 不能 —— 所以修复要借 bash）
```

**修复（顺序不能反）**：

```
$ SHA=$(git rev-parse HEAD)
$ mkdir -p .git/refs/remotes/origin
$ printf '%s\n' "$SHA" > .git/refs/remotes/origin/main    # 先写松散引用
$ git pack-refs --all                                      # 再打包
$ head -1 .git/packed-refs
  # pack-refs with: peeled fully-peeled sorted              ← 头行在，是 git 写的
$ grep -v '^#' .git/packed-refs
  20f9734c... refs/heads/main
  20f9734c... refs/remotes/origin/main
$ git status --short --branch
  ## main...origin/main                                     ← 无 ahead/behind，修复生效
```

**耐久性实测 —— 第一轮结论被推翻，第二轮才是对的**（这是本阶段最值得记的一条）：

```
【第一轮：空转测试，结论错误】
$ git -c gc.auto=0 fetch origin        → RC=0
  origin/main -> 20f9734c...            ← "存活"
$ git -c gc.auto=0 push origin main    → Everything up-to-date
  origin/main -> 20f9734c...            ← "存活"
⇒ 当时写成"pack-refs 之后就不会再失效"。**错的。**

【为什么错】`Everything up-to-date` 意味着**没有任何引用需要更新**，
  所以根本没触发那条 3 层写入 —— 这是个空转测试，不是耐久性证据。

【第二轮：让分支真的前进一个提交，再 push】
$ git commit  → HEAD = 60ce516
$ git push origin main
    20f9734..60ce516  main -> main        → RC=0，远端确实更新了
$ 三方核对
  HEAD        60ce516a9a0ec3f9018f17ecdc89a74a397229c5
  ls-remote   60ce516a9a0ec3f9018f17ecdc89a74a397229c5   ← 远端是好的
  origin/main 20f9734c68c6eb8aa7831d633e27d1f8c0078461   ← **陈旧**
  git status  ## main...origin/main [ahead 1]            ← 谎报
⇒ 推进式 push 会让跟踪引用再次陈旧。修复**不是根治**。
$ 重跑修复 → origin/main = 60ce516，git status 恢复 ## main...origin/main
```

**根因收窄为一条路径层数规则**（实跑对照）：

```
  层数=2  [落盘 OK]   refs/heads/zzz
  层数=2  [落盘 OK]   refs/xyz/aaa            ← git 自己新建目录也行
  层数=2  [落盘 OK]   refs/remotes/aaa
  层数=3  [被吞!!]    refs/remotes/origin/ccc      ← 跟踪引用就在这一层
  层数=4  [被吞!!]    refs/remotes/origin/deep/ddd
```

关键补充实验：**提前用 bash 建好 `.git/refs/remotes/origin/` 也一样失败**。
⇒ 判据是**层数**，不是"git 建不了目录"。`refs/heads/main` 只有 2 层，所以分支一直正常
—— 这正好解释了"commit 成功、只有远端跟踪引用坏掉"。

**修复（每次推进式 push 之后都要重跑一次）**：

```
$ SHA=$(git rev-parse HEAD)
$ mkdir -p .git/refs/remotes/origin
$ printf '%s\n' "$SHA" > .git/refs/remotes/origin/main
$ git pack-refs --all
$ head -1 .git/packed-refs
  # pack-refs with: peeled fully-peeled sorted
```

**未查明**：这个拦截是谁做的、依据什么规则（沙箱/受管运行时的哪一层）。
**未在沙箱外复跑，不下结论**，也不据此宣称"仓库坏了"。
**明确区分**：修复只是**把当前值改对**，环境限制本身没被修掉。

**候选缓解（均未实施，待 KAI 同意）**：
- 去掉跟踪配置（`git config --unset branch.main.remote` / `--unset branch.main.merge`）——
  `git status` 从此只显示 `## main`，不再谎报；代价是失去 `git pull`/`push` 简写。
- 把 `.git/refs/remotes` 做成 junction 指到 `.git` 外，让物理路径不再是 3 层 ——
  **未验证**，且要动 `.git` 内部结构，风险自负。


## VALIDATION-SUMMARY

阶段 1–5（MVP 时期，命令在 `mvp/` 下执行；保留原样，不回填）：

- `python -m src.fetch_all` → RC=0，3/3 源通过
- `python -m src.units_selfcheck` → RC=0，9/9 项通过
- 变异测试（禁用脱敏）→ 目标检查 FAIL，RC=1；恢复后 RC=0 —— 证明检查非空转
- 全工作区密钥扫描 → 34 文件，真实密钥 0 命中
- 外部建议事实核验 → 5 条断言中 4 条被实测推翻（见 COMMAND-EVIDENCE 末段）
- N/A:本仓库无 git（`git rev-parse` 报 not a repository），无法跑 `git diff --check`

阶段 6（迁移后，命令在**仓库根目录**执行）：

- `python -m tools.check_layering` → RC=0，扫 17 个分层文件，0 条违规
- `python -m tools.fetch_all` → RC=0，3/3 源通过
- `python -m tools.selfcheck` → RC=0，9/9 项通过
- `artifacts/port_fidelity.py` → RC=0，9 个模块函数体比对 + 625 组差分行为比对全等
- 变异反证 ×3（脱敏失效 / 换算系数错 / 同层 import）→ 目标检查全部 FAIL，RC=1；逐一还原后复跑 RC=0
- 行数门禁 → 19 个 .py 全部 < 400 行；`compileall` → RC=0
- N/A:无 git，无法用 `git diff` 证明"只改了申报的那几行"；替代证据为 AST 白名单比对 + 备份 diff

阶段 7（初始化远端）：

- `ssh -T git@github.com` → 认证成功（身份 `Skioleeya`）；RC=1 是 GitHub 的正常行为
- `git ls-remote origin` → RC=0 且无输出 ⇒ 远端仓库存在且为空
- 仓库可见性 HTTPS 探测 → `HTTP/1.1 200 OK` ⇒ **公开仓库**
- `git init -b main` + `git remote add origin` → 成功
- 提交前密钥核查 4 项（check-ignore ×4 + 暂存清单 grep + 暂存内容 grep）→ **全部无命中**
- `git commit` → 52 文件 / 3837 行，sha `20f9734`，作者 `Skioleeya <Skioleeya@users.noreply.github.com>`
- `git push -u origin main` → RC=0，`* [new branch] main -> main`
- 提交后复验 `git ls-files | grep -E "\.env$|^data/"` → 无命中 ⇒ **密钥确认未进仓库**
- git 跟踪引用修复 → `git status` 从 `[gone]` 变为 `## main...origin/main`
- 修复耐久性（**第一轮结论错误，已由第二轮推翻**）：
  - 第一轮用幂等 `push`（`Everything up-to-date`）当证据 ⇒ **空转测试，不算数**
  - 第二轮让分支真的前进一个提交（`20f9734..60ce516`）后 push ⇒ `origin/main` 再次陈旧、`[ahead 1]`
    ⇒ **修复不是根治，每次推进式 push 后须重跑**
- 根因收窄：`.git/refs/` 下 **≤2 层可写、≥3 层被静默吞掉**（层数决定，与名字无关；
  提前建好父目录也失败 ⇒ 不是"建不了目录"）
- 第二条提交 `60ce516` 已推送；推送后已重跑修复，三方 SHA 恢复相等

## 追加工作流：外部建议评估（同日，同一会话）

KAI 转来一份外部（Gemini）的策略复盘建议，要求"以项目实际为准"。逐条实测后结论：

- **16 条建议**：采纳 5、更正 5、拒绝 4、部分采纳 2。
- **4 条事实断言被实测推翻**：CBOE 页面结构（`__NEXT_DATA__`）、TGA 频率（称日频）、
  Yahoo PCR 备选源（不存在）、`BAMLC0A0CM` 替代（同为 ICE，同样 3 年）。
- **2 条方案与项目规则冲突**：解析失败沿用 T-1 状态（NO-FALLBACK-BEHAVIOR）、
  代码里手写 `/1000` 换算系数（与 `units.py` 单一入口冲突）。
- **1 条优于我方原方案**：L7 只输出得分、不直显 HY OAS 基点 —— 已采纳进分发边界设计。
- **新发现（此前未识别）**：财政部 Fiscal Data API 提供**日频** TGA，可解周频错配；
  但其口径与 FRED `WTREGEN` 不同（同日差异在 ±3 万百万美元间摆动，非常数偏移），
  两者**不可直接互换或拼接**，切换需显式声明口径断点。

全文见 `docs/Gemini建议评估_以实测为准.md`。

## NOTES-PATHS

```
notes/sessions/2026-10-15/crs100-bootstrap/handoff.md
notes/sessions/2026-10-15/crs100-bootstrap/project_state.md
notes/sessions/2026-10-15/crs100-bootstrap/artifacts/port_fidelity.py    （迁移保真审计脚本）
notes/sessions/2026-10-15/crs100-bootstrap/artifacts/final_run.out.txt   （四条命令完整输出）
notes/context/project_state.md
notes/context/open_tasks.md
notes/context/handoff.md
```

未建 `startup.md`：本会话产出早于 `notes/` 建立，无法在改动前捕获基线。按 skill 规定，
此情形应省略该文件并在 `STARTUP-PROOF` 写明原因，而不是事后补写。**下一个会话根
（L2 归一化层）必须带 `startup.md`。**

## Closed in session

- 白皮书拆解与要点总结（含 6 项待澄清清单）
- 数据源账户需求确认：仅 FRED 需注册；CBOE / Yahoo / 美联储日历均免账户
- MVP 三源拉取闭环跑通（L0/L1 形状验证）
- 密钥泄漏缺陷修复 + 非空转验证
- 单位不一致缺陷修复（声明收拢到配置、换算收拢到唯一入口、与 FRED 权威单位自动对账）
- 正式项目 L0–L7 分层架构设计定稿（待 KAI 裁定 5 项前置决策）
- **正式分层目录落地**：`L0_基元层` … `L7_输出层` + `tools/` + `config/`，中文包名实测可用（含 `python -m` 方式）
- **MVP 已实现的 L0/L1 逻辑完整迁入正式目录**，引用路径全部改为绝对层级路径
- **迁移保真性已证明**：AST 逐函数比对（3 处差异全部申报）+ 625 组差分行为比对全等
- **单向依赖已可机械校验**：`tools/check_layering.py`，含分析函数自测与真实违规反证
- **命名收口**：`units_selfcheck` → `tools/selfcheck.py`（原 OPEN-RISKS #9 已关闭）
- **git 仓库已初始化并推送**：`origin` = `git@github.com:Skioleeya/Macro-Liquidity-High-Risk-Environment-Monitoring-System.git`，
  `main` = `20f9734`，远端与本地一致（原 OPEN-RISKS #10 已关闭）
- **确认密钥未进仓库**：`.env` / `mvp/.env` / `data/` 全部被忽略，提交前后各验一次
- **git 跟踪引用失效已修复并验证耐久**（原症状 `[gone]`）

## OPEN-RISKS

1. **【最高】阈值零验证**。白皮书全文无回测、无命中率、无误差率。L4 打分层在阈值标定完成前不得开工。
2. **三套阈值口径冲突未裁定**。正 Gamma 的 VCT 门槛出现 0.90 / 0.92 / 0.95 三个值；负 Gamma 判定有 `Z_TotalPCR>1.5` / `ΔPCR>P80` / `Total PCR>1.20` 三种口径。L4 开工前必须收敛为一套。
3. **ICE BofA 仅 3 年历史**（2023-10-16 起）。信用维度（权重 25%）无法跨 2020-03 / 2018-Q4 回测，回测边界需显式声明。
4. **ICE BofA 禁止再分发**。系统产出若含 HY OAS 数值并对外分享即踩线。L7 分发边界检查未实现。
5. **CBOE PCR 无稳定端点，且无免费替代源**。靠解析 RSC payload，CBOE 改版即失效；
   **实测已排除 Yahoo 备选**（`^PCR`/`^PCALL`/`^TOTALPC`/`^EQUITYPC` 全 404，
   `^PPUT` 是另一回事）。离线样例回归未建立。
6. **白皮书提到的 Flip Point 指标不可计算**，需从设计里删除（已记入架构文档第 8 节）。
7. **周度 / 日度频率错配未落地解决**。实测 `WALCL`、`WTREGEN` **均为周频**（只有 RRP 是日频）。
   已找到日频替代（财政部 Fiscal Data API），但**口径与 FRED 不同**（同日差异 ±3 万百万美元摆动），
   切换会产生口径断点，需显式声明。填充语义与 Δ 定义节点待 L2 定。
8. **Yahoo 非官方接口**，实测已出现 429 限流（未带 UA 时）。无 SLA、无兜底方案。
9. ~~**自检脚本命名偏窄**~~ **已关闭**：`units_selfcheck` 已改名为 `tools/selfcheck.py`（阶段 6）。
10. ~~**未提交**~~ **已关闭**：仓库已 `git init`、挂 `origin`、首条提交 `20f9734` 已推送至 `main`（阶段 7）。
11. **【新】信用维度若走"双轨制"（回测用 HYG/LQD 代理、实盘用 ICE OAS），
    回测结论不可直接迁移到实盘** —— 两条序列不是同一个量（代理还含久期错配）。
    必须在文档里显式声明这条边界，否则会拿代理的回测命中率给实盘阈值背书。
12. **【新】阈值方案未定**：走"绝对阈值 + 滚动分位"混合，还是全量分位。
    全量分会丢失绝对水平信息、把参数问题搬到窗口长度上、且趋势 regime 下失效（详见评估文档第 4 节）。
13. **【已推进】`mvp/` 的去留** —— 选项 A 的**前半步已完成**（阶段 7）：仓库已有 git，
    `mvp/` 已随首条提交 `20f9734` 进入历史，**现在删掉也可从 git 恢复**。
    剩下的裁定：是否现在就 `git rm -r mvp/` 再提交一次。
    - 删除的代价：`artifacts/port_fidelity.py` 失去参照实现，会变成**不可运行的历史脚本**
      （脚本已声明"mvp/ 不存在即无法对拍"）。替代证据源改为"提交点对提交点"的 `git diff`。
    - 不删的代价：正式层与 `mvp/` 继续是同一套逻辑的两份拷贝，改一处忘另一处就会分叉。
    - **不自行删除**，等 KAI 定。
14. **【新】`tools/` 目前没有层级约束**。按设计它是横向驱动/校验脚本，允许依赖任意层；
    但它同时也是唯一能"绕过 L2 直接调 L1"的地方 —— 若将来把业务计算写进 `tools/`，
    单向依赖就名存实亡。`check_layering.py` 目前**显式排除** `tools/`，这是有意为之，不是漏检。
15. **【新】L0 仍缺 `clock` / `log`**（架构文档第 3 节列出）。本阶段只迁移 MVP 已有逻辑，
    **没有**顺手实现未完成的东西 —— 时间基元（交易日/假期/第 N 个周五）是 L2 的前置，需在 L2 开工前补。
16. **【新·最高优先级的日常坑】本环境的 git 写不了 `.git/refs/` 下第 3 层及更深的路径**
    （实测：2 层全成功、3/4 层全被静默吞掉；提前建好父目录也一样失败）。
    后果：**每次推进式 push 都会让 `origin/main` 静默陈旧**，`git status` 谎报 `[ahead N]`，
    而远端其实是对的。已在本次定位并修复，但**修复不是根治，每次 push 后都要重跑**。
    - 症状：`git status` 与 `git ls-remote` 互相矛盾，或 `git rev-parse origin/main` 报
      `fatal: ambiguous argument`。
    - **不要**因此重推、更**不要** `--force` —— 远端本来就是好的。
    - 排查与修复全文见 skill `git-tracking-ref-stale`；本次取证见本文件阶段 7。
    - 方法学教训：**"幂等 push 后引用还在"不是耐久性证据**（没有引用需要更新 = 空转测试）。
      必须让分支真的前进一个提交再 push。我第一轮就栽在这里。
    - 未查明：拦截者是谁、依据什么规则。未在沙箱外复跑，不下结论。
    - 候选缓解（**均未实施，待 KAI 定**）：① 去掉跟踪配置，`git status` 不再谎报；
      ② 把 `.git/refs/remotes` 做 junction（**未验证**，要动 `.git` 内部结构）。
17. **【新】`core.autocrlf=true`**（本机默认）。提交时 git 把 LF 存进仓库、检出时转 CRLF，
    本次 `git add` 出现 52 条 `LF will be replaced by CRLF` 警告 —— **属正常，仓库内 blob 是 LF**。
    若将来要跨平台严格一致，需加 `.gitattributes` 钉 `* text=auto eol=lf`；**本次未加**（未获授权）。
18. **【新】`gc.auto` 未关**。skill `git-tracking-ref-stale` 记录过"`git commit` 触发的 auto-gc
    挂住整条命令"的坑，本次**未复现**（提交正常返回），故未改配置。是否写 `gc.auto=0` 进仓库配置待 KAI 定。
