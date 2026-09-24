# Source registry

Date accessed: 2026-09-23. Social and video sources are idea generators. None were independently verified. None are evidence of an edge.

## Required references

| Source | URL | Core claim as accessed | How it was used | Confidence | Verified |
| --- | --- | --- | --- | --- | --- |
| DaviddTech, "I Built an INSANELY Profitable AI Hedge Fund" | https://www.youtube.com/watch?v=FbuYWdwA_wU | A Claude plus TradingKit workflow backtests Pine Script and can pause a strategy | Took the research-loop and pause-on-degradation ideas. Rejected the profit framing and the Pine search | Low | No |
| gwrx2005, Medium | https://medium.com/@gwrx2005/from-trading-bot-to-trading-agent-how-to-build-an-ai-based-investment-system-313d4c370c60 | Multi-agent roles, LLM news reading, reinforcement learning | Took the role split. Kept the LLM and any RL policy off the order path | Low | No |
| Reddit r/Trading 1rsuokt | https://www.reddit.com/r/Trading/comments/1rsuokt/how_do_people_build_ai_systems_that_trade/ | Page timed out. Not read | Not used as evidence. A similarly titled thread was read instead | None | No |
| Reddit r/ai_trading 1rsumui | https://www.reddit.com/r/ai_trading/comments/1rsumui/how_do_people_build_ai_systems_that_trade/ | Practitioners emphasize data quality, narrow targets, and costs | Treated as unverified opinion | Low | No |
| DaviddTech GPT plus TradingView | https://www.youtube.com/watch?v=rQRs6DdnB6A | Many strategies were generated in one sitting, then incubated | Took incubation before capital. Refused the search procedure as a multiple-testing failure | Low | No |
| Execution-bot video NWK7rbDeGcE | https://www.youtube.com/watch?v=NWK7rbDeGcE | Claude plus an exchange MCP, a ledger, and a warning about one-loss rules | Took the ledger and the one-loss warning. Rejected LLM-sent orders | Low | No |

## Design inputs

| Source | URL | Core claim as used | How it was used | Confidence | Verified |
| --- | --- | --- | --- | --- | --- |
| Jegadeesh 1990 | https://doi.org/10.1111/j.1540-6261.1990.tb05110.x | Short-horizon reversal exists in historical returns | Named the phenomenon. Did not copy a return number | Medium, citation only | No, full text not re-read this session |
| Lehmann 1990 | https://doi.org/10.2307/2937816 | Weekly reversal | Same as above | Medium, citation only | No |
| Bid-ask bounce literature | https://doi.org/10.1080/07350015.1997.10524715 | A large share of short-horizon reversal profit is the spread | Made the stress model and the liquidity gate mandatory | Medium | Abstract read |
| NY Fed Staff Report 513 | https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr513.html | A residual reversal profit may remain after decomposition | Held as a hypothesis to retest, not a result to import | Medium | Staff report page read in part |
| Ball and Brown 1968; Bernard and Thomas 1989/1990 | standard citations | Post-earnings drift | Reserve program only. Not implemented | Medium, citation only | No |
| Bailey and López de Prado, deflated Sharpe | https://doi.org/10.3905/jpm.2014.40.5.094 | Multiple trials inflate Sharpe | Implemented a penalty. It does not certify an edge | Medium | Formula implemented from the published method, not re-derived from the PDF this session |
| Alpaca paper trading | https://docs.alpaca.markets/us/docs/paper-trading | Paper and live are separate hosts and keys. Paper fills are simulated and omit borrow fees | Paper adapter only. Borrow is modeled locally | High for the docs that were read | Yes, docs |
| Alpaca market data FAQ | https://docs.alpaca.markets/us/docs/market-data-faq | Free data is IEX, about 2.5 percent of volume | IEX is rejected as the sole price for a cost conclusion | High for the docs that were read | Yes, docs |
| TradingView charting libraries | https://www.tradingview.com/free-charting-libraries/ | Lightweight Charts is Apache 2.0 and allowed for personal use. Advanced Charts are not offered for personal or hobby use | Workstation uses Lightweight Charts and prints the attribution | High | Yes, licensing page |
| Lightweight Charts repository | https://github.com/tradingview/lightweight-charts/ | Apache 2.0 plus a TradingView attribution notice | Attribution link is in the chart workspace | High | Yes, repository license |
