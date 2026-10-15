"""面板构建驱动（非分层）。

用法（在**仓库根目录**下）：
    python -m tools.build_panel                      # 取最新 raw 目录，as_of = 该目录名
    python -m tools.build_panel --as-of 2026-10-15   # 指定决策日
    python -m tools.build_panel --raw 2026-10-15 --as-of 2026-10-15

定位：本文件不属于 L0–L7 任何一层，是横向驱动脚本 —— 只负责"加载配置、
调 L1 把落盘 payload 读成观测流、调 L2 组装面板、打印结果与退出码"。
所有业务计算都在 L2 里；本文件不含任何判断逻辑。

行为约定：任一步失败即打印 FAIL 并以退出码 1 结束。不静默降级。
打印前所有文本一律过 config.redact()。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from L0_基元层.config import ConfigError, load_sources, raw_dir, redact
from L1_接入层.observations import collect
from L2_归一化层 import pipeline
from L2_归一化层.settings import SettingsError, load_settings


def latest_raw_dir() -> Path:
    """raw 目录下按名字排序的最后一个子目录。自检脚本也用它，所以是公开名字。"""
    base = raw_dir()
    dirs = sorted((d for d in base.iterdir() if d.is_dir()), key=lambda d: d.name)
    if not dirs:
        raise RuntimeError(f"没有落盘数据，请先跑 python -m tools.fetch_all（{base}）")
    return dirs[-1]


def _summarize(panel, path: Path) -> str:
    lines = [f"面板落盘：{path}", f"as_of={panel.as_of}  行数={len(panel.rows)}"]
    width = max(len(key) for key in panel.series_keys())
    for key in panel.series_keys():
        rows = panel.rows_of(key)
        real = sum(1 for row in rows if not row.fill_flag)
        tail = max(rows, key=lambda row: row.date)
        lines.append(
            f"  {key:<{width}}  行={len(rows):>3}  真实={real:>3}  填充={len(rows) - real:>3}"
            f"  单位={tail.unit:<14}  尾部数据日={tail.source_as_of}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="CRS-100 面板构建")
    parser.add_argument("--raw", default=None, help="raw 子目录名，如 2026-10-15；默认取最新")
    parser.add_argument("--as-of", dest="as_of", default=None, help="决策日，如 2026-10-15")
    args = parser.parse_args()

    try:
        sources = load_sources()
        settings = load_settings()
        directory = raw_dir() / args.raw if args.raw else latest_raw_dir()
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.fromisoformat(directory.name)
        observations = collect(directory, sources)
        panel, path = pipeline.build_and_store(observations, settings, as_of=as_of)
    except (ConfigError, SettingsError, RuntimeError, ValueError) as exc:
        print(f"[BUILD] FAIL  {redact(str(exc))}")
        return 1

    print(f"=== CRS-100 面板构建 @ {as_of} ===")
    print(f"输入目录：{directory}")
    print(f"观测条数：{len(observations)}")
    print(_summarize(panel, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
