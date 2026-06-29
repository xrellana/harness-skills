# A-share Rules and Modeling Caveats

Use this reference before modeling live-like A-share strategies.

- T+1: stocks bought today normally cannot be sold until the next trading day.
- Price limits: common A-shares usually have daily price limits; ST, STAR Market, ChiNext, and Beijing Stock Exchange rules can differ.
- Suspensions: suspended stocks cannot trade even if a signal says buy or sell.
- Lot size: A-share buy orders are usually in board lots of 100 shares; sells can have odd lots.
- Fees: include commission, transfer fee where applicable, and stamp duty on sells where applicable.
- Slippage: close-price fills are optimistic when volume is low or the signal trades many stocks.
- Adjustment: use forward-adjusted prices for continuous technical analysis unless the research question requires raw prices.
- ST and delisting risk: flag ST, *ST, delisting warnings, and very low liquidity before treating a signal as usable.
- Benchmarks: compare strategies with relevant indexes such as CSI 300, CSI 500, CSI 1000, ChiNext, or an industry index when possible.
