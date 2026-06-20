"""A-share ticker mapping for JoinQuant-compatible exports."""

from __future__ import annotations

import re


class JoinQuantMappingError(RuntimeError):
    """Raised when a local ticker cannot be mapped to JoinQuant format."""


LOCAL_TO_JQ_EXCHANGE = {
    "SH": "XSHG",
    "SZ": "XSHE",
}
JQ_TO_LOCAL_EXCHANGE = {value: key for key, value in LOCAL_TO_JQ_EXCHANGE.items()}
JQ_EXCHANGES = set(LOCAL_TO_JQ_EXCHANGE.values())
TICKER_RE = re.compile(r"^(?P<code>\d{6})\.(?P<exchange>[A-Z]{2,4})$")


def map_ticker(ticker: str) -> str:
    """Map local A-share ticker formats to JoinQuant formats.

    Examples:
      600519.SH -> 600519.XSHG
      300750.SZ -> 300750.XSHE
      000001.SH -> 000001.XSHG
    """
    raw = str(ticker or "").strip().upper()
    match = TICKER_RE.match(raw)
    if not match:
        raise JoinQuantMappingError(f"股票代码格式无法识别: {ticker}")
    code = match.group("code")
    exchange = match.group("exchange")
    if exchange in JQ_EXCHANGES:
        return f"{code}.{exchange}"
    jq_exchange = LOCAL_TO_JQ_EXCHANGE.get(exchange)
    if jq_exchange is None:
        raise JoinQuantMappingError(f"暂不支持该交易所代码映射: {ticker}")
    return f"{code}.{jq_exchange}"


def mapping_preview(ticker: str) -> dict[str, str | bool]:
    """Return a non-throwing mapping preview for preflight screens."""
    try:
        return {"source_ticker": ticker, "mapped_ticker": map_ticker(ticker), "ok": True}
    except JoinQuantMappingError as exc:
        return {"source_ticker": ticker, "mapped_ticker": "", "ok": False, "error": str(exc)}


def unmap_ticker(ticker: str) -> str:
    """Map JoinQuant A-share tickers back to the local Vibe format.

    Examples:
      600519.XSHG -> 600519.SH
      300750.XSHE -> 300750.SZ
      600519.SH -> 600519.SH
    """
    raw = str(ticker or "").strip().upper()
    match = TICKER_RE.match(raw)
    if not match:
        raise JoinQuantMappingError(f"股票代码格式无法识别: {ticker}")
    code = match.group("code")
    exchange = match.group("exchange")
    if exchange in LOCAL_TO_JQ_EXCHANGE:
        return f"{code}.{exchange}"
    local_exchange = JQ_TO_LOCAL_EXCHANGE.get(exchange)
    if local_exchange is None:
        raise JoinQuantMappingError(f"暂不支持该聚宽交易所代码映射: {ticker}")
    return f"{code}.{local_exchange}"
