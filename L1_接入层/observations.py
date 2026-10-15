"""把已落盘的原始 payload 解析成 `Observation` 流（L1）。

为什么需要这个模块：L1 的适配器返回的是**原始 payload**（`fetch_series` / `fetch_index_history`
/ `fetch_quote`），`tools/fetch_all.py` 把它们落盘；但 L2 要的是带单位的观测流。
本模块就是那条 "payload -> Observation" 的通道 —— 按架构文档第 4 节，
`Observation` 是 L1 的产物，所以这条通道属于 L1。

`series_key` 约定（与 `config/normalization.toml` 头部注释一致）：
    fred:<别名>                          <- sources.toml [fred.series.<别名>]
    cboe:<文件名去 _History.csv 并小写>   <- [cboe] index_csv_files
    cboe:<label 键>                      <- [cboe.ratios.labels]
    yahoo:<代码>                         <- [yahoo.symbols]

本模块的 `series_key_*` 函数是该约定的**唯一实现** —— 配置注释、L2 自检、
面板组装都引用它们，避免同一套拼法散落多处后各自漂移。

**本模块不产出 CBOE PCR 观测**：PCR 的日期只能从页面自身取，而现有适配器只解析了数值、
没有解析页面上的交易日。用落盘目录名当日期等于编造一个日期，比缺失更糟，
所以这里不产出（该三键已在 normalization.toml 的 [pending] 里显式声明）。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from L1_接入层.contract import Observation, make_observation

# FRED 用 "." 表示"该日没有观测"。缺失值不是观测，跳过；
# 但整份 payload 全是缺失值时报错 —— 那是源坏了，不是"今天没数据"。
FRED_MISSING = "."


class ObservationSourceError(RuntimeError):
    """落盘 payload 缺失或结构不符。不返回空值、不返回默认值。"""


def series_key_fred(alias: str) -> str:
    return f"fred:{alias}"


def series_key_cboe_index(filename: str) -> str:
    return "cboe:" + filename.replace("_History.csv", "").lower()


def series_key_cboe_ratio(label_key: str) -> str:
    return f"cboe:{label_key}"


def series_key_yahoo(symbol: str) -> str:
    return f"yahoo:{symbol}"


def yahoo_stem(symbol: str) -> str:
    """sources.toml 的代码 -> tools/fetch_all.py 落盘用的文件名主干。"""
    return symbol.replace("^", "").replace("=", "_")


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise ObservationSourceError(f"原始数据文件不存在：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ObservationSourceError(f"原始数据文件不是合法 JSON：{path}（{exc}）") from None


def _retrieved_at(path: Path) -> datetime:
    """取回时刻 = 文件落盘时刻（UTC，带时区）。"""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _stamp(path: Path, override: datetime | None) -> datetime:
    return override if override is not None else _retrieved_at(path)


def from_fred(
    payload: dict,
    *,
    alias: str,
    unit: str,
    source: str,
    retrieved_at: datetime,
) -> list[Observation]:
    """FRED 响应 -> 观测。注意 FRED 的 `sort_order=desc`：返回是**降序**的。"""
    observations = payload.get("observations")
    if not observations:
        raise ObservationSourceError(f"FRED {alias} 响应里没有 observations")
    key = series_key_fred(alias)
    out: list[Observation] = []
    missing = 0
    for entry in observations:
        if entry.get("value") == FRED_MISSING:
            missing += 1
            continue
        out.append(
            make_observation(
                series_key=key,
                day=date.fromisoformat(entry["date"]),
                value=entry["value"],
                unit=unit,
                source=source,
                retrieved_at=retrieved_at,
            )
        )
    if not out:
        raise ObservationSourceError(
            f"FRED {alias} 的 {len(observations)} 条观测全部是缺失值（{FRED_MISSING!r}）"
        )
    return out


def from_cboe_index(
    rows: Sequence[Sequence[Any]],
    *,
    filename: str,
    unit: str,
    source: str,
    retrieved_at: datetime,
) -> list[Observation]:
    """CBOE 波动率指数历史 CSV（已落盘为 [[日期, 收盘], ...]）-> 观测。

    日期是 `MM/DD/YYYY`（CBOE 原样），不是 ISO —— 这点与其它两个源都不同。
    """
    key = series_key_cboe_index(filename)
    out: list[Observation] = []
    for index, row in enumerate(rows):
        if len(row) < 2:
            raise ObservationSourceError(f"{filename} 第 {index} 行不足两列：{row!r}")
        raw_day, value = row[0], row[1]
        try:
            day = datetime.strptime(str(raw_day), "%m/%d/%Y").date()
        except ValueError as exc:
            raise ObservationSourceError(
                f"{filename} 第 {index} 行日期不是 MM/DD/YYYY：{raw_day!r}（{exc}）"
            ) from None
        out.append(
            make_observation(
                series_key=key,
                day=day,
                value=value,
                unit=unit,
                source=source,
                retrieved_at=retrieved_at,
            )
        )
    if not out:
        raise ObservationSourceError(f"{filename} 解析后为空")
    return out


def from_yahoo(
    payload: dict,
    *,
    symbol: str,
    unit: str,
    source: str,
    retrieved_at: datetime,
) -> list[Observation]:
    """Yahoo chart 响应 -> 观测。空收盘价（`None`）跳过 —— 那不是观测。"""
    results = payload.get("chart", {}).get("result")
    if not results:
        raise ObservationSourceError(
            f"Yahoo {symbol} 响应无 result：{payload.get('chart', {}).get('error')}"
        )
    result = results[0]
    stamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    key = series_key_yahoo(symbol)
    out: list[Observation] = []
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        out.append(
            make_observation(
                series_key=key,
                day=datetime.fromtimestamp(stamp, tz=timezone.utc).date(),
                value=close,
                unit=unit,
                source=source,
                retrieved_at=retrieved_at,
            )
        )
    if not out:
        raise ObservationSourceError(f"Yahoo {symbol} 响应里没有有效收盘价")
    return out


def collect(
    directory: Path,
    sources: dict,
    *,
    retrieved_at: datetime | None = None,
) -> list[Observation]:
    """把一个落盘目录（如 `data/raw/2026-10-15/`）里的全部 payload 读成观测流。

    `retrieved_at` 不传时逐文件取落盘时刻（每个文件的取回时刻本来就不同）。
    缺任何一个文件即报错 —— 不允许"少一个源也算成功"。
    """
    directory = Path(directory)
    out: list[Observation] = []

    for alias, spec in sources["fred"]["series"].items():
        path = directory / f"fred_{alias}.json"
        payload = _read_json(path)
        out.extend(
            from_fred(
                payload,
                alias=alias,
                unit=spec["unit"],
                source=f"fred:{spec['id']}",
                retrieved_at=_stamp(path, retrieved_at),
            )
        )

    cboe = sources["cboe"]
    for filename in cboe["index_csv_files"]:
        stem = filename.replace("_History.csv", "")
        path = directory / f"cboe_{stem}.json"
        rows = _read_json(path)
        out.extend(
            from_cboe_index(
                rows,
                filename=filename,
                unit=cboe["index_csv_unit"],
                source=f"cboe:{filename}",
                retrieved_at=_stamp(path, retrieved_at),
            )
        )

    for symbol, spec in sources["yahoo"]["symbols"].items():
        path = directory / f"yahoo_{yahoo_stem(symbol)}.json"
        payload = _read_json(path)
        out.extend(
            from_yahoo(
                payload,
                symbol=symbol,
                unit=spec["unit"],
                source=f"yahoo:{symbol}",
                retrieved_at=_stamp(path, retrieved_at),
            )
        )

    return out
