"""Yahoo Finance 数据源（L1）。只负责 chart 接口的 URL 组装与响应解析。

注意：这是非官方接口，无 SLA。取不到就抛错，不返回空值。
"""

from __future__ import annotations

import json
import urllib.parse

from L0_基元层 import net


def fetch_quote(symbol: str, *, sources: dict) -> dict:
    yahoo = sources["yahoo"]
    http = sources["http"]
    url = yahoo["chart_url"].format(symbol=urllib.parse.quote(symbol, safe=""))
    params = {"range": yahoo["range"], "interval": yahoo["interval"]}
    payload = net.fetch_text(
        f"{url}?{urllib.parse.urlencode(params)}",
        timeout=http["timeout_seconds"],
        user_agent=http["user_agent"],
    )
    return json.loads(payload)


def latest_close(payload: dict) -> tuple[str, float]:
    """取最近一根日线的 (日期, 收盘)。"""
    results = payload.get("chart", {}).get("result")
    if not results:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"Yahoo 响应无 result：{error}")
    result = results[0]
    stamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    for stamp, close in zip(reversed(stamps), reversed(closes)):
        if close is None:
            continue
        from datetime import datetime, timezone

        day = datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y-%m-%d")
        return day, float(close)
    raise RuntimeError("Yahoo 响应里没有有效收盘价")
