---
name: tushare-quant
description: Use when analyzing China A-share stocks or strategies with Tushare data, technical indicators, MACD, KDJ, moving averages, simple backtests, factor screens, market timing, valuation data, financial data, or beginner-friendly A股量化 explanations.
---

# Tushare Quant

## Overview

Use this for A-share quant analysis from Tushare Pro data. Outputs are research, not investment advice.

## Read First

- Read `references/script-guide.md` before running bundled scripts, importing helpers, setting up `.venv` or `.env`, or troubleshooting encoding/API behavior.
- Load `references/beginner-terms-zh.md` for beginners or term explanations.
- Load `references/a-share-rules.md` when execution realism, T+1, price limits, suspensions, ST risk, lots, fees, or slippage matter.
- Load `references/playbooks.md` for factor screens or endpoint planning beyond a single stock.
- Load `references/quant-checklist.md` before judging whether a strategy result is meaningful.

## Workflow

1. Restate the question as a measurable rule: symbol, date range, frequency, indicator, strategy, benchmark, and cost assumptions.
2. Fetch or load data using the script guide. Prefer forward-adjusted prices for trend/backtest work unless asked otherwise. Always sort bars by ascending `trade_date`.
3. Add MA, MACD, and KDJ indicators when doing technical analysis.
4. Single-stock reports must cover volume, turnover, max drawdown, valuation, financial quality, benchmark relative strength, adjustment method, limit-up/limit-down, suspension, and explicit data gaps.
5. Strategy reports must include total return, max drawdown, trade count, fees, modeled constraints, and missing real-world constraints.
6. Explain technical, valuation, risk, and liquidity terms in plain Chinese when they appear.
7. End with evidence boundaries: what the data supports, what is only a signal, and what cannot be concluded.

## Output Rules

- Always include data source, sample period, latest trade date, price adjustment method, and benchmark code when used.
- Single-stock analysis must say which major dimensions were covered and which Tushare endpoints failed or were unavailable. Do not silently omit missing `daily_basic`, `moneyflow`, `index_daily`, `fina_indicator`, `adj_factor`, `stk_limit`, or `suspend_d` data.
- Never say "buy", "sell", "must rise", "guaranteed", or give target-price instructions.
- Separate historical facts from interpretation.
- Explain MACD, KDJ, MA, return, drawdown, win rate, PE, PB, ROE, volume, turnover, and liquidity.
- Mention A-share constraints when relevant: T+1, price limits, suspension, ST risk, lots, fees, slippage, and survivorship bias.
- If a backtest ignores a real-world constraint, say so explicitly.

## Task Playbooks

- Individual technical report: read the script guide, use `tq.py analyze` or helpers, then summarize trend, momentum, volume/turnover, drawdown, PE/PB, ROE/growth, benchmark relative strength, adjustment status, limit/suspension checks, and data limits.
- Single-stock backtest: read the script guide, use `tq.py backtest` or `scripts/backtest.py`, compare against buy-and-hold if implemented manually, and state cost/slippage assumptions.
- Factor or screening request: load `references/playbooks.md`; build factors first, then fetch only needed Tushare endpoints.
- Any "is this strategy good?" request: load `references/quant-checklist.md` before concluding.

## References

- `references/script-guide.md`: scripts, inputs, setup, helper APIs, encoding, proxy behavior.
- `references/beginner-terms-zh.md`: beginner term explanations.
- `references/a-share-rules.md`: trading rules and modeling caveats.
- `references/quant-checklist.md`: leakage, overfitting, bias, and backtest checks.
- `references/playbooks.md`: analysis recipes and endpoint families.
