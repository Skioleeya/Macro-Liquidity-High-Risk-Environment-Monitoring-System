"""迁移保真审计：MVP（参照实现） vs 正式分层（移植实现）。

三层证据，缺一层就不能下"保真"结论：

  A. 函数体 AST 逐函数比对 —— 证明函数**结构**没被改过（除白名单内声明的差异）。
     用 AST 而不是文本 diff：文件路径/注释/行序变化不应算作行为变化，
     而函数体内部任何一处逻辑改动都必须现形。
  B. 差分行为比对 —— 同一批输入喂给新旧两个实现，返回值逐一 `==` 比较。
     只比**公开函数的返回值**，不比内部状态、不比打印文本。
  C. 声明式差异清单 —— A 里检出的每一处差异必须落在白名单内，否则 FAIL。
     白名单外出现任何差异 = 迁移引入了未申报的改动。

本脚本**不能**证明的东西（明说，避免过度外推）：
  - 不能证明 L2–L7 的行为 —— 那些层还没实现，没有可比的参照。
  - 不能证明网络层的等价性：`fred.fetch_series` / `cboe.fetch_daily_ratios` 依赖
    外部响应，本脚本只比对**解析函数**在固定输入下的输出。
  - 不能证明"新实现是对的" —— 只证明"新旧一致"。若参照实现本身有错，两边一起错。

用法：任意目录下 `python port_fidelity.py`，退出码非 0 即有未通过的证据层。
"""

from __future__ import annotations

import ast
import json
import sys
from decimal import Decimal
from pathlib import Path

# artifacts -> crs100-bootstrap -> 2026-10-15 -> sessions -> notes -> <repo root>
ROOT = Path(__file__).resolve().parents[5]
MVP = ROOT / "mvp"

for entry in (str(ROOT), str(MVP)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

# --- 被比对的模块对：(参照实现相对 mvp/ 的路径, 移植实现相对仓库根的路径) ---
PAIRS: list[tuple[str, str]] = [
    ("src/config.py", "L0_基元层/config.py"),
    ("src/units.py", "L0_基元层/units.py"),
    ("src/net.py", "L0_基元层/net.py"),
    ("src/sources/fred.py", "L1_接入层/sources/fred.py"),
    ("src/sources/cboe.py", "L1_接入层/sources/cboe.py"),
    ("src/sources/yahoo.py", "L1_接入层/sources/yahoo.py"),
    ("src/derive/net_liquidity.py", "L1_接入层/derive/net_liquidity.py"),
    ("src/fetch_all.py", "tools/fetch_all.py"),
    ("src/units_selfcheck.py", "tools/selfcheck.py"),
]

# 白名单：只允许这三处函数体差异，且每处都必须给出理由。
ALLOWED_FUNC_DIFFS: dict[tuple[str, str], str] = {
    ("src/config.py", "raw_dir"): "根锚点改名 MVP_ROOT -> REPO_ROOT（新目录深度恰好仍是上两级）",
    ("src/fetch_all.py", "main"): "面向用户的描述串与横幅去掉 'MVP' 字样",
    ("src/units_selfcheck.py", "_latest_raw"): "错误提示里的命令名 src.fetch_all -> tools.fetch_all",
    ("src/units_selfcheck.py", "main"): (
        "会话 2026-10-15/l2-normalization：末尾的打印/退出码改为委托 CheckKit.report()，"
        "检查项本身与执行顺序未变（实测仍 9/9 通过）"
    ),
}

# 迁移之后**有意**发生演化的模块（每处必须给出理由与出处）。
#
# 声明为演化的模块：函数**集合**允许变化（增删函数）；但同名函数仍逐一比对，
# 差异仍必须落在 ALLOWED_FUNC_DIFFS 里 —— 演化只放宽"增删"，不放宽"偷改"。
# 反向也校验：声明了演化却查不出集合变化，视为声明过期，报 FAIL。
EVOLVED_MODULES: dict[str, str] = {
    "src/units_selfcheck.py": (
        "会话 2026-10-15/l2-normalization：检查骨架 check() 与空转自测 _harness_selftest() "
        "抽到 tools/checkkit.py，供 selfcheck 与 selfcheck_l2 共用（避免两套实现各自腐化）。"
        "B 层行为比对不涉及本文件，625 组仍全等。"
    ),
}

FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f"  [FAIL] {message}")


