"""检查器共用骨架（非分层）。

为什么单独成文件：`tools/` 下有两个自检脚本（`selfcheck` / `selfcheck_l2`），
它们共用同一套"跑检查 -> 汇总 -> 非空转自测"骨架。这套骨架若各写一份，
"检查器是不是空转"这个最关键的保证就会有两个实现、两处可能腐化。

非空转保证：`selftest()` 故意塞一个必然失败的用例，确认它确实被记为 FAIL。
调用方把它本身也注册成一项检查，所以"自测失败"会让整个脚本报红。
"""

from __future__ import annotations

from typing import Callable


class CheckKit:
    def __init__(self, title: str) -> None:
        self.title = title
        self._results: list[tuple[bool, str, str]] = []

    def check(self, name: str, fn: Callable[[], object]) -> None:
        try:
            detail = fn()
        except Exception as exc:  # noqa: BLE001 - 检查器要吞掉一切异常并记为 FAIL
            self._results.append((False, name, f"{type(exc).__name__}: {exc}"))
        else:
            self._results.append((True, name, str(detail or "")))

    def selftest(self) -> str:
        """证明本骨架不是空转：故意做坏的用例必须被记为 FAIL。"""
        saved = list(self._results)
        self._results.clear()
        self.check("__故意做坏__", lambda: 1 / 0)
        caught = len(self._results) == 1 and self._results[0][0] is False
        self._results.clear()
        self._results.extend(saved)
        if not caught:
            raise RuntimeError("检查器空转：故意做坏的用例没有被记为 FAIL")
        return "故意做坏的用例已被正确记为 FAIL"

    def report(self, *, redact: Callable[[str], str] | None = None) -> int:
        """打印全部结论并返回退出码（任一 FAIL 即 1）。"""
        scrub = redact or (lambda text: text)
        failed = [item for item in self._results if not item[0]]
        for ok, name, detail in self._results:
            suffix = f"  —— {scrub(detail)}" if detail else ""
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}")
        passed = len(self._results) - len(failed)
        print(f"\n{self.title}：执行 {len(self._results)} 项检查，通过 {passed} 项")
        return 1 if failed else 0
