"""配置加载层（L0）。

职责边界：只做两件事 —— 读 .env 里的密钥、读 config/sources.toml 的结构常量。
不包含任何业务默认值；缺键、空值、格式错误一律抛 ConfigError（fail fast）。
"""

from __future__ import annotations

import tomllib
from pathlib import Path

MVP_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = MVP_ROOT / ".env"
SOURCES_PATH = MVP_ROOT / "config" / "sources.toml"

# 短于该长度的值不参与兜底擦除，避免把常见短串误伤。
MIN_SECRET_LENGTH = 8
REDACTED = "***"


class ConfigError(RuntimeError):
    """配置缺失或不合法。不静默兜底，直接失败。"""


def _parse_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ConfigError(f".env 不存在：{path}")
    parsed: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"{path.name} 第 {lineno} 行不是 KEY=VALUE 形式：{raw!r}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            raise ConfigError(f"{path.name} 第 {lineno} 行键为空：{raw!r}")
        parsed[key] = value
    return parsed


def get_secret(name: str) -> str:
    """取 .env 中的密钥。缺键或空值都抛错。"""
    env = _parse_env(ENV_PATH)
    if name not in env:
        raise ConfigError(f".env 缺少键 {name}")
    value = env[name]
    if not value:
        raise ConfigError(f".env 的 {name} 是空值")
    return value


def all_secrets() -> tuple[str, ...]:
    """所有够长的 .env 值。用于输出前的兜底擦除。"""
    return tuple(
        value for value in _parse_env(ENV_PATH).values() if len(value) >= MIN_SECRET_LENGTH
    )


def redact(text: str) -> str:
    """把 .env 里的任何密钥值从 text 中抹掉。输出边界上的最后一道闸。

    与 net.fetch_text 的 secrets 参数是两层防护：那一层只擦确知的密钥，
    这一层兜住任何漏网的路径。
    """
    for secret in all_secrets():
        text = text.replace(secret, REDACTED)
    return text


def load_sources() -> dict:
    """加载数据源结构常量。"""
    if not SOURCES_PATH.is_file():
        raise ConfigError(f"配置文件不存在：{SOURCES_PATH}")
    with SOURCES_PATH.open("rb") as handle:
        return tomllib.load(handle)


def raw_dir() -> Path:
    """按配置返回原始数据落盘目录，并确保存在。"""
    target = MVP_ROOT / load_sources()["output"]["raw_dir"]
    target.mkdir(parents=True, exist_ok=True)
    return target
