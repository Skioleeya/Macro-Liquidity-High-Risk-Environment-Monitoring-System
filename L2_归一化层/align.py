"""时间轴对齐（L2）。把各序列的观测投到交易日轴上，缺失点前向填充并**打标**。

填充语义（目前唯一支持的一种，由配置 `[align].policy` 声明）：

  - 轴上某天有该序列的真实观测  -> `fill_flag=False`，`source_as_of=该天`
  - 轴上某天没有                -> 取该序列**在它之前最近**的一条真实观测，
                                    `fill_flag=True`，`source_as_of=那条的日期`
  - 序列第一条真实观测**之前**的轴日 -> **不产生行**。禁止向后填充 —— 那是编造历史。
  - 序列最后一条观测**之后**的轴日   -> 一直填充到 `as_of`。
    是否可接受不在这里判断，交给 `staleness` 门禁（职责分离：这里只管"怎么填"，门禁管"能不能用"）。

为什么打标是硬要求：填充点如果被当成观测参与 Z-Score 与 Δ 计算，滚动统计量会被静默污染。
打标之后，L3 才有机会说"这个 Δ 只对周度更新节点有意义"。
"""

from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

from L1_接入层.contract import Observation
from L2_归一化层.contract import PanelRow


class AlignError(ValueError):
    """观测或时间轴不满足对齐前提。一律 fail fast。"""


def check_axis(axis: Sequence[date], *, as_of: date) -> None:
    """时间轴必须严格升序、不晚于 as_of、且**末元素就是 as_of**。

    末元素必须是 as_of：面板的意义就是"站在 as_of 看"，缺了最后一天等于答案里没有今天。
    """
    if not axis:
        raise AlignError("时间轴为空，无法对齐")
    previous: date | None = None
    for day in axis:
        if previous is not None and day <= previous:
            raise AlignError(f"时间轴必须严格升序且不重复：{previous} 之后出现 {day}")
        if day > as_of:
            raise AlignError(f"时间轴上的 {day} 晚于 as_of={as_of}")
        previous = day
    if axis[-1] != as_of:
        raise AlignError(f"时间轴末元素 {axis[-1]} 必须等于 as_of={as_of}")


def align_series(
    observations: Sequence[Observation],
    axis: Sequence[date],
    *,
    as_of: date,
) -> list[PanelRow]:
    """把**单个序列**的观测对齐到轴上，返回该序列的面板行（升序）。

    调用方负责保证 `observations` 同属一个 `series_key` 且已完成单位归一。
    """
    check_axis(axis, as_of=as_of)

    keys = {obs.series_key for obs in observations}
    if len(keys) > 1:
        raise AlignError(
            f"align_series 只接受单个序列的观测，收到 {len(keys)} 个：{sorted(keys)}"
        )
    if not keys:
        return []

    by_date: dict[date, Observation] = {}
    for obs in observations:
        if obs.date > as_of:
            raise AlignError(
                f"{obs.series_key} @ {obs.date} 晚于 as_of={as_of} —— "
                "面板不能包含决策日之后的观测"
            )
        if obs.date in by_date:
            raise AlignError(f"{obs.series_key} @ {obs.date} 出现重复观测")
        by_date[obs.date] = obs

    if not by_date:
        return []

    units = {obs.unit for obs in by_date.values()}
    if len(units) > 1:
        raise AlignError(
            f"{next(iter(keys))} 出现多种单位：{sorted(units)}"
            " —— 单位归一步骤没有生效"
        )

    key = next(iter(keys))
    timeline = sorted(by_date)  # 真实观测日，升序
    rows: list[PanelRow] = []
    cursor = 0
    current: Observation | None = None
    for day in axis:
        # 游标只前进：轴升序 + 观测升序 => 整体 O(len(axis) + len(timeline))
        while cursor < len(timeline) and timeline[cursor] <= day:
            current = by_date[timeline[cursor]]
            cursor += 1
        if current is None:
            continue  # 序列起点之前 —— 不造行
        rows.append(
            PanelRow(
                date=day,
                series_key=key,
                value=current.value,
                unit=current.unit,
                fill_flag=day != current.date,
                source_as_of=current.date,
            )
        )
    return rows


def align_all(
    observations_by_series: Mapping[str, Sequence[Observation]],
    axis: Sequence[date],
    *,
    as_of: date,
) -> list[PanelRow]:
    """按 series_key 升序逐个对齐，保证结果与输入顺序无关（可复现）。"""
    check_axis(axis, as_of=as_of)
    rows: list[PanelRow] = []
    for key in sorted(observations_by_series):
        rows.extend(align_series(observations_by_series[key], axis, as_of=as_of))
    return rows
