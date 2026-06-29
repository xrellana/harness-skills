"""Small, dependency-free technical indicators for A-share quant reports."""

from __future__ import annotations

from typing import Iterable


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 4)


def sma(values: list[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    result: list[float] = []
    running = 0.0
    for idx, value in enumerate(values):
        running += value
        if idx >= window:
            running -= values[idx - window]
        divisor = min(idx + 1, window)
        result.append(running / divisor)
    return result


def ema(values: list[float], span: int) -> list[float]:
    if span <= 0:
        raise ValueError("span must be positive")
    if not values:
        return []
    alpha = 2.0 / (span + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    diff = [fast_value - slow_value for fast_value, slow_value in zip(fast_ema, slow_ema)]
    dea = ema(diff, signal)
    hist = [(diff_value - dea_value) * 2.0 for diff_value, dea_value in zip(diff, dea)]
    return diff, dea, hist


def kdj(
    rows: list[dict[str, object]],
    window: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    if window <= 0:
        raise ValueError("window must be positive")

    k_values: list[float] = []
    d_values: list[float] = []
    j_values: list[float] = []
    previous_k = 50.0
    previous_d = 50.0

    for idx, row in enumerate(rows):
        start = max(0, idx - window + 1)
        window_rows = rows[start : idx + 1]
        highest = max(_as_float(item.get("high")) for item in window_rows)
        lowest = min(_as_float(item.get("low")) for item in window_rows)
        close = _as_float(row.get("close"))
        if highest == lowest:
            rsv = 50.0
        else:
            rsv = (close - lowest) / (highest - lowest) * 100.0
        current_k = previous_k * 2.0 / 3.0 + rsv / 3.0
        current_d = previous_d * 2.0 / 3.0 + current_k / 3.0
        current_j = 3.0 * current_k - 2.0 * current_d
        k_values.append(current_k)
        d_values.append(current_d)
        j_values.append(current_j)
        previous_k = current_k
        previous_d = current_d

    return k_values, d_values, j_values


def add_indicators(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    enriched = [dict(row) for row in rows]
    closes = [_as_float(row.get("close")) for row in enriched]
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    diff, dea, hist = macd(closes)
    k_values, d_values, j_values = kdj(enriched)

    for idx, row in enumerate(enriched):
        row["ma5"] = _round(ma5[idx])
        row["ma10"] = _round(ma10[idx])
        row["ma20"] = _round(ma20[idx])
        row["macd_diff"] = _round(diff[idx])
        row["macd_dea"] = _round(dea[idx])
        row["macd_hist"] = _round(hist[idx])
        row["kdj_k"] = _round(k_values[idx])
        row["kdj_d"] = _round(d_values[idx])
        row["kdj_j"] = _round(j_values[idx])
    return enriched
