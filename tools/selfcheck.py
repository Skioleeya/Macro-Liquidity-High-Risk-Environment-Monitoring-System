"""单位与脱敏自检（验证入口，非分层）。

用法（在**仓库根目录**下）：
    python -m tools.selfcheck
    python -m tools.selfcheck --skip-network

退出码：任一检查失败即 1。本脚本自带"检查器空转"自测 ——
会故意塞一个必然失败的用例，确认它确实被记为 FAIL。
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from L0_基元层 import net
from L0_基元层.config import ConfigError, get_secret, load_sources, raw_dir, redact
from L0_基元层.units import UnitError, convert, registered
from L1_接入层.derive.net_liquidity import SIGN_MINUS, SIGN_PLUS, net_liquidity
from L1_接入层.sources import fred
from tools.checkkit import CheckKit

# 假密钥：只用于验证擦除是否生效，不对应任何真实凭据。
FAKE_SECRET = "deadbeefcafe1234deadbeefcafe1234"


def _declared_units(sources: dict) -> dict[str, str]:
    """收集配置里所有被声明的单位：{描述: 单位令牌}。"""
    declared: dict[str, str] = {}
    for alias, spec in sources["fred"]["series"].items():
        declared[f"fred.{alias}"] = spec["unit"]
    declared["cboe.ratios"] = sources["cboe"]["ratios"]["unit"]
    declared["cboe.index_csv"] = sources["cboe"]["index_csv_unit"]
    for symbol, spec in sources["yahoo"]["symbols"].items():
        declared[f"yahoo.{symbol}"] = spec["unit"]
    declared["units.net_liquidity_target"] = sources["units"]["net_liquidity_target"]
    return declared


def _latest_raw() -> Path:
    base = raw_dir()
    dirs = sorted((d for d in base.iterdir() if d.is_dir()), key=lambda d: d.name)
    if not dirs:
        raise RuntimeError(f"没有落盘数据，请先跑 python -m tools.fetch_all（{base}）")
    return dirs[-1]


def _latest_value(directory: Path, alias: str) -> float:
    payload = json.loads((directory / f"fred_{alias}.json").read_text(encoding="utf-8"))
    return float(payload["observations"][0]["value"])


def main() -> int:
    parser = argparse.ArgumentParser(description="单位与脱敏自检")
    parser.add_argument("--skip-network", action="store_true", help="跳过需要联网的检查")
    args = parser.parse_args()

    sources = load_sources()
    declared = _declared_units(sources)
    kit = CheckKit("单位自检")

    print("=== 单位自检 ===")

    kit.check("检查器非空转自测", kit.selftest)

    def units_registered() -> str:
        known = registered()
        unknown = {k: v for k, v in declared.items() if v not in known}
        if unknown:
            raise UnitError(f"配置声明了未登记的单位：{unknown}")
        return f"{len(declared)} 处声明全部已登记（共 {len(known)} 个可用令牌）"

    kit.check("配置声明的单位都已登记", units_registered)

    def within_family() -> str:
        got = convert(1, "USD_BILLION", "USD_MILLION")
        if got != Decimal(1000):
            raise AssertionError(f"1 十亿应等于 1000 百万，得到 {got}")
        back = convert(got, "USD_MILLION", "USD_BILLION")
        if back != Decimal(1):
            raise AssertionError(f"往返换算应回到 1，得到 {back}")
        return "1 USD_BILLION -> 1000 USD_MILLION -> 1 USD_BILLION"

    kit.check("族内换算与往返一致", within_family)

    def cross_family_rejected() -> str:
        for src, dst in [("USD_MILLION", "PERCENT"), ("INDEX_POINT", "USD_BILLION")]:
            try:
                convert(1, src, dst)
            except UnitError:
                continue
            raise AssertionError(f"跨族换算 {src} -> {dst} 竟然通过了")
        return "USD_MILLION->PERCENT、INDEX_POINT->USD_BILLION 均被拒绝"

    kit.check("跨族换算必须被拒绝", cross_family_rejected)

    def unknown_rejected() -> str:
        try:
            convert(1, "USD_MILLION", "USD_SQUILLION")
        except UnitError:
            return "未登记令牌 USD_SQUILLION 被拒绝"
        raise AssertionError("未登记的单位令牌竟然通过了")

    kit.check("未登记单位必须被拒绝", unknown_rejected)

    if args.skip_network:
        print("（已跳过联网检查：FRED 权威单位对账）")
    else:

        def fred_units_agree() -> str:
            unit_map = sources["fred"]["units_short_map"]
            mismatches = []
            for alias, spec in sources["fred"]["series"].items():
                meta = fred.fetch_metadata(spec["id"], sources=sources)
                short = meta["units_short"]
                if short not in unit_map:
                    mismatches.append(f"{alias}: FRED 报了未知单位 {short!r}")
                elif unit_map[short] != spec["unit"]:
                    mismatches.append(
                        f"{alias}: 配置 {spec['unit']} != FRED {unit_map[short]}"
                    )
            if mismatches:
                raise AssertionError("；".join(mismatches))
            return f"{len(sources['fred']['series'])} 个 FRED 序列与权威 units_short 一致"

        kit.check("配置单位 vs FRED 权威单位", fred_units_agree)

    def whitepaper_formula() -> str:
        directory = _latest_raw()
        target = sources["units"]["net_liquidity_target"]
        walcl_unit = sources["fred"]["series"]["walcl"]["unit"]
        tga_unit = sources["fred"]["series"]["wtregon"]["unit"]
        rrp_unit = sources["fred"]["series"]["rrpontsyd"]["unit"]
        walcl = _latest_value(directory, "walcl")
        tga = _latest_value(directory, "wtregon")
        rrp = _latest_value(directory, "rrpontsyd")

        naive = Decimal(str(walcl)) - Decimal(str(tga)) - Decimal(str(rrp))
        correct = net_liquidity(
            [(walcl, walcl_unit, SIGN_PLUS), (tga, tga_unit, SIGN_MINUS), (rrp, rrp_unit, SIGN_MINUS)],
            target=target,
        )
        if naive == correct:
            raise AssertionError(
                "不换算与换算结果相同 —— 说明本检查无法区分两种算法（检查空转）"
            )
        gap = abs(naive - correct)
        ratio = gap / correct * 100
        return (
            f"不换算={naive:,.1f} vs 换算后={correct:,.0f} {target}，"
            f"差 {gap:,.1f}（当前占 {ratio:.4f}%）"
        )

    kit.check("白皮书净值公式的换算差异可见", whitepaper_formula)

    def net_layer_hides_secret() -> str:
        """带对照组的脱敏检查：不传 secrets 时必须能看见密钥，传了必须看不见。"""
        http = sources["http"]
        url = f"https://api.stlouisfed.org/fred/series?series_id=NOPE&api_key={FAKE_SECRET}"

        try:
            net.fetch_text(url, timeout=http["timeout_seconds"], user_agent=http["user_agent"])
        except RuntimeError as exc:
            unguarded = str(exc)
        else:
            raise AssertionError("预期报错但没有报错，本检查无法成立")
        if FAKE_SECRET not in unguarded:
            raise AssertionError(
                "对照组没能检出密钥 —— 说明本检查根本检测不到泄漏，属空转"
            )

        try:
            net.fetch_text(
                url,
                timeout=http["timeout_seconds"],
                user_agent=http["user_agent"],
                secrets=(FAKE_SECRET,),
            )
        except RuntimeError as exc:
            guarded = str(exc)
        else:
            raise AssertionError("预期报错但没有报错，本检查无法成立")
        if FAKE_SECRET in guarded:
            raise AssertionError("传入 secrets 后密钥仍然出现在报错文本里")
        return "对照组可见 / 实测组已抹为 ***，两层差异成立"

    if args.skip_network:
        print("（已跳过联网检查：net 层报错脱敏）")
    else:
        kit.check("net 层报错不泄漏密钥（带对照组）", net_layer_hides_secret)

    def boundary_redact() -> str:
        env_name = sources["fred"]["api_key_env"]
        try:
            real = get_secret(env_name)
        except ConfigError:
            return f"{env_name} 未配置，跳过（非失败）"
        sample = f"2026-10-15 log: GET /fred/series?api_key={real} 200"
        if real in redact(sample):
            raise AssertionError(f"config.redact() 没能抹除 {env_name}")
        if redact(sample) == sample:
            raise AssertionError("redact() 没有改变文本，疑似空转")
        return "输出边界的兜底擦除生效"

    kit.check("输出边界兜底擦除生效", boundary_redact)

    return kit.report(redact=redact)


if __name__ == "__main__":
    sys.exit(main())
