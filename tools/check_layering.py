"""层级单向依赖校验（非分层）。

用法（在**仓库根目录**下）：
    python -m tools.check_layering
    python -m tools.check_layering --selftest      # 只跑分析函数自测

规则（来自 docs/正式项目分层架构设计.md 第 5 节）：
  1. 只允许 Ln 导入 Lm，其中 m < n；反向导入即缺陷。
  2. 同层内模块不得互相 import（含相对导入）—— 但**显式声明的例外**见下。
  3. L0 不含任何 import L* 的语句。
  4. tools/ 与 config/、docs/、notes/ 等非分层目录不参与校验。

## 同层依赖的两类显式例外

第 2 条的用意是防止**同层业务模块**互相耦合（典型如 L3 的四个维度互相 import）。
但有两类模块天然需要跨同层使用，因此允许显式声明：

  - `SHARED_MODULES`（层内共享叶子）：本层其它模块可以 import 它。
    声明成立的前提是它**自己不得 import 本层任何模块**（否则它就不是叶子）。
  - `ORCHESTRATORS`（层内编排）：它就是这个层的组装点，允许 import 本层其它模块。
    声明成立的前提是它**不得被本层任何模块 import**（否则它就是个隐藏枢纽）。

两类声明都会被 `_verify_declarations` **机械校验**：
声明不实（共享叶子其实有层内依赖 / 编排模块其实被别人 import / 声明的文件根本不存在）
一律报 FAIL。没有这一步，白名单会慢慢变成"什么都能写"。

## 非空转保证

内置自测把**已知违规**与**已知合规**的源码喂给同一个分析函数：
已知违规必须被检出、已知合规必须不被误报、显式例外必须恰好生效。
分析函数空转时脚本不可能报绿。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYER_DIR = re.compile(r"^L(\d+)_")
EXCLUDED_DIRS = {"tools", "config", "docs", "notes", "data", ".workbuddy-ai", "mvp"}

# 层内共享叶子：本层其它模块可以 import。值是不带 .py 的模块名。
SHARED_MODULES: dict[int, frozenset[str]] = {
    1: frozenset({"contract"}),
    2: frozenset({"settings", "contract"}),
}

# 层内编排：允许 import 本层其它模块，但不得被本层任何模块 import。
ORCHESTRATORS: dict[int, frozenset[str]] = {
    2: frozenset({"pipeline"}),
}


def layer_of(segment: str) -> int | None:
    """把顶层目录名映射成层级号；不是分层目录则返回 None。"""
    match = LAYER_DIR.match(segment)
    return int(match.group(1)) if match else None


def _resolve_relative(package_parts: list[str], level: int, module: str | None) -> list[str]:
    """把相对导入解析成绝对模块路径片段。"""
    base = package_parts[: len(package_parts) - (level - 1)]
    return base + (module.split(".") if module else [])


def import_targets(node: ast.AST, package_parts: list[str]) -> list[tuple[list[str], int]]:
    """把一个 import 语句展开成 [(模块路径片段, 行号)]。

    `from X import a, b` 会展开成两条 —— 不展开的话，同层共享模块的判定就看不到被导入的名字。
    """
    if isinstance(node, ast.Import):
        return [(alias.name.split("."), node.lineno) for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    if node.level:
        base = _resolve_relative(package_parts, node.level, node.module)
        if node.module is None:
            return [(base + [alias.name], node.lineno) for alias in node.names]
        return [(base, node.lineno)]
    if node.module:
        base = node.module.split(".")
        return [(base + [alias.name], node.lineno) for alias in node.names]
    return []


def analyse_source(
    source: str,
    package_parts: list[str],
    own_layer: int,
    *,
    shared: frozenset[str] = frozenset(),
    orchestrator: bool = False,
) -> list[str]:
    """返回该源码的违规说明列表。纯函数，便于自测。

    package_parts：本文件所在包的各层目录名（如 ['L1_接入层','sources']）。
    own_layer：本文件所属层级号。
    shared：本层声明的共享叶子模块名（可被本层任意模块 import）。
    orchestrator：本文件是否为本层声明的编排模块（可 import 本层任意模块）。
    """
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        for parts, lineno in import_targets(node, package_parts):
            if not parts:
                continue
            other = layer_of(parts[0])
            if other is None:
                continue
            if other == own_layer:
                if orchestrator:
                    continue
                stem = parts[1] if len(parts) > 1 else None
                if stem is not None and stem in shared:
                    continue
                violations.append(
                    f"第 {lineno} 行：同层互相 import —— {'.'.join(parts)}"
                )
            elif other > own_layer:
                violations.append(
                    f"第 {lineno} 行：反向依赖 L{own_layer} -> L{other} —— {'.'.join(parts)}"
                )
    return violations


def _harness_selftest() -> str:
    """证明分析函数不是空转：已知违规必须被检出，已知合规与显式例外必须恰好生效。"""
    parts = ["L1_接入层", "sources"]

    bad = "from L3_因子层 import gamma_proxy\nfrom ..sources import fred\n"
    got = analyse_source(bad, parts, own_layer=1)
    if len(got) != 2:
        raise RuntimeError(f"自测失败：预期检出 2 条违规，实际 {len(got)} 条 —— {got}")

    good = "from L0_基元层 import net\nimport json\n"
    got_ok = analyse_source(good, parts, own_layer=1)
    if got_ok:
        raise RuntimeError(f"自测失败：合规源码被误报 —— {got_ok}")

    # 例外一：共享叶子可被同层 import
    shared_src = "from L1_接入层 import contract\n"
    if analyse_source(shared_src, ["L1_接入层"], own_layer=1, shared=frozenset({"contract"})):
        raise RuntimeError("自测失败：已声明的共享叶子被误报")

    # 例外二：**未**声明的同层 import 仍然必须被检出（否则例外等于把规则废掉）
    unshared = analyse_source(shared_src, ["L1_接入层"], own_layer=1, shared=frozenset({"settings"}))
    if len(unshared) != 1:
        raise RuntimeError(f"自测失败：未声明的同层 import 未被检出 —— {unshared}")

    # 例外三：编排模块可自由 import 本层
    orch = analyse_source(
        "from L2_归一化层 import align, contract, settings\n", ["L2_归一化层"], own_layer=2,
        orchestrator=True,
    )
    if orch:
        raise RuntimeError(f"自测失败：已声明的编排模块被误报 —— {orch}")

    return "违规 2 条全检出 / 合规 0 误报 / 三类例外各恰好生效"


def iter_layer_files() -> list[tuple[Path, int, list[str]]]:
    """枚举所有分层目录下的 .py 文件，附带其层级号与包路径片段。"""
    found: list[tuple[Path, int, list[str]]] = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT)
        if any(part in EXCLUDED_DIRS or part == "__pycache__" for part in rel.parts):
            continue
        own = layer_of(rel.parts[0])
        if own is None:
            continue
        # 包路径 = 去掉文件名。对 `L1_接入层/sources/fred.py` 得 ['L1_接入层','sources']，
        # 对 `L1_接入层/__init__.py` 得 ['L1_接入层'] —— 两种情况都是 parts[:-1]。
        found.append((path, own, list(rel.parts[:-1])))
    return found


def _same_layer_imports(files: list[tuple[Path, int, list[str]]]) -> dict[tuple[int, str], set[str]]:
    """{（层号, 模块名）: 它 import 的本层模块名集合}。"""
    result: dict[tuple[int, str], set[str]] = {}
    for path, own, package_parts in files:
        imported: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            for parts, _ in import_targets(node, package_parts):
                if len(parts) > 1 and layer_of(parts[0]) == own:
                    imported.add(parts[1])
        result[(own, path.stem)] = imported
    return result


def _verify_declarations(files: list[tuple[Path, int, list[str]]]) -> list[str]:
    """校验 SHARED_MODULES / ORCHESTRATORS 的声明是否属实。不属实即报错。"""
    problems: list[str] = []
    same = _same_layer_imports(files)
    imported_by: dict[tuple[int, str], set[str]] = {}
    for (layer, stem), imported in same.items():
        for target in imported:
            imported_by.setdefault((layer, target), set()).add(stem)

    for layer, names in SHARED_MODULES.items():
        for name in sorted(names):
            deps = same.get((layer, name))
            if deps is None:
                problems.append(f"L{layer} 把 {name} 声明为共享叶子，但该模块不存在")
            elif deps:
                problems.append(
                    f"L{layer} 把 {name} 声明为共享叶子，但它 import 了本层模块：{sorted(deps)}"
                )
    for layer, names in ORCHESTRATORS.items():
        for name in sorted(names):
            if (layer, name) not in same:
                problems.append(f"L{layer} 把 {name} 声明为编排模块，但该模块不存在")
                continue
            importers = imported_by.get((layer, name), set())
            if importers:
                problems.append(
                    f"L{layer} 把 {name} 声明为编排模块，但它被本层模块 import：{sorted(importers)}"
                )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="层级单向依赖校验")
    parser.add_argument("--selftest", action="store_true", help="只跑分析函数自测")
    args = parser.parse_args()

    print("=== 层级单向依赖校验 ===")

    try:
        detail = _harness_selftest()
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] 分析函数自测  —— {type(exc).__name__}: {exc}")
        return 1
    print(f"  [PASS] 分析函数自测  —— {detail}")
    if args.selftest:
        return 0

    files = iter_layer_files()
    violations: list[str] = []

    for path, own, package_parts in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        messages = analyse_source(
            path.read_text(encoding="utf-8"),
            package_parts,
            own,
            shared=SHARED_MODULES.get(own, frozenset()),
            orchestrator=path.stem in ORCHESTRATORS.get(own, frozenset()),
        )
        violations.extend(f"{rel} {message}" for message in messages)

    try:
        problems = _verify_declarations(files)
    except Exception as exc:  # noqa: BLE001
        problems = [f"声明校验自身出错：{type(exc).__name__}: {exc}"]

    # 统计实际的跨层导入边，证明"确实扫到了依赖"而不是没扫到东西。
    edges: dict[str, int] = {}
    for path, own, _ in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                other = layer_of(node.module.split(".")[0])
                if other is not None and other < own:
                    edges[f"L{own} -> L{other}"] = edges.get(f"L{own} -> L{other}", 0) + 1

    honoured = {
        f"L{layer}": sorted(
            SHARED_MODULES.get(layer, frozenset()) | ORCHESTRATORS.get(layer, frozenset())
        )
        for layer in sorted(set(SHARED_MODULES) | set(ORCHESTRATORS))
    }
    print(f"  扫描分层文件 {len(files)} 个，跨层导入边：{edges or '无'}")
    print(f"  已声明的层内例外：{honoured or '无'}")

    for item in problems:
        print(f"  [FAIL] 声明校验  {item}")
    for item in violations:
        print(f"  [FAIL] {item}")

    total = len(violations) + len(problems)
    if total:
        print(f"\n发现 {total} 条违规（其中声明不实 {len(problems)} 条）")
        return 1

    print("  [PASS] 无同层互相 import（例外声明属实），无反向依赖")
    print(f"\n扫描 {len(files)} 个文件，0 条违规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
