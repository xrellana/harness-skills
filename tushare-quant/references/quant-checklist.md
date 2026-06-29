# Quant Checklist

Use this before judging whether an A-share strategy result is meaningful.

## Data Integrity

- Confirm symbol, exchange suffix, sample period, frequency, and latest trade date.
- Confirm price adjustment method（复权方式）: qfq, hfq, or raw.
- Check missing days, zero volume, volume and turnover（量能、换手率）, suspensions（停牌）, ST status, and limit-up or limit-down days（涨跌停）.
- For single-stock reports, include `daily_basic` for turnover, volume ratio, PE, PB, market value, and valuation context（估值）.
- Include `moneyflow` when judging whether a price move has capital-flow confirmation.
- Include `adj_factor` when discussing adjusted prices, dividends, splits, or share conversions.
- Include `stk_limit` and `suspend_d` when discussing limit-up, limit-down, suspension, liquidity, or whether technical indicators may be distorted.
- Do not mix daily data with quarterly fundamentals without aligning publish dates.

## Single-stock Completeness

- Report max drawdown for the price path, not only interval return.
- Use `index_daily` to compare with a relevant benchmark such as CSI 300, CSI 500, CSI 1000, ChiNext, or an industry index（基准对比）.
- Use `fina_indicator` for ROE, revenue growth, net profit growth, margin context, and financial quality（财务）.
- State whether valuation and fundamentals support, contradict, or are missing from the technical signal.
- Put failed or unavailable endpoints in a data-gap section instead of silently dropping them.

## Backtest Integrity

- Avoid future leakage: never use data that was unavailable on the signal date.
- Include fees and a simple slippage assumption.
- State whether T+1, price limits, and suspensions are modeled.
- Report max drawdown, trade count, and sample length, not only total return.
- Compare with a benchmark or buy-and-hold when possible.

## Overfitting Checks

- Beware strategies tuned to one stock and one period.
- Split in-sample and out-of-sample periods for serious work.
- Prefer simple rules with economic intuition over complex rules that only fit history.
- Treat high return plus high turnover with suspicion until costs are modeled.

## Response Boundary

Say "historically performed well in this sample" instead of "works". Say "signal" instead of "prediction". Do not give investment instructions.
