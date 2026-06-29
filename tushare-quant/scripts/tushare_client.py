"""Tushare access helpers.

The skill never stores tokens. Set TUSHARE_TOKEN in the environment before
using live data.
"""

from __future__ import annotations

import os
from typing import Iterable


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if "." in value:
        return value
    if value.startswith("6"):
        return f"{value}.SH"
    if value.startswith(("0", "3")):
        return f"{value}.SZ"
    if value.startswith(("4", "8", "9")):
        return f"{value}.BJ"
    return value


def _frame_to_rows(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    records = frame.to_dict("records")
    rows = []
    for record in records:
        rows.append(
            {
                "trade_date": str(record.get("trade_date", "")),
                "open": float(record.get("open", 0) or 0),
                "high": float(record.get("high", 0) or 0),
                "low": float(record.get("low", 0) or 0),
                "close": float(record.get("close", 0) or 0),
                "vol": float(record.get("vol", 0) or 0),
            }
        )
    return sorted(rows, key=lambda row: str(row["trade_date"]))


def fetch_daily_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    adj: str = "qfq",
    token_env: str = "TUSHARE_TOKEN",
    api_url: str | None = None,
    api_url_env: str = "TUSHARE_API_URL",
) -> list[dict[str, object]]:
    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(f"Set {token_env} before fetching live Tushare data")

    try:
        import tushare as ts
    except ImportError as exc:
        raise RuntimeError("Install tushare before fetching live data: pip install tushare") from exc

    ts.set_token(token)
    ts_code = normalize_symbol(symbol)
    resolved_api_url = api_url or os.environ.get(api_url_env)
    if resolved_api_url:
        api = ts.pro_api(token)
        # Tushare stores the endpoint on DataApi as a private attribute. Setting
        # the mangled name keeps pro_bar usable while allowing reverse proxies.
        setattr(api, "_DataApi__http_url", resolved_api_url)
        frame = ts.pro_bar(
            pro_api=api,
            ts_code=ts_code,
            adj=adj,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        frame = ts.pro_bar(ts_code=ts_code, adj=adj, start_date=start_date, end_date=end_date)
    return _frame_to_rows(frame)


def ensure_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    data = sorted([dict(row) for row in rows], key=lambda row: str(row.get("trade_date", "")))
    if not data:
        raise ValueError("no market data rows were returned")
    return data
