# Specialization thesis

Status: hypothesis. Not a strategy acceptance. Confidence before any market test: low.

## Phenomenon

Liquidity-conditioned short-horizon cross-sectional reversal in the most liquid US common stocks.

Working statement: among names that already pass a dollar-volume floor and a spread ceiling, the names with the weakest 1-day or 5-day residual return have a higher subsequent 1-day to 5-day return than the strongest names, after quote-aware prices and pessimistic costs.

The economic story under test is temporary liquidity pressure. It is not a chart pattern and it is not an AI forecast.

## Why this was selected

- A multi-day hold matches the latency of one machine and a retail API. Seconds around the close or the next open are enough.
- A liquid cross-section produces many observations without trading thin stocks.
- The behavior is published and disputed, so failing to find it is a result.
- The main competing explanation, bid-ask bounce plus costs, is directly testable with quotes and a stress fill model.
- The orders are ordinary equity orders. No colocation and no borrow-fee feed are required for the first long-only diagnostic, and the short side is modeled with an explicit daily borrow charge.

## Why other candidates were rejected for the first program

- Intraday order-book trading needs data and latency this operator does not have.
- Crypto strategy search, as shown in the supplied videos, is a multiple-testing engine. It is outside the US-equity mandate.
- LLM price prediction has no economic prior and sits on the wrong side of the order path.
- Pairs trades need borrow and fail when the hedge breaks.
- Options volatility premium is a different market and a different data budget.
- Post-earnings drift is the reserve program. It needs announcement timestamps that were knowable at the decision, which the free stack does not yet have.
- Intermediate residual momentum is slower to falsify and more regime-dependent. It stays third.

## Evidence that the behavior might exist

Jegadeesh (1990) and Lehmann (1990) documented short-horizon reversal. Later work, including Jegadeesh and Titman on the bid-ask spread and the cost studies associated with Avramov, Chordia, and Goyal, shows that a large part of the headline profit is microstructure and trading cost. NY Fed Staff Report 513 argues a residual can remain after a decomposition. That paper is a hypothesis to retest on a liquid universe. It is not imported as a performance number.

None of this has been replicated on a dataset this repository controls.

## What would falsify it

- Stress-model net performance is indistinguishable from zero on the validation window.
- The effect exists only inside the bid-ask bounce, or only in names that fail the liquidity gate.
- One lookback or hold wins and its neighbors do not. That is not a plateau.
- The sealed window, once opened at a promotion review, disagrees in sign with validation after costs.
- Paper and shadow fills are materially worse than the stress backtest.

## Data

Raw daily bars with open, high, low, close, volume, and bid/ask or an explicit spread. Dollar volume. A session calendar. Splits and dividends kept beside raw prices. A point-in-time universe. Free Alpaca data is IEX and is not sufficient for a cost conclusion. The asset list is not a survivorship-free universe. Those limits are stated on every report.

## Horizon and frequency

If the hypothesis survived, the hold would be 1 to 5 trading sessions. The book would be a small number of liquid names per day, not hundreds of turns.

## Execution

Decision at the close. Fill on a later session. Market orders in the study. Limit and stop logic exists in the backtester and is not the research rule. Optimistic, expected, and stress models are all required. Only stress can support promotion, and only together with the other gates.

## Weaknesses

The residual is the cross-sectional mean, not a full factor model. The synthetic plant used for software tests is not the market. Shorting assumes inventory. Sector tags in the synthetic panel are fake. The calendar omits one-off exchange closures rather than guessing them.

## Regimes where it may fail

High-volatility crashes, quiet markets where the spread is the whole signal, and any period where liquidity providers are already leaning against the same names. The market-state scalar can only reduce exposure. It has not been shown to help, and it is not allowed to loosen a hard limit.

## Open questions

- Does any liquid-universe residual survive SIP quotes and a full-spread stress model?
- Is the 1-day cell a different phenomenon from the 5-day cell, or one plateau?
- How large is the survivorship bias if the universe is today's liquid names only?
- What borrow rate should the stress model use for the short leg?

## Current decision

Promotion is rejected. The market hypothesis is untested. See `RESEARCH_LOG.md` after the study command writes `research/results/reversal_study.json`.
