# Quant Checklist

Use this before judging whether an A-share strategy result is meaningful.

## Data Integrity

- Confirm symbol, exchange suffix, sample period, frequency, and latest trade date.
- Confirm price adjustment method: qfq, hfq, or raw.
- Check missing days, zero volume, suspensions, ST status, and limit-up or limit-down days.
- Do not mix daily data with quarterly fundamentals without aligning publish dates.

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
