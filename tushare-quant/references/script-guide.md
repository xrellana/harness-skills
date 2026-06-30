# Script Guide

Read this before running bundled scripts or importing helper functions from `tushare-quant/scripts`.

## Runtime Setup

Use a skill-local virtual environment at `tushare-quant/.venv`. If it is missing, create it and install the bundled dependencies before running live-data scripts:

```powershell
py -m venv tushare-quant\.venv
tushare-quant\.venv\Scripts\python.exe -m pip install -r tushare-quant\requirements.txt
```

```bash
python3 -m venv tushare-quant/.venv
tushare-quant/.venv/bin/python -m pip install -r tushare-quant/requirements.txt
```

Use system Python only to create the virtual environment. Do not run the bundled scripts with global Python unless explicitly troubleshooting environment setup.

## Credentials And API URL

Harness reads `TUSHARE_TOKEN` and `TUSHARE_API_URL` only from `tushare-quant/.env`. Use `tushare-quant/.env.example` as the template; never commit the real `.env` file.

Put `TUSHARE_TOKEN=...` in `.env` for live data. Put `TUSHARE_API_URL=...` in `.env` only when using a DataApi-compatible reverse proxy that supports the endpoints the SDK calls.

If the token is unavailable, use `--source sample` only for tool validation and say clearly that sample data is not market data.

## Encoding

This skill and its references are UTF-8. On Windows PowerShell, read Chinese files with explicit UTF-8, for example:

```powershell
Get-Content -Encoding UTF8 tushare-quant\references\beginner-terms-zh.md
```

`scripts/tq.py` configures its stdout and stderr streams as UTF-8 at startup so Chinese report output does not depend on the Windows display language or active code page. If you wrap lower-level helpers in your own Python script and output still appears garbled, set `PYTHONIOENCODING=utf-8` for that command or run through a UTF-8 terminal.

## `scripts/tq.py`

Purpose: command-line entry point for fast first-pass reports.

Commands:

```powershell
tushare-quant\.venv\Scripts\python.exe tushare-quant\scripts\tq.py analyze --symbol 600519.SH --start 20230101 --end 20261231
tushare-quant\.venv\Scripts\python.exe tushare-quant\scripts\tq.py backtest --symbol 600519.SH --strategy macd --start 20230101 --end 20261231
tushare-quant\.venv\Scripts\python.exe tushare-quant\scripts\tq.py sample
```

```bash
tushare-quant/.venv/bin/python tushare-quant/scripts/tq.py analyze --symbol 600519.SH --start 20230101 --end 20261231
tushare-quant/.venv/bin/python tushare-quant/scripts/tq.py backtest --symbol 600519.SH --strategy macd --start 20230101 --end 20261231
tushare-quant/.venv/bin/python tushare-quant/scripts/tq.py sample
```

Required inputs for `analyze`: `--symbol`, `--start`, and `--end` for a real request. `--benchmark` defaults to `000300.SH`. `--source` accepts `auto`, `tushare`, or `sample`; default is `auto`.

Required inputs for `backtest`: `--symbol`, `--start`, `--end`, and an explicit strategy when the user names one. `--strategy` accepts `macd` or `ma-cross`; default is `macd`. `--initial-cash` and `--fee-rate` are optional assumptions that should be reported.

Required inputs for `sample`: none. It generates deterministic sample output for validation, not market analysis.

## `scripts/tushare_client.py`

Purpose: Tushare access, symbol normalization, environment loading, response cleanup, adjusted-price fallback, and supplemental endpoint bundles.

Use this import for one-off scripts:

```python
from scripts.tushare_client import fetch_daily_bars

rows = fetch_daily_bars("600519.SH", "20230101", "20261231")
```

Public helpers:

- `load_skill_env()`: load `tushare-quant/.env` as the harness configuration source.
- `normalize_symbol(symbol)`: add `.SH`, `.SZ`, or `.BJ` suffix when the user provides a plain A-share code.
- `fetch_daily_bars(symbol, start_date, end_date, adj="qfq", token_env="TUSHARE_TOKEN")`: return sorted daily bars with `trade_date`, `open`, `high`, `low`, `close`, and `vol`.
- `fetch_daily_bars_result(...)`: same inputs as `fetch_daily_bars`, but returns rows plus adjustment metadata such as `unadjusted-fallback`.
- `fetch_analysis_bundle(symbol, start_date, end_date, benchmark="000300.SH", trade_dates=None, token_env="TUSHARE_TOKEN")`: fetch supplemental data for comprehensive single-stock reports: `daily_basic`, `moneyflow`, `index_daily`, `fina_indicator`, `adj_factor`, `stk_limit`, and `suspend_d`.
- `ensure_rows(rows)`: sort rows and raise a clear error when no market data exists.

API behavior: `tq.py` fetches live daily bars through `ts.pro_bar(..., api=api)` so `adj="qfq"` can return forward-adjusted prices. Tushare's `daily` endpoint uses `ts_code`, `trade_date`, `start_date`, and `end_date`, but it returns unadjusted daily bars. Tushare documents `pro_bar` as an SDK integration interface rather than a raw HTTP endpoint.

When a DataApi-compatible proxy does not return usable `adj_factor` data for `qfq`, the helper retries with unadjusted daily bars and marks the data source as `unadjusted fallback: missing adj_factor`. Treat those reports as unadjusted-price analysis and mention that adjusted-price data was unavailable.

## `scripts/indicators.py`

Purpose: dependency-free technical indicators for daily bars.

Required inputs for `add_indicators(rows)`: iterable rows sorted or sortable by the caller, with `close`, `high`, and `low` values. It returns copied rows enriched with `ma5`, `ma10`, `ma20`, `macd_diff`, `macd_dea`, `macd_hist`, `kdj_k`, `kdj_d`, and `kdj_j`.

## `scripts/backtest.py`

Purpose: minimal long-only backtesting for first-pass strategy checks.

Required inputs for `run_signal_backtest(rows, signals, initial_cash=100000.0, fee_rate=0.001)`: market rows with `close`, a same-length signal sequence where truthy means long and falsy means cash, initial cash, and fee rate. It returns initial cash, final equity, total return, max drawdown, trade count, fee rate, and an equity curve.

This backtester does not model T+1, price-limit execution failures, suspensions, slippage beyond `fee_rate`, or survivorship bias unless the caller adds that logic.

## `scripts/report.py`

Purpose: format beginner-friendly Chinese reports after data, indicators, and optional supplemental analysis are prepared.

Required inputs for `format_indicator_report(symbol, rows, source, analysis=None)`: indicator-enriched rows and a source label. Pass the `fetch_analysis_bundle(...)` output as `analysis` for comprehensive single-stock reports.

Required inputs for `format_backtest_report(symbol, strategy, rows, result, source)`: market rows, a strategy name, a backtest result from `run_signal_backtest(...)`, and a source label.