def ok(message: str) -> None:
    print(f"  [PASS] {message}")


# --------------------------------------------------------------------------
# A. 函数体 AST 比对
# --------------------------------------------------------------------------
def functions_of(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: ast.dump(node.args) + "|" + ast.dump(ast.Module(body=node.body, type_ignores=[]))
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def module_level_of(path: Path) -> list[str]:
    """模块级语句的形态（忽略赋值目标名与字面量），用于报告"没比对到"的东西。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    kinds = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        kinds.append(type(node).__name__)
    return kinds


def compare_structure() -> None:
    print("A. 函数体 AST 比对")
    seen_diffs: set[tuple[str, str]] = set()
    for old_rel, new_rel in PAIRS:
        old_path, new_path = MVP / old_rel, ROOT / new_rel
        if not old_path.is_file() or not new_path.is_file():
            fail(f"缺少文件：{old_rel} 或 {new_rel}")
            continue
        old_fns, new_fns = functions_of(old_path), functions_of(new_path)
        set_diff = set(old_fns) ^ set(new_fns)
        if set_diff and old_rel not in EVOLVED_MODULES:
            fail(
                f"{old_rel}: 函数集合不一致 —— 仅旧有 {sorted(set(old_fns) - set(new_fns))}，"
                f"仅新有 {sorted(set(new_fns) - set(old_fns))}"
            )
        elif not set_diff and old_rel in EVOLVED_MODULES:
            fail(f"{old_rel}: 已声明为演化模块，但函数集合与参照实现完全一致（声明已过期）")
        # 同名函数一律逐一比对 —— 即使模块声明为演化，也不放过"偷改"。
        # 这里刻意不 continue：一旦 continue，本模块已申报的差异会全部被误报成"白名单过期"。
        for name in sorted(set(old_fns) & set(new_fns)):
            if old_fns[name] != new_fns[name]:
                seen_diffs.add((old_rel, name))

    unexpected = seen_diffs - set(ALLOWED_FUNC_DIFFS)
    if unexpected:
        for item in sorted(unexpected):
            fail(f"未申报的函数体差异：{item[0]}::{item[1]}()")
    missing = set(ALLOWED_FUNC_DIFFS) - seen_diffs
    if missing:
        for item in sorted(missing):
            fail(f"白名单声明了差异但实际不存在（白名单已过期）：{item[0]}::{item[1]}()")

    if not unexpected and not missing:
        ok(
            f"{len(PAIRS)} 个模块的共有函数已逐一比对；"
            f"函数体差异 {len(seen_diffs)} 处，全部在白名单内："
        )
        for (mod, fn), reason in sorted(ALLOWED_FUNC_DIFFS.items()):
            print(f"         - {mod}::{fn}() —— {reason}")
        if EVOLVED_MODULES:
            print(f"   已声明的演化模块 {len(EVOLVED_MODULES)} 个（函数集合允许增删，同名函数仍比对）：")
            for mod, reason in sorted(EVOLVED_MODULES.items()):
                print(f"         - {mod} —— {reason}")

    print("   模块级语句形态（仅供参考，不参与判定）：")
    for old_rel, new_rel in PAIRS:
        a = module_level_of(MVP / old_rel)
        b = module_level_of(ROOT / new_rel)
        flag = "同" if a == b else "异"
        print(f"         [{flag}] {old_rel} -> {new_rel}")


# --------------------------------------------------------------------------
# B. 差分行为比对
# --------------------------------------------------------------------------
def compare_behaviour() -> None:
    print("B. 差分行为比对（同一输入 -> 新旧返回值逐一相等）")
    from src import config as old_config, net as old_net, units as old_units
    from src.derive.net_liquidity import net_liquidity as old_nl
    from src.sources import cboe as old_cboe, fred as old_fred, yahoo as old_yahoo

    from L0_基元层 import config as new_config, net as new_net, units as new_units
    from L1_接入层.derive.net_liquidity import net_liquidity as new_nl
    from L1_接入层.sources import cboe as new_cboe, fred as new_fred, yahoo as new_yahoo

    checks = 0

    def same(label: str, a, b) -> None:
        nonlocal checks
        checks += 1
        if a != b:
            fail(f"{label}: 旧={a!r} 新={b!r}")

    # --- 单位换算：全令牌矩阵 × 多个量级，含跨族报错路径 ---
    tokens = sorted(old_units.registered())
    same("units.registered()", sorted(old_units.registered()), sorted(new_units.registered()))
    for src_tok in tokens:
        for dst_tok in tokens:
            for value in (0, 1, -1, "12345678901234.5678", 0.201, 6747560):
                try:
                    got_old = old_units.convert(value, src_tok, dst_tok)
                except Exception as exc:  # noqa: BLE001
                    got_old = type(exc).__name__
                try:
                    got_new = new_units.convert(value, src_tok, dst_tok)
                except Exception as exc:  # noqa: BLE001
                    got_new = type(exc).__name__
                same(f"convert({value!r},{src_tok},{dst_tok})", got_old, got_new)

    same("units.family_of(USD_BILLION)", old_units.family_of("USD_BILLION"), new_units.family_of("USD_BILLION"))
    same(
        "units.total(...)",
        old_units.total([(1, "USD_BILLION"), (2, "USD_MILLION")], target="USD_MILLION"),
        new_units.total([(1, "USD_BILLION"), (2, "USD_MILLION")], target="USD_MILLION"),
    )

    # --- 脱敏 ---
    for text, secrets in [
        ("key=abc12345 here", ("abc12345",)),
        ("no secret at all", ()),
        ("", ("abc",)),
        ("abcabc", ("abc",)),
    ]:
        same(f"net._scrub({text!r},{secrets})", old_net._scrub(text, secrets), new_net._scrub(text, secrets))

    # --- 配置：两份 sources.toml 与 .env 内容一致，加载结果必须深度相等 ---
    same("config.load_sources()", old_config.load_sources(), new_config.load_sources())
    same("config.all_secrets()", old_config.all_secrets(), new_config.all_secrets())
    same(
        "config.redact(样例)",
        old_config.redact("GET /x?api_key=SEKRET 200"),
        new_config.redact("GET /x?api_key=SEKRET 200"),
    )
    old_raw, new_raw = old_config.raw_dir(), new_config.raw_dir()
    same("config.raw_dir().name", old_raw.name, new_raw.name)
    same("config.raw_dir() 相对各自根", old_raw.relative_to(MVP), new_raw.relative_to(ROOT))

    # --- 解析函数：固定输入 ---
    fred_payload = {
        "observations": [{"date": "2026-10-07", "value": "6747560"}, {"date": "2026-09-30", "value": "."}]
    }
    same("fred.latest_observation", old_fred.latest_observation(fred_payload), new_fred.latest_observation(fred_payload))
    for bad in ({}, {"observations": []}):
        try:
            old_fred.latest_observation(bad)
            got_old = "no-raise"
        except Exception as exc:  # noqa: BLE001
            got_old = type(exc).__name__
        try:
            new_fred.latest_observation(bad)
            got_new = "no-raise"
        except Exception as exc:  # noqa: BLE001
            got_new = type(exc).__name__
        same(f"fred.latest_observation({bad})", got_old, got_new)

    cboe_html = 'x\\"name\\":\\"TOTAL PUT/CALL RATIO\\",\\"value\\":\\"0.88\\"y'
    same("cboe._extract_ratio(命中)", old_cboe._extract_ratio(cboe_html, "TOTAL PUT/CALL RATIO"), new_cboe._extract_ratio(cboe_html, "TOTAL PUT/CALL RATIO"))
    try:
        old_cboe._extract_ratio("nothing", "TOTAL PUT/CALL RATIO")
        got_old = "no-raise"
    except Exception as exc:  # noqa: BLE001
        got_old = type(exc).__name__
    try:
        new_cboe._extract_ratio("nothing", "TOTAL PUT/CALL RATIO")
        got_new = "no-raise"
    except Exception as exc:  # noqa: BLE001
        got_new = type(exc).__name__
    same("cboe._extract_ratio(未命中)", got_old, got_new)

    # fetch_index_history 的解析：把两个实现的 _fetch 换成同一段固定 CSV 文本
    csv_text = "DATE,OPEN,HIGH,LOW,CLOSE\n10/14/2026,16.0,17.0,15.0,16.87\n10/13/2026,15.0,16.0,14.0,15.50\n"
    sources = old_config.load_sources()
    old_cboe._fetch = lambda url, sources: csv_text
    new_cboe._fetch = lambda url, sources: csv_text
    same(
        "cboe.fetch_index_history(固定 CSV)",
        old_cboe.fetch_index_history("VIX_History.csv", sources=sources),
        new_cboe.fetch_index_history("VIX_History.csv", sources=sources),
    )

    yahoo_payload = {
        "chart": {"result": [{"timestamp": [1000, 2000, 3000], "indicators": {"quote": [{"close": [1.0, None, 3.5]}]}}]}
    }
    same("yahoo.latest_close", old_yahoo.latest_close(yahoo_payload), new_yahoo.latest_close(yahoo_payload))
    try:
        old_yahoo.latest_close({"chart": {"result": None, "error": "x"}})
        got_old = "no-raise"
    except Exception as exc:  # noqa: BLE001
        got_old = type(exc).__name__
    try:
        new_yahoo.latest_close({"chart": {"result": None, "error": "x"}})
        got_new = "no-raise"
    except Exception as exc:  # noqa: BLE001
        got_new = type(exc).__name__
    same("yahoo.latest_close(无 result)", got_old, got_new)

    # --- 净值公式：用真实落盘值 ---
    walcl = json.loads((ROOT / "data/raw/2026-10-15/fred_walcl.json").read_text(encoding="utf-8"))
    tga = json.loads((ROOT / "data/raw/2026-10-15/fred_wtregon.json").read_text(encoding="utf-8"))
    rrp = json.loads((ROOT / "data/raw/2026-10-15/fred_rrpontsyd.json").read_text(encoding="utf-8"))
    terms = [
        (float(walcl["observations"][0]["value"]), "USD_MILLION", 1),
        (float(tga["observations"][0]["value"]), "USD_MILLION", -1),
        (float(rrp["observations"][0]["value"]), "USD_BILLION", -1),
    ]
    same("net_liquidity(真实值)", old_nl(terms, target="USD_MILLION"), new_nl(terms, target="USD_MILLION"))
    for bad_sign in (0, 2, None):
        try:
            old_nl([(1, "USD_MILLION", bad_sign)], target="USD_MILLION")
            got_old = "no-raise"
        except Exception as exc:  # noqa: BLE001
            got_old = type(exc).__name__
        try:
            new_nl([(1, "USD_MILLION", bad_sign)], target="USD_MILLION")
            got_new = "no-raise"
        except Exception as exc:  # noqa: BLE001
            got_new = type(exc).__name__
        same(f"net_liquidity(符号={bad_sign!r})", got_old, got_new)

    same("net_liquidity(真实值) 类型", type(old_nl(terms, target="USD_MILLION")), type(new_nl(terms, target="USD_MILLION")))
    if not isinstance(new_nl(terms, target="USD_MILLION"), Decimal):
        fail("新实现返回值不再是 Decimal")

    if checks and not any("B." in f for f in FAILURES):
        ok(f"{checks} 组输入的新旧返回值全部相等")


def main() -> int:
    print(f"参照实现：{MVP}")
    print(f"移植实现：{ROOT}")
    print()
    compare_structure()
    print()
    compare_behaviour()
    print()
    if FAILURES:
        print(f"结论：不通过 —— {len(FAILURES)} 项失败")
        return 1
    print("结论：通过 —— 结构层与行为层证据均无未申报差异")
    return 0


if __name__ == "__main__":
    sys.exit(main())
