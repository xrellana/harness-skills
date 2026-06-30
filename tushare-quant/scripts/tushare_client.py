"""Tushare access helpers.

The skill never stores tokens in tracked files. Put local credentials in
``tushare-quant/.env`` or set environment variables before using live data.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
from pathlib import Path
from typing import Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = SKILL_ROOT / ".env"
REQUIRED_BAR_FIELDS = ("trade_date", "open", "high", "low", "close", "vol")
TRADE_DATE_FALLBACK_ENDPOINTS = {"stk_limit", "suspend_d"}
TRANSIENT_HTTP_STATUSES = {502, 503, 504}
DATA_API_MAX_ATTEMPTS = 2


class TushareDataError(RuntimeError):
    """Raised when Tushare data is unavailable or shaped differently than expected."""


class BarsFetchResult:
    def __init__(self, rows: list[dict[str, object]], adjustment: str, warning: str = "") -> None:
        self.rows = rows
        self.adjustment = adjustment
        self.warning = warning


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
    return load_env_file(DEFAULT_ENV_FILE, override=True)


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
    if not records:
        return []
    missing = [field for field in REQUIRED_BAR_FIELDS if field not in records[0]]
    if missing:
        raise TushareDataError(f"Tushare bar response missing required columns: {', '.join(missing)}")

    rows = []
    for record in records:
        try:
            rows.append(
                {
                    "trade_date": str(record["trade_date"]),
                    "open": float(record["open"] or 0),
                    "high": float(record["high"] or 0),
                    "low": float(record["low"] or 0),
                    "close": float(record["close"] or 0),
                    "vol": float(record["vol"] or 0),
                }
            )
        except (TypeError, ValueError) as exc:
            raise TushareDataError(f"Tushare bar response contains invalid numeric data: {exc}") from exc
    return sorted(rows, key=lambda row: str(row["trade_date"]))


def _clean_record_value(value: object) -> object:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
    except TypeError:
        pass
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except ValueError:
            return value
    return value


def _frame_to_records(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    records = frame.to_dict("records")
    rows = [{str(key): _clean_record_value(value) for key, value in record.items()} for record in records]
    return sorted(rows, key=lambda row: str(row.get("trade_date") or row.get("end_date") or row.get("ann_date") or ""))


def _is_adjustment_data_error(exc: BaseException) -> bool:
    message = str(exc)
    return "adj_factor" in message or ("trade_date" in message and "columns" in message)


def _call_pro_bar(
    ts: object,
    ts_code: str,
    start_date: str,
    end_date: str,
    adj: str | None,
    api: object | None = None,
) -> object:
    kwargs = {
        "ts_code": ts_code,
        "adj": adj,
        "start_date": start_date,
        "end_date": end_date,
        "retry_count": 1,
    }
    if api is not None:
        kwargs["api"] = api
    captured_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_output), contextlib.redirect_stderr(captured_output):
            return ts.pro_bar(**kwargs)
    except Exception as exc:
        details = captured_output.getvalue().strip()
        if details:
            raise RuntimeError(f"{exc} {details}") from exc
        raise


def _call_daily(api: object, ts_code: str, start_date: str, end_date: str) -> object:
    if type(api).__name__ == "DataApi":
        token = getattr(api, "_DataApi__token")
        http_url = getattr(api, "_DataApi__http_url")
        return _query_data_api(
            api,
            token,
            "daily",
            {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date,
            },
            http_url,
        )
    return api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)


def _call_pro_api_endpoint(api: object, api_name: str, params: dict[str, object]) -> object:
    if type(api).__name__ == "DataApi":
        token = getattr(api, "_DataApi__token")
        http_url = getattr(api, "_DataApi__http_url")
        return _query_data_api(api, token, api_name, params, http_url)
    method = getattr(api, api_name)
    return method(**params)


def _filter_records_by_ts_code(rows: list[dict[str, object]], ts_code: str) -> list[dict[str, object]]:
    return [row for row in rows if not row.get("ts_code") or str(row.get("ts_code")) == ts_code]


def _query_endpoint_records(
    api: object,
    api_name: str,
    params: dict[str, object],
    ts_code_filter: str | None = None,
) -> list[dict[str, object]]:
    frame = _call_pro_api_endpoint(api, api_name, params)
    rows = _frame_to_records(frame)
    if ts_code_filter:
        return _filter_records_by_ts_code(rows, ts_code_filter)
    return rows


def _query_by_trade_dates(
    api: object,
    api_name: str,
    ts_code: str,
    trade_dates: Iterable[str],
    base_params: dict[str, object],
) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for trade_date in sorted({str(value) for value in trade_dates if value}):
        params = {"ts_code": ts_code, "trade_date": trade_date}
        if api_name == "suspend_d" and base_params.get("suspend_type"):
            params["suspend_type"] = base_params["suspend_type"]
        try:
            rows.extend(_query_endpoint_records(api, api_name, params, ts_code_filter=ts_code))
        except Exception as exc:
            warnings.append(f"{api_name} {trade_date}: {exc}")
    return rows, warnings


def _frame_from_data_api_payload(api_name: str, status_code: int, payload: dict[str, object], text: str) -> object:
    if status_code >= 400:
        message = payload.get("msg") if isinstance(payload, dict) else None
        raise TushareDataError(f"Tushare API {api_name} failed: {message or text[:200] or f'HTTP {status_code}'}")
    if payload.get("code") != 0:
        raise TushareDataError(f"Tushare API {api_name} failed: {payload.get('msg') or 'unknown error'}")

    data = payload.get("data") or {}
    fields = data.get("fields") or []
    items = data.get("items") or []
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Install pandas before fetching live Tushare data") from exc
    return pd.DataFrame(items, columns=fields)


def _query_data_api(api: object, token: str, api_name: str, params: dict[str, object], http_url: str) -> object:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Install requests before fetching live Tushare data") from exc

    request_params = dict(params)
    request_params.setdefault("ts_type_name", http_url)
    request_body = {
        "api_name": api_name,
        "token": token,
        "params": request_params,
        "fields": "",
    }
    response = None
    for attempt in range(DATA_API_MAX_ATTEMPTS):
        response = requests.post(
            f"{http_url.rstrip('/')}/{api_name}",
            json=request_body,
            timeout=getattr(api, "_DataApi__timeout", 30),
        )
        retry_available = attempt < DATA_API_MAX_ATTEMPTS - 1
        if response.status_code in TRANSIENT_HTTP_STATUSES and retry_available:
            continue
        try:
            payload = response.json()
        except ValueError as exc:
            if response.status_code in TRANSIENT_HTTP_STATUSES and retry_available:
                continue
            raise TushareDataError(
                f"Tushare API {api_name} returned HTTP {response.status_code} with non-JSON response: "
                f"{response.text[:200]}"
            ) from exc
        return _frame_from_data_api_payload(api_name, response.status_code, payload, response.text)

    raise TushareDataError(f"Tushare API {api_name} did not return a response")


def _result_from_frame(
    frame: object,
    ts_code: str,
    start_date: str,
    end_date: str,
    adjustment: str,
    warning: str = "",
) -> BarsFetchResult:
    rows = _frame_to_rows(frame)
    if not rows:
        raise TushareDataError(
            f"No Tushare bars returned for {ts_code} from {start_date} to {end_date}. "
            "Check the symbol, date range, token permissions, and proxy endpoint."
        )
    return BarsFetchResult(rows=rows, adjustment=adjustment, warning=warning)


def fetch_daily_bars_result(
    symbol: str,
    start_date: str,
    end_date: str,
    adj: str = "qfq",
    token_env: str = "TUSHARE_TOKEN",
    api_url: str | None = None,
    api_url_env: str = "TUSHARE_API_URL",
) -> BarsFetchResult:
    load_skill_env()
    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(f"Set {token_env} before fetching live Tushare data")

    try:
        import tushare as ts
    except ImportError as exc:
        raise RuntimeError("Install tushare before fetching live data: pip install tushare") from exc

    ts_code = normalize_symbol(symbol)
    resolved_api_url = api_url or os.environ.get(api_url_env)
    api = ts.pro_api(token)
    if resolved_api_url:
        # Tushare stores the endpoint on DataApi as a private attribute. Setting
        # the mangled name keeps SDK-level pro_bar usable with compatible proxies.
        setattr(api, "_DataApi__http_url", resolved_api_url)

    try:
        if adj:
            frame = _call_pro_bar(ts, ts_code, start_date, end_date, adj=adj, api=api)
        else:
            frame = _call_daily(api, ts_code, start_date, end_date)
        return _result_from_frame(frame, ts_code, start_date, end_date, adjustment=adj or "none")
    except TushareDataError:
        raise
    except Exception as exc:
        if adj and _is_adjustment_data_error(exc):
            try:
                frame = _call_daily(api, ts_code, start_date, end_date)
                return _result_from_frame(
                    frame,
                    ts_code,
                    start_date,
                    end_date,
                    adjustment="unadjusted-fallback",
                    warning=f"{adj} adjustment failed because adj_factor data was unavailable; used unadjusted daily bars.",
                )
            except Exception as fallback_exc:
                fallback_message = str(fallback_exc)
                if "Token" in fallback_message or "token" in fallback_message:
                    raise TushareDataError(fallback_message) from fallback_exc
                raise TushareDataError(
                    f"Tushare {adj} adjustment failed because adj_factor data was unavailable, "
                    f"and the unadjusted fallback also failed: {fallback_exc}"
                ) from fallback_exc
        raise TushareDataError(f"Tushare pro_bar failed for {ts_code} from {start_date} to {end_date}: {exc}") from exc


def _make_api(
    token_env: str,
    api_url: str | None,
    api_url_env: str,
) -> object:
    load_skill_env()
    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(f"Set {token_env} before fetching live Tushare data")
    try:
        import tushare as ts
    except ImportError as exc:
        raise RuntimeError("Install tushare before fetching live data: pip install tushare") from exc

    resolved_api_url = api_url or os.environ.get(api_url_env)
    api = ts.pro_api(token)
    if resolved_api_url:
        setattr(api, "_DataApi__http_url", resolved_api_url)
    return api


def fetch_analysis_bundle(
    symbol: str,
    start_date: str,
    end_date: str,
    benchmark: str = "000300.SH",
    trade_dates: Iterable[str] | None = None,
    token_env: str = "TUSHARE_TOKEN",
    api_url: str | None = None,
    api_url_env: str = "TUSHARE_API_URL",
) -> dict[str, object]:
    """Fetch optional datasets used by the comprehensive single-stock report."""

    api = _make_api(token_env, api_url, api_url_env)
    ts_code = normalize_symbol(symbol)
    bundle: dict[str, object] = {
        "daily_basic": [],
        "moneyflow": [],
        "benchmark": {"code": benchmark, "rows": []},
        "fina_indicator": [],
        "adj_factor": [],
        "stk_limit": [],
        "suspend_d": [],
        "warnings": [],
    }
    endpoint_params = {
        "daily_basic": {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
        "moneyflow": {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
        "index_daily": {"ts_code": benchmark, "start_date": start_date, "end_date": end_date},
        "fina_indicator": {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
        "adj_factor": {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
        "stk_limit": {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
        "suspend_d": {"ts_code": ts_code, "start_date": start_date, "end_date": end_date, "suspend_type": "S"},
    }

    warnings = bundle["warnings"]
    assert isinstance(warnings, list)
    for endpoint, params in endpoint_params.items():
        try:
            rows = _query_endpoint_records(
                api,
                endpoint,
                params,
                ts_code_filter=ts_code if endpoint != "index_daily" else benchmark,
            )
        except Exception as exc:
            if endpoint in TRADE_DATE_FALLBACK_ENDPOINTS and trade_dates:
                rows, fallback_warnings = _query_by_trade_dates(api, endpoint, ts_code, trade_dates, params)
                warnings.append(f"{endpoint}: range query failed ({exc}); used trade_date fallback")
                warnings.extend(fallback_warnings)
            else:
                warnings.append(f"{endpoint}: {exc}")
                rows = []

        if endpoint == "index_daily":
            bundle["benchmark"] = {"code": benchmark, "rows": rows}
        else:
            bundle[endpoint] = rows
    return bundle


def fetch_daily_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    adj: str = "qfq",
    token_env: str = "TUSHARE_TOKEN",
    api_url: str | None = None,
    api_url_env: str = "TUSHARE_API_URL",
) -> list[dict[str, object]]:
    result = fetch_daily_bars_result(
        symbol,
        start_date,
        end_date,
        adj=adj,
        token_env=token_env,
        api_url=api_url,
        api_url_env=api_url_env,
    )
    return result.rows


def ensure_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    data = sorted([dict(row) for row in rows], key=lambda row: str(row.get("trade_date", "")))
    if not data:
        raise ValueError("no market data rows were returned")
    return data
