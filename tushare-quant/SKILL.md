---
name: tushare-quant
description: Use when analyzing China A-share stocks or strategies with Tushare data, technical indicators, MACD, KDJ, moving averages, simple backtests, factor screens, market timing, valuation data, financial data, or beginner-friendly A股量化 explanations.
---

# Tushare Quant

## Overview

Use this skill to turn Tushare Pro data into disciplined, beginner-friendly A-share quant analysis. Treat every output as research, not investment advice.

## Quick Start

Use the bundled CLI when the user wants a fast first pass:

```bash
python tushare-quant/scripts/tq.py analyze --symbol 600519.SH --start 20230101 --end 20261231
python tushare-quant/scripts/tq.py backtest --symbol 600519.SH --strategy macd --start 20230101 --end 20261231
python tushare-quant/scripts/tq.py sample
```

Live data requires `TUSHARE_TOKEN`. The bundled Python scripts automatically load `tushare-quant/.env` before fetching data, so local users can put `TUSHARE_TOKEN=...` there instead of configuring Codex settings. Use `tushare-quant/.env.example` as the template; never commit the real `.env` file. External environment variables take precedence over values in `.env`, and `--api-url` takes precedence over `TUSHARE_API_URL`.

Reverse-proxy deployments can set `TUSHARE_API_URL` in `.env`, export it in the shell, or pass `--api-url https://your-proxy.example/api`. If the token is unavailable, use `--source sample` only for tool validation and say clearly that sample data is not market data.

Encoding note: this skill and its references are UTF-8. On Windows PowerShell, read Chinese files with explicit UTF-8, for example `Get-Content -Encoding UTF8 tushare-quant\references\beginner-terms-zh.md`. If Python command output appears garbled in a terminal, set `PYTHONIOENCODING=utf-8` for that command or run through a UTF-8 terminal.

API note: `tq.py` fetches live daily bars through `ts.pro_bar(..., api=api)` so `adj="qfq"` can return forward-adjusted prices. Tushare's `daily` endpoint uses `ts_code`, `trade_date`, `start_date`, and `end_date`, but it returns unadjusted daily行情. Tushare documents `pro_bar` as an SDK integration interface rather than a raw HTTP endpoint, so use `TUSHARE_API_URL` only with a DataApi-compatible reverse proxy that supports the endpoints the SDK calls.

When a DataApi-compatible proxy does not return usable `adj_factor` data for `qfq`, the CLI retries with unadjusted daily bars and marks the data source as `unadjusted fallback: missing adj_factor`. Treat those reports as unadjusted-price analysis and mention that复权数据 was unavailable.

## Workflow

1. Restate the research question as a measurable rule: symbol, date range, data frequency, indicator, strategy, benchmark, and cost assumptions.
2. Fetch data through `scripts/tushare_client.py` or run `scripts/tq.py`. Use `TUSHARE_API_URL` or `--api-url` when the user has a non-official Tushare endpoint. Always sort bars by ascending `trade_date`.
3. Add indicators with `scripts/indicators.py`. Prefer forward-adjusted prices for trend and backtest work unless the user asks otherwise.
4. For strategies, run `scripts/backtest.py` and report total return, max drawdown, trade count, fee assumptions, and limitations.
5. Explain terms in plain Chinese. Load `references/beginner-terms-zh.md` when the user is a beginner or asks what a term means.
6. End with evidence boundaries: what the data supports, what is only a signal, and what cannot be concluded.

## Output Rules

- Always include data source, sample period, and latest trade date.
- Never say "buy", "sell", "must rise", "guaranteed", or give target prices as instructions.
- Separate historical facts from interpretation.
- Explain MACD, KDJ, MA, return, drawdown, win rate, PE, PB, ROE, volume, turnover, and liquidity when they appear.
- Mention A-share constraints: T+1, price limits, suspension, ST risk, lots, fees, slippage, and survivorship bias when relevant.
- If a backtest ignores a real-world constraint, say so explicitly.

## Task Playbooks

- Individual technical report: use `tq.py analyze`, then summarize trend, momentum, overbought/oversold risk, and data limits.
- Single-stock strategy backtest: use `tq.py backtest`, compare against buy-and-hold if implemented manually, and state cost/slippage assumptions.
- Factor or screening request: load `references/playbooks.md`; build the factor list first, then fetch only the needed Tushare endpoints.
- Any "is this strategy good?" request: load `references/quant-checklist.md` before concluding.

## References

- `references/beginner-terms-zh.md`: plain Chinese explanations of common market and quant terms.
- `references/a-share-rules.md`: A-share trading rules and modeling caveats.
- `references/quant-checklist.md`: checks for future leakage, overfitting, survivorship bias, and backtest quality.
- `references/playbooks.md`: reusable analysis recipes and suggested Tushare endpoint families.
