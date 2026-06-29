# Playbooks

## Individual Technical Report

Use when the user asks "分析某只股票", "MACD/KDJ 怎么样", or "近三年量化分析".

1. Fetch daily bars: daily close, high, low, volume; prefer forward-adjusted prices.
2. Compute MA5, MA20, MACD, KDJ.
3. Summarize trend, momentum, overbought or oversold risk.
4. Explain the terms in beginner Chinese.
5. State that this is not a valuation or investment recommendation.

## Single-stock Strategy Backtest

Use when the user provides a rule such as "MACD 金叉买入、死叉卖出".

1. Convert the sentence into an explicit signal rule.
2. Define execution price, fee, slippage, and date range.
3. Run the backtest and report return, max drawdown, trade count, and sample length.
4. Add benchmark comparison if benchmark data is available.
5. List missing real-world constraints.

## Factor Screen

Use when the user asks to find candidate stocks.

1. Translate natural language into factors: valuation, quality, growth, momentum, liquidity, or risk.
2. Fetch only required Tushare endpoint families, such as daily bars, daily_basic, fina_indicator, income, balancesheet, cashflow, moneyflow, and stock_basic.
3. Rank and filter transparently.
4. Output an observation list, not a buy list.
5. Explain every factor in plain Chinese.
