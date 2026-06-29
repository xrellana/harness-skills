"""Markdown report formatting for tushare-quant."""

from __future__ import annotations


def _last_signal(rows: list[dict[str, object]]) -> str:
    last = rows[-1]
    previous = rows[-2] if len(rows) > 1 else last
    signals = []
    if float(last["close"]) > float(last["ma20"]):
        signals.append("收盘价在 20 日均线上方，短期趋势偏强")
    else:
        signals.append("收盘价在 20 日均线下方，短期趋势偏弱")
    if float(last["macd_diff"]) > float(last["macd_dea"]) and float(previous["macd_diff"]) <= float(previous["macd_dea"]):
        signals.append("MACD 刚出现金叉")
    elif float(last["macd_diff"]) > float(last["macd_dea"]):
        signals.append("MACD 仍在多头区间")
    else:
        signals.append("MACD 尚未形成多头信号")
    if float(last["kdj_j"]) > 100:
        signals.append("KDJ 的 J 值偏高，短线可能过热")
    elif float(last["kdj_j"]) < 0:
        signals.append("KDJ 的 J 值偏低，短线可能超卖")
    return "；".join(signals)


def format_indicator_report(symbol: str, rows: list[dict[str, object]], source: str) -> str:
    first = rows[0]["trade_date"]
    last = rows[-1]
    change_pct = (float(last["close"]) / float(rows[0]["close"]) - 1.0) * 100.0
    return f"""# {symbol} 量化指标速览

数据来源: {source}
样本区间: {first} 至 {last["trade_date"]}

## 一句话结论
{_last_signal(rows)}。这只是基于历史价格的量化信号，不是买卖建议。

## 关键数据
- 最新收盘价: {last["close"]}
- 区间涨跌幅: {change_pct:.2f}%
- MA5 / MA20: {last["ma5"]} / {last["ma20"]}
- MACD DIF / DEA / 柱: {last["macd_diff"]} / {last["macd_dea"]} / {last["macd_hist"]}
- KDJ K / D / J: {last["kdj_k"]} / {last["kdj_d"]} / {last["kdj_j"]}

## 新手解释
- MA20: 近 20 个交易日平均价格，常用来观察短期趋势。
- MACD 金叉: DIF 从下往上穿过 DEA，通常表示动能转强，但会滞后。
- KDJ: 更敏感的短线指标，J 值太高或太低都可能只是短期情绪。

## 风险提示
- 单靠技术指标不能判断公司价值。
- 指标来自历史价格，不能保证未来收益。
- A 股存在涨跌停、停牌、T+1、流动性变化等交易限制。
"""


def format_backtest_report(
    symbol: str,
    strategy: str,
    rows: list[dict[str, object]],
    result: dict[str, object],
    source: str,
) -> str:
    return f"""# {symbol} 策略回测

数据来源: {source}
样本区间: {rows[0]["trade_date"]} 至 {rows[-1]["trade_date"]}
策略: {strategy}

## 回测结果
- 初始资金: {result["initial_cash"]}
- 期末权益: {result["final_equity"]}
- 总收益率: {result["total_return_pct"]}%
- 最大回撤: {result["max_drawdown_pct"]}%
- 交易次数: {result["trade_count"]}
- 手续费率假设: {result["fee_rate"]}

## 新手解释
- 总收益率: 这段历史里策略最后赚亏多少。
- 最大回撤: 从阶段高点跌到低点的最大跌幅，越接近 0 风险越低。
- 交易次数: 买入和卖出都算一次，太高会被手续费和滑点侵蚀。

## 结论边界
这个结果只说明策略在样本期内的历史表现。正式使用前还要检查手续费、滑点、涨跌停无法成交、停牌、复权方式、样本外表现和过拟合风险。
"""
