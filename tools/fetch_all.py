"""数据拉取驱动脚本（非分层）。

用法（在**仓库根目录**下）：
    python -m tools.fetch_all              # 取各源最新
    python -m tools.fetch_all --date 2026-10-14

定位：本文件不属于 L0–L7 任何一层，是横向驱动脚本 —— 只负责"按顺序调用
L1 各适配器、把结果落盘、把失败汇总成退出码"，不含任何业务计算。

行为约定：三个数据源各自独立跑，任一失败都打印 FAIL 并以退出码 1 结束。
不做静默降级 —— 失败必须可见。打印前所有文本一律过 config.redact()。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from L0_基元层.config import ConfigError, load_sources, raw_dir, redact
from L1_接入层.sources import cboe, fred, yahoo

NY = ZoneInfo("America/New_York")


def _stamp() -> str:
    return datetime.now(NY).strftime("%Y-%m-%d %H:%M %Z")


def _write(directory: Path, name: str, payload) -> None:
    (directory / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_fred(sources: dict, directory: Path) -> str:
    parts = []
    for alias, spec in sources["fred"]["series"].items():
        payload = fred.fetch_series(spec["id"], sources=sources)
        _write(directory, f"fred_{alias}.json", payload)
        day, value = fred.latest_observation(payload)
        parts.append(f"{alias}={value} {spec['unit']}@{day}")
    return "  ".join(parts)


def run_cboe(sources: dict, directory: Path, date_str: str | None) -> str:
    cboe_cfg = sources["cboe"]
    ratios = cboe.fetch_daily_ratios(date_str, sources=sources)
    _write(directory, "cboe_ratios.json", ratios)
    parts = [f"{k}={v} {cboe_cfg['ratios']['unit']}" for k, v in ratios.items()]
    for filename in cboe_cfg["index_csv_files"]:
        rows = cboe.fetch_index_history(filename, sources=sources)
        _write(directory, f"cboe_{filename.replace('_History.csv', '')}.json", rows[-5:])
        parts.append(f"{filename.split('_')[0]}={rows[-1][1]} {cboe_cfg['index_csv_unit']}")
    return "  ".join(parts)


def run_yahoo(sources: dict, directory: Path) -> str:
    parts = []
    failures = []
    for symbol, spec in sources["yahoo"]["symbols"].items():
        try:
            payload = yahoo.fetch_quote(symbol, sources=sources)
            day, close = yahoo.latest_close(payload)
            stem = symbol.replace("^", "").replace("=", "_")
            _write(directory, f"yahoo_{stem}.json", payload)
            parts.append(f"{symbol}={close} {spec['unit']}@{day}")
        except RuntimeError as exc:
            failures.append(f"{symbol}({exc})")
    if failures:
        raise RuntimeError("部分代码失败：" + ", ".join(failures))
    return "  ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="CRS-100 数据拉取")
    parser.add_argument("--date", default=None, help="交易日，形如 2026-10-14；默认取最新")
    args = parser.parse_args()

    sources = load_sources()
    directory = raw_dir() / (args.date or datetime.now(NY).strftime("%Y-%m-%d"))
    directory.mkdir(parents=True, exist_ok=True)

    print(f"=== CRS-100 数据拉取 @ {_stamp()} ===")
    print(f"落盘目录: {directory}\n")

    jobs = [
        ("FRED ", lambda: run_fred(sources, directory)),
        ("CBOE ", lambda: run_cboe(sources, directory, args.date)),
        ("YAHOO", lambda: run_yahoo(sources, directory)),
    ]

    failed = 0
    for label, job in jobs:
        try:
            detail = job()
        except (RuntimeError, ConfigError) as exc:
            failed += 1
            print(f"[{label}] FAIL  {redact(str(exc))}")
        else:
            print(f"[{label}] PASS  {detail}")

    print(f"\n结果：{len(jobs) - failed}/{len(jobs)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
