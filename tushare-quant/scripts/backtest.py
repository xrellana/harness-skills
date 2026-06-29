"""Minimal long-only backtesting helpers for first-pass quant checks."""

from __future__ import annotations

from typing import Iterable


def _close(row: dict[str, object]) -> float:
    value = row.get("close")
    if value is None:
        raise ValueError("each row must include close")
    return float(value)


def _pct(value: float) -> float:
    return round(value * 100.0, 4)


def run_signal_backtest(
    rows: Iterable[dict[str, object]],
    signals: Iterable[int | bool],
    initial_cash: float = 100000.0,
    fee_rate: float = 0.001,
) -> dict[str, object]:
    data = list(rows)
    desired_positions = [1 if signal else 0 for signal in signals]
    if len(data) != len(desired_positions):
        raise ValueError("rows and signals must have the same length")
    if not data:
        raise ValueError("rows must not be empty")

    cash = float(initial_cash)
    shares = 0.0
    in_market = 0
    trade_count = 0
    peak = float(initial_cash)
    max_drawdown = 0.0
    equity_curve: list[dict[str, object]] = []

    for row, desired in zip(data, desired_positions):
        price = _close(row)
        if desired and not in_market:
            shares = (cash * (1.0 - fee_rate)) / price
            cash = 0.0
            in_market = 1
            trade_count += 1
        elif not desired and in_market:
            cash = shares * price * (1.0 - fee_rate)
            shares = 0.0
            in_market = 0
            trade_count += 1

        equity = cash + shares * price
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        max_drawdown = min(max_drawdown, drawdown)
        equity_curve.append(
            {
                "trade_date": row.get("trade_date"),
                "close": price,
                "position": in_market,
                "equity": round(equity, 2),
                "drawdown_pct": _pct(drawdown),
            }
        )

    final_equity = equity_curve[-1]["equity"]
    total_return = float(final_equity) / float(initial_cash) - 1.0
    return {
        "initial_cash": round(float(initial_cash), 2),
        "final_equity": round(float(final_equity), 2),
        "total_return_pct": _pct(total_return),
        "max_drawdown_pct": _pct(max_drawdown),
        "trade_count": trade_count,
        "fee_rate": fee_rate,
        "equity_curve": equity_curve,
    }
