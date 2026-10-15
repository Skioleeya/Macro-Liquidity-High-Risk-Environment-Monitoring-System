"""HTTP 取回层（L0）。

职责边界：只按 URL 取回文本，不做任何解析、不认任何业务字段。
错误一律转成 RuntimeError 抛出，不返回空值。

敏感信息处理：
  URL 里带密钥时，调用方必须把密钥值放进 secrets，本层会把报错文本
  （含服务端回显的响应体）里的密钥全部替换掉；同时用 `from None` 切断
  异常链 —— urllib 的 HTTPError 对象自身持有带密钥的完整 URL，一旦被
  上层打印 traceback 就会泄漏。
"""

from __future__ import annotations

import urllib.error
import urllib.request

REDACTED = "***"


def _scrub(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def fetch_text(
    url: str, *, timeout: int, user_agent: str, secrets: tuple[str, ...] = ()
) -> str:
    secrets = tuple(secret for secret in secrets if secret)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            detail = ""
        tail = f" | {detail}" if detail else ""
        raise RuntimeError(_scrub(f"HTTP {exc.code} <- {url}{tail}", secrets)) from None
    except urllib.error.URLError as exc:
        reason = _scrub(str(exc.reason), secrets)
        raise RuntimeError(_scrub(f"连接失败 <- {url}: {reason}", secrets)) from None
    except TimeoutError:
        raise RuntimeError(_scrub(f"超时 <- {url}", secrets)) from None
