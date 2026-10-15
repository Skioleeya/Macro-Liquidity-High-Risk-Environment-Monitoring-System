"""面板落盘 / 读取（L2）。

格式：CSV，列序 = `contract.COLUMNS`，文件名 `panel_<as_of>.csv`。

为什么是 CSV 而不是 parquet / pickle：
  - 文本、可 diff、可用肉眼查。面板是全部下游统计的地基，"能看"比"紧凑"重要；
  - 读取时**重新过一遍 `make_panel`**，所以被手改坏的文件会立刻报错，
    而不是带着脏数据继续往下走（这正是"落盘再读"最容易静默失真的地方）。

写盘用临时文件 + 原子替换：避免中途失败留下半截面板，被后续读成"合法面板"。
`as_of` 只从文件名取 —— 不允许调用方另传一个，否则文件名与内容可能不一致。
"""

from __future__ import annotations

import csv
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from L2_归一化层.contract import COLUMNS, Panel, PanelError, PanelRow, make_panel

_NAME_PATTERN = re.compile(r"^panel_(\d{4}-\d{2}-\d{2})\.csv$")
_TRUE, _FALSE = "1", "0"


class PanelStoreError(RuntimeError):
    """面板文件不存在、格式不对，或内容违反不变量。"""


def panel_path(directory: Path, *, as_of: date) -> Path:
    return Path(directory) / f"panel_{as_of.isoformat()}.csv"


def write_panel(panel: Panel, *, directory: Path) -> Path:
    """写盘并返回文件路径。写入过程中失败不会留下半成品文件。"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = panel_path(directory, as_of=panel.as_of)
    tmp = target.with_name(target.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            # lineterminator 必须显式写成 "\n"：csv.writer 默认是 "\r\n"，
            # 而本仓约定换行为 LF（.gitattributes: * text=auto eol=lf）。
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(COLUMNS)
            for row in panel.rows:
                writer.writerow(
                    [
                        row.date.isoformat(),
                        row.series_key,
                        str(row.value),
                        row.unit,
                        _TRUE if row.fill_flag else _FALSE,
                        row.source_as_of.isoformat(),
                    ]
                )
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return target


def _parse_date(raw: str, *, lineno: int, column: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise PanelStoreError(f"第 {lineno} 行 {column} 不是 ISO 日期：{raw!r}（{exc}）") from None


def _parse_decimal(raw: str, *, lineno: int) -> Decimal:
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise PanelStoreError(f"第 {lineno} 行 value 不是十进制数：{raw!r}（{exc}）") from None


def read_panel(path: Path) -> Panel:
    """读回面板并**重新校验不变量**。文件名里的 as_of 是唯一真值来源。"""
    path = Path(path)
    match = _NAME_PATTERN.match(path.name)
    if match is None:
        raise PanelStoreError(
            f"面板文件名必须是 panel_<YYYY-MM-DD>.csv，收到 {path.name!r}"
        )
    if not path.is_file():
        raise PanelStoreError(f"面板文件不存在：{path}")
    as_of = date.fromisoformat(match.group(1))

    rows: list[PanelRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != list(COLUMNS):
            raise PanelStoreError(f"表头必须是 {list(COLUMNS)}，收到 {header}")
        for lineno, raw in enumerate(reader, start=2):
            if len(raw) != len(COLUMNS):
                raise PanelStoreError(
                    f"第 {lineno} 行有 {len(raw)} 列，期望 {len(COLUMNS)} 列：{raw}"
                )
            day, series_key, value, unit, fill_flag, source_as_of = raw
            if fill_flag not in (_TRUE, _FALSE):
                raise PanelStoreError(
                    f"第 {lineno} 行 fill_flag 只能是 {_TRUE!r} 或 {_FALSE!r}，收到 {fill_flag!r}"
                )
            rows.append(
                PanelRow(
                    date=_parse_date(day, lineno=lineno, column="date"),
                    series_key=series_key,
                    value=_parse_decimal(value, lineno=lineno),
                    unit=unit,
                    fill_flag=fill_flag == _TRUE,
                    source_as_of=_parse_date(source_as_of, lineno=lineno, column="source_as_of"),
                )
            )
    # 不变量复核：手改过的文件在这里就会炸，而不是被下游当合法数据用掉。
    # 统一包成 PanelStoreError —— 本模块对外只声明这一种异常，
    # 让调用方"按声明捕获"就能接住全部文件级问题（漏出别的类型等于声明不实）。
    try:
        return make_panel(rows, as_of=as_of)
    except PanelError as exc:
        raise PanelStoreError(f"面板文件 {path.name} 违反不变量：{exc}") from exc
