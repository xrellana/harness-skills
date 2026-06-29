"""CLI entry point for tushare-quant."""

from __future__ import annotations

import argparse
import math
import os
from datetime import date, timedelta

import backtest
import indicators
import report
import tushare_client


def make_sample_rows(days: int = 90) -> list[dict[str, object]]:
    start = date(2024, 1, 2)
    rows = []
    price = 10.0
    current = start
    idx = 0
    while len(rows) < days:
        if current.weekday() < 5:
            drift = 0.015 + math.sin(idx / 4.0) * 0.08
            price = max(1.0, price + drift)
            high = price + 0.18
            low = price - 0.22
            rows.append(
                {
                    "trade_date": current.strftime("%Y%m%d"),
                    "open": round(price - 0.05, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(price, 2),
                    "vol": 100000 + idx * 1000,
                }
            )
            idx += 1
        current += timedelta(days=1)
    return rows


def load_rows(symbol: str, start: str, end: str, source: str) -> tuple[list[dict[str, object]], str]:
    if source == "sample" or (source == "auto" and not os.environ.get("TUSHARE_TOKEN")):
        return make_sample_rows(), "sample-data"
    rows = tushare_client.fetch_daily_bars(symbol, start, end)
    return tushare_client.ensure_rows(rows), "tushare"


def build_signals(rows: list[dict[str, object]], strategy: str) -> list[int]:
    if strategy == "macd":
        return [1 if float(row["macd_diff"]) > float(row["macd_dea"]) else 0 for row in rows]
    if strategy == "ma-cross":
        return [1 if float(row["ma5"]) > float(row["ma20"]) else 0 for row in rows]
    raise ValueError(f"unknown strategy: {strategy}")


def command_analyze(args: argparse.Namespace) -> str:
    rows, source = load_rows(args.symbol, args.start, args.end, args.source)
    enriched = indicators.add_indicators(rows)
    return report.format_indicator_report(args.symbol, enriched, source)


def command_backtest(args: argparse.Namespace) -> str:
    rows, source = load_rows(args.symbol, args.start, args.end, args.source)
    enriched = indicators.add_indicators(rows)
    signals = build_signals(enriched, args.strategy)
    result = backtest.run_signal_backtest(
        enriched,
        signals,
        initial_cash=args.initial_cash,
        fee_rate=args.fee_rate,
    )
    return report.format_backtest_report(args.symbol, args.strategy, enriched, result, source)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A-share quant analysis using Tushare data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_data_args(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--symbol", default="600519.SH", help="A-share code, e.g. 600519.SH")
        command_parser.add_argument("--start", default="20230101", help="Start date, YYYYMMDD")
        command_parser.add_argument("--end", default=date.today().strftime("%Y%m%d"), help="End date, YYYYMMDD")
        command_parser.add_argument("--source", choices=["auto", "tushare", "sample"], default="auto")

    analyze_parser = subparsers.add_parser("analyze", help="Generate a beginner-friendly indicator report")
    add_data_args(analyze_parser)

    backtest_parser = subparsers.add_parser("backtest", help="Run a simple long-only strategy backtest")
    add_data_args(backtest_parser)
    backtest_parser.add_argument("--strategy", choices=["macd", "ma-cross"], default="macd")
    backtest_parser.add_argument("--initial-cash", type=float, default=100000.0)
    backtest_parser.add_argument("--fee-rate", type=float, default=0.001)

    sample_parser = subparsers.add_parser("sample", help="Run both demo reports using deterministic sample data")
    sample_parser.add_argument("--symbol", default="SAMPLE")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "analyze":
        output = command_analyze(args)
    elif args.command == "backtest":
        output = command_backtest(args)
    elif args.command == "sample":
        analyze_args = argparse.Namespace(symbol=args.symbol, start="20240101", end="20241231", source="sample")
        backtest_args = argparse.Namespace(
            symbol=args.symbol,
            start="20240101",
            end="20241231",
            source="sample",
            strategy="macd",
            initial_cash=100000.0,
            fee_rate=0.001,
        )
        output = command_analyze(analyze_args) + "\n\n---\n\n" + command_backtest(backtest_args)
    else:
        parser.error(f"unknown command: {args.command}")
    print(output)


if __name__ == "__main__":
    main()
