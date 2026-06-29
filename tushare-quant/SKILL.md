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

Live data requires `TUSHARE_TOKEN`. If the token is unavailable, use `--source sample` only for tool validation and say clearly that sample data is not market data.

## Workflow

1. Restate the research question as a measurable rule: symbol, date range, data frequency, indicator, strategy, benchmark, and cost assumptions.
2. Fetch data through `scripts/tushare_client.py` or run `scripts/tq.py`. Always sort bars by ascending `trade_date`.
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
