"""Markdown report formatting for tushare-quant."""

from __future__ import annotations


def _as_float(value: object, default: float | None = None) -> float | None:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: object, suffix: str = "", digits: int = 2) -> str:
    number = _as_float(value)
    if number is None:
        return "缺失"
    return f"{number:.{digits}f}{suffix}"


def _latest(rows: object) -> dict[str, object] | None:
    if not isinstance(rows, list) or not rows:
        return None
    return sorted(rows, key=lambda row: str(row.get("trade_date") or row.get("end_date") or row.get("ann_date") or ""))[-1]


def _return_pct(rows: list[dict[str, object]]) -> float:
    return (float(rows[-1]["close"]) / float(rows[0]["close"]) - 1.0) * 100.0


def _max_drawdown_pct(rows: list[dict[str, object]]) -> float:
    peak = float(rows[0]["close"])
    max_drawdown = 0.0
    for row in rows:
        close = float(row["close"])
        peak = max(peak, close)
        if peak:
            max_drawdown = min(max_drawdown, close / peak - 1.0)
    return max_drawdown * 100.0


def _format_volume_section(rows: list[dict[str, object]], analysis: dict[str, object]) -> str:
    volumes = [_as_float(row.get("vol"), 0.0) or 0.0 for row in rows]
    latest_volume = volumes[-1]
    window = volumes[-20:] if len(volumes) >= 20 else volumes
    average_volume = sum(window) / len(window) if window else 0.0
    volume_ratio = latest_volume / average_volume if average_volume else 0.0
    zero_volume_days = sum(1 for value in volumes if value <= 0)
    latest_basic = _latest(analysis.get("daily_basic"))
    if latest_basic:
        basic_line = (
            f"- 换手率: {_fmt(latest_basic.get('turnover_rate'), '%')}；"
            f"量比: {_fmt(latest_basic.get('volume_ratio'))}"
        )
    else:
        basic_line = "- daily_basic 未返回: 无法判断换手率、量比和成交活跃度。"

    return f"""## 量能与换手
- 最新成交量: {_fmt(latest_volume, digits=0)}
- 20日均量口径: {_fmt(average_volume, digits=0)}；最新/均量: {_fmt(volume_ratio, digits=2)} 倍
- 零成交或疑似停牌交易日: {zero_volume_days}
{basic_line}
"""


def _format_valuation_section(analysis: dict[str, object]) -> str:
    latest_basic = _latest(analysis.get("daily_basic"))
    if not latest_basic:
        return """## 估值锚点
- daily_basic 未返回: 无法判断 PE、PB、总市值和流通市值。
"""
    return f"""## 估值锚点
- PE(TTM): {_fmt(latest_basic.get('pe_ttm'))}；PE: {_fmt(latest_basic.get('pe'))}；PB: {_fmt(latest_basic.get('pb'))}
- 总市值: {_fmt(latest_basic.get('total_mv'), ' 万元')}；流通市值: {_fmt(latest_basic.get('circ_mv'), ' 万元')}
"""


def _format_moneyflow_section(analysis: dict[str, object]) -> str:
    latest_flow = _latest(analysis.get("moneyflow"))
    if not latest_flow:
        return """## 资金流向
- moneyflow 未返回: 无法判断主力、大单、小单资金方向。
"""
    large_net = (
        (_as_float(latest_flow.get("buy_lg_amount"), 0.0) or 0.0)
        + (_as_float(latest_flow.get("buy_elg_amount"), 0.0) or 0.0)
        - (_as_float(latest_flow.get("sell_lg_amount"), 0.0) or 0.0)
        - (_as_float(latest_flow.get("sell_elg_amount"), 0.0) or 0.0)
    )
    net_amount = _as_float(latest_flow.get("net_mf_amount"))
    return f"""## 资金流向
- 主力资金净流入: {_fmt(large_net, ' 万元')}（大单 + 特大单口径）
- 全部主动买卖净流入: {_fmt(net_amount, ' 万元')}；日期: {latest_flow.get("trade_date", "缺失")}
"""


def _format_benchmark_section(rows: list[dict[str, object]], analysis: dict[str, object]) -> str:
    benchmark = analysis.get("benchmark") if isinstance(analysis.get("benchmark"), dict) else {}
    benchmark_code = benchmark.get("code", "000300.SH") if isinstance(benchmark, dict) else "000300.SH"
    benchmark_rows = benchmark.get("rows", []) if isinstance(benchmark, dict) else []
    if not isinstance(benchmark_rows, list) or len(benchmark_rows) < 2:
        return f"""## 基准对比
- index_daily 未返回: 无法与 {benchmark_code} 做同期相对强弱对比。
"""
    benchmark_return = _return_pct(benchmark_rows)
    stock_return = _return_pct(rows)
    return f"""## 基准对比
- 股票区间涨跌幅: {stock_return:.2f}%；{benchmark_code} 区间涨跌幅: {benchmark_return:.2f}%
- 相对强弱: {stock_return - benchmark_return:.2f} 个百分点
"""


