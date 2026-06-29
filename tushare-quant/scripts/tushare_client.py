"""Tushare access helpers.

The skill never stores tokens in tracked files. Put local credentials in
``tushare-quant/.env`` or set environment variables before using live data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = SKILL_ROOT / ".env"


def _strip_env_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned


def load_env_file(path: str | os.PathLike[str] | None = None, override: bool = False) -> dict[str, str]:
    env_path = Path(path) if path is not None else DEFAULT_ENV_FILE
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        loaded[key] = _strip_env_value(value)

    for key, value in loaded.items():
        if override:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)
    return loaded


def load_skill_env() -> dict[str, str]:
    return load_env_file(DEFAULT_ENV_FILE)


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
    load_skill_env()
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
        # the mangled name keeps SDK-level pro_bar usable with compatible proxies.
        setattr(api, "_DataApi__http_url", resolved_api_url)
        frame = ts.pro_bar(
            api=api,
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
