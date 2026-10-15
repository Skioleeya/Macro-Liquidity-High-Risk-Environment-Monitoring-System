"""CBOE 数据源（L1）。

职责边界：只负责 CBOE 日度 PCR 页面与波动率指数历史 CSV 的解析。
注意：CBOE 官网已无公开 CSV 下载端点（实测 403/404），PCR 只能从
服务端渲染的页面 payload 中解析，因此解析失败必须抛错而非返回空值。
"""

from __future__ import annotations

import re

from .. import net


def _fetch(url: str, sources: dict) -> str:
    http = sources["http"]
    return net.fetch_text(
        url, timeout=http["timeout_seconds"], user_agent=http["user_agent"]
    )


def fetch_daily_ratios(date_str: str | None, *, sources: dict) -> dict[str, float]:
    """取 PCR。date_str 形如 2026-10-14；传 None 则取官网当前展示的交易日。"""
    cboe = sources["cboe"]
    url = cboe["daily_stats_url"] + (f"?dt={date_str}" if date_str else "")
    html = _fetch(url, sources)
    return {
        key: _extract_ratio(html, label)
        for key, label in cboe["ratios"]["labels"].items()
    }


def _extract_ratio(html: str, label: str) -> float:
    pattern = (
        r'\\?"name\\?":\\?"' + re.escape(label) + r'\\?",\\?"value\\?":\\?"([0-9.]+)\\?"'
    )
    match = re.search(pattern, html)
    if match is None:
        raise RuntimeError(f"CBOE 页面中未找到 {label!r}（页面结构可能已变）")
    return float(match.group(1))


def fetch_index_history(filename: str, *, sources: dict) -> list[tuple[str, float]]:
    """取波动率指数历史 CSV，返回 [(日期, 收盘)]。"""
    cboe = sources["cboe"]
    url = cboe["index_csv_base"] + filename
    text = _fetch(url, sources)
    rows: list[tuple[str, float]] = []
    for line in text.splitlines()[1:]:
        parts = line.strip().split(",")
        if len(parts) < 5:
            continue
        rows.append((parts[0], float(parts[4])))
    if not rows:
        raise RuntimeError(f"{filename} 解析后为空")
    return rows