def _format_financial_section(analysis: dict[str, object]) -> str:
    latest_financial = _latest(analysis.get("fina_indicator"))
    if not latest_financial:
        return """## 财务质量
- fina_indicator 未返回: 无法判断 ROE、营收增速和净利增速。
"""
    return f"""## 财务质量
- 报告期: {latest_financial.get("end_date", "缺失")}；公告日: {latest_financial.get("ann_date", "缺失")}
- ROE: {_fmt(latest_financial.get('roe'), '%')}；营收同比: {_fmt(latest_financial.get('or_yoy'), '%')}；净利同比: {_fmt(latest_financial.get('netprofit_yoy'), '%')}
- 毛利率: {_fmt(latest_financial.get('gross_margin'), '%')}
"""


def _count_limit_hits(rows: list[dict[str, object]], limit_rows: object) -> tuple[int, int]:
    if not isinstance(limit_rows, list):
        return 0, 0
    close_by_date = {str(row.get("trade_date")): float(row["close"]) for row in rows}
    up_hits = 0
    down_hits = 0
    for limit_row in limit_rows:
        close = close_by_date.get(str(limit_row.get("trade_date")))
        up_limit = _as_float(limit_row.get("up_limit"))
        down_limit = _as_float(limit_row.get("down_limit"))
        if close is None:
            continue
        if up_limit is not None and close >= up_limit * 0.999:
            up_hits += 1
        if down_limit is not None and close <= down_limit * 1.001:
            down_hits += 1
    return up_hits, down_hits


def _format_adjustment_and_constraints(rows: list[dict[str, object]], source: str, analysis: dict[str, object]) -> str:
    adj_rows = analysis.get("adj_factor")
    first_adj = adj_rows[0] if isinstance(adj_rows, list) and adj_rows else None
    last_adj = _latest(adj_rows)
    if first_adj and last_adj:
        adj_line = (
            f"- 价格复权: 默认按 qfq 前复权读取；复权因子: "
            f"{_fmt(first_adj.get('adj_factor'), digits=4)} -> {_fmt(last_adj.get('adj_factor'), digits=4)}"
        )
    else:
        adj_line = "- adj_factor 未返回: 只能说明当前价格序列来源，无法验证复权因子变化。"
    if "unadjusted fallback" in source:
        adj_line += "；本次数据已降级为未复权行情。"

    up_hits, down_hits = _count_limit_hits(rows, analysis.get("stk_limit"))
    suspend_rows = analysis.get("suspend_d")
    suspend_count = len(suspend_rows) if isinstance(suspend_rows, list) else 0
    return f"""## 复权与交易约束
{adj_line}
- 涨停触及: {up_hits}；跌停触及: {down_hits}
- 停牌记录: {suspend_count}
"""


def _format_data_gaps(analysis: dict[str, object]) -> str:
    warnings = analysis.get("warnings")
    if not isinstance(warnings, list) or not warnings:
        return ""
    lines = "\n".join(f"- {warning}" for warning in warnings)
    return f"""## 数据缺口
{lines}
"""


def _format_analysis_sections(rows: list[dict[str, object]], source: str, analysis: dict[str, object] | None) -> str:
    if analysis is None:
        analysis = {}
    sections = [
        f"""## 区间风险
- 区间最大回撤: {_max_drawdown_pct(rows):.2f}%
""",
        _format_volume_section(rows, analysis),
        _format_valuation_section(analysis),
        _format_moneyflow_section(analysis),
        _format_benchmark_section(rows, analysis),
        _format_financial_section(analysis),
        _format_adjustment_and_constraints(rows, source, analysis),
        _format_data_gaps(analysis),
    ]
    return "\n\n".join(section.rstrip() for section in sections if section).rstrip()


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


def format_indicator_report(
    symbol: str,
    rows: list[dict[str, object]],
    source: str,
    analysis: dict[str, object] | None = None,
) -> str:
    first = rows[0]["trade_date"]
    last = rows[-1]
    change_pct = (float(last["close"]) / float(rows[0]["close"]) - 1.0) * 100.0
    analysis_sections = _format_analysis_sections(rows, source, analysis)
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

{analysis_sections}

## 新手解释
- MA20: 近 20 个交易日平均价格，常用来观察短期趋势。
- MACD 金叉: DIF 从下往上穿过 DEA，通常表示动能转强，但会滞后。
- KDJ: 更敏感的短线指标，J 值太高或太低都可能只是短期情绪。
- 最大回撤: 样本内从阶段高点跌到后续低点的最大跌幅，用来衡量中途风险。
- 换手率/量比: 用来判断上涨或下跌是否有成交活跃度配合。
- PE/PB/ROE: 估值和经营质量锚点，不能单独作为结论。

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
