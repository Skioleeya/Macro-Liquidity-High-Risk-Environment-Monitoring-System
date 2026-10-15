"""FRED 数据源（L1）。只负责 FRED 接口的 URL 组装与响应解析。

密钥只在本模块内取出，并且立刻作为 secrets 传给 net 层，
保证任何报错路径都不会把密钥带出去。
"""

from __future__ import annotations

import json
import urllib.parse

from .. import net
from ..config import get_secret


def _get(path: str, params: dict, *, sources: dict) -> dict:
    fred = sources["fred"]
    http = sources["http"]
    api_key = get_secret(fred["api_key_env"])
    query = urllib.parse.urlencode(
        {**params, "api_key": api_key, "file_type": fred["file_type"]}
    )
    payload = net.fetch_text(
        f"{path}?{query}",
        timeout=http["timeout_seconds"],
        user_agent=http["user_agent"],
        secrets=(api_key,),
    )
    return json.loads(payload)


def fetch_series(series_id: str, *, sources: dict) -> dict:
    """取单个序列的最近若干观测值。缺 API Key 时由 config 层直接抛错。"""
    fred = sources["fred"]
    return _get(
        fred["base_url"],
        {
            "series_id": series_id,
            "sort_order": fred["sort_order"],
            "limit": fred["default_limit"],
        },
        sources=sources,
    )


def fetch_metadata(series_id: str, *, sources: dict) -> dict:
    """取序列元数据，用于把配置声明的单位与 FRED 权威单位对账。"""
    fred = sources["fred"]
    entries = _get(fred["meta_url"], {"series_id": series_id}, sources=sources).get(
        "seriess"
    )
    if not entries:
        raise RuntimeError(f"FRED 元数据里没有 {series_id}")
    return entries[0]


def latest_observation(payload: dict) -> tuple[str, str]:
    """从响应里取最近一条 (日期, 数值)。FRED 的缺失值写作 '.'。"""
    observations = payload.get("observations")
    if not observations:
        raise RuntimeError("FRED 响应里没有 observations")
    head = observations[0]
    return head["date"], head["value"]
