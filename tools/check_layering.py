"""层级单向依赖校验（非分层）。

用法（在**仓库根目录**下）：
    python -m tools.check_layering

规则（来自 docs/正式项目分层架构设计.md 第 5 节）：
  1. 只允许 Ln 导入 Lm，其中 m < n；反向导入即缺陷。
  2. 同层内模块不得互相 import（含相对导入）。
  3. L0 不含任何 import L* 的语句。
  4. tools/ 与 config/、docs/、notes/ 等非分层目录不参与校验。

非空转保证：内置自测 —— 把一段**已知违规**的源码喂给同一个分析函数，
若它没被检出，则本脚本自身报 FAIL 并退出 1。分析函数空转时脚本不可能报绿。
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


def layer_of(segment: str) -> int | None:
    """把顶层目录名映射成层级号；不是分层目录则返回 None。"""
    match = LAYER_DIR.match(segment)
    return int(match.group(1)) if match else None


def _resolve_relative(package_parts: list[str], level: int, module: str | None) -> list[str]:
    """把相对导入解析成绝对模块路径片段。"""
    base = package_parts[: len(package_parts) - (level - 1)]
    return base + (module.split(".") if module else [])


def analyse_source(source: str, package_parts: list[str], own_layer: int) -> list[str]:
    """返回该源码的违规说明列表。纯函数，便于自测。

    package_parts：本文件所在包的各层目录名（如 ['L1_接入层','sources']）。
    own_layer：本文件所属层级号。
    """
    violations: list[str] = []
    tree = ast.parse(source)

    for node in ast.walk(tree):
        targets: list[tuple[list[str], int]] = []
        if isinstance(node, ast.Import):
            targets = [(alias.name.split("."), node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                targets = [
                    (_resolve_relative(package_parts, node.level, node.module), node.lineno)
                ]
            elif node.module:
                targets = [(node.module.split("."), node.lineno)]

        for parts, lineno in targets:
            if not parts:
                continue
            other = layer_of(parts[0])
            if other is None:
                continue
            if other == own_layer:
                violations.append(
                    f"第 {lineno} 行：同层互相 import —— {'.'.join(parts)}"
                )
            elif other > own_layer:
                violations.append(
                    f"第 {lineno} 行：反向依赖 L{own_layer} -> L{other} —— {'.'.join(parts)}"
                )

    return violations


def _harness_selftest() -> str:
    """证明分析函数不是空转：已知违规必须被检出，已知合规必须不被误报。"""
    bad = "from L3_因子层 import gamma_proxy\nfrom ..sources import fred\n"
    got = analyse_source(bad, ["L1_接入层", "sources"], own_layer=1)
    if len(got) != 2:
        raise RuntimeError(f"自测失败：预期检出 2 条违规，实际 {len(got)} 条 —— {got}")

    good = "from L0_基元层 import net\nimport json\n"
    got_ok = analyse_source(good, ["L1_接入层", "sources"], own_layer=1)
    if got_ok:
        raise RuntimeError(f"自测失败：合规源码被误报 —— {got_ok}")

    return "已知违规 2 条全部检出，已知合规 0 误报"


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
        package_parts = list(rel.parts[:-1])
        found.append((path, own, package_parts))
    return found


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
    edges: dict[str, int] = {}

    for path, own, package_parts in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for message in analyse_source(path.read_text(encoding="utf-8"), package_parts, own):
            violations.append(f"{rel} {message}")

    # 统计实际的跨层导入边，证明"确实扫到了依赖"而不是没扫到东西。
    for path, own, _ in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                other = layer_of(node.module.split(".")[0])
                if other is not None and other < own:
                    edges[f"L{own} -> L{other}"] = edges.get(f"L{own} -> L{other}", 0) + 1

    print(f"  扫描分层文件 {len(files)} 个，跨层导入边：{edges or '无'}")

    if violations:
        for item in violations:
            print(f"  [FAIL] {item}")
        print(f"\n发现 {len(violations)} 条违规")
        return 1

    print("  [PASS] 无同层互相 import，无反向依赖")
    print(f"\n扫描 {len(files)} 个文件，0 条违规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
