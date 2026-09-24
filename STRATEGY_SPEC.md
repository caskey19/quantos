# Strategy specification

Name: `liquid-short-horizon-reversal`  
Version: `0.1.0`  
State: rejected for promotion until market evidence exists.

## Rule

On each session, among names with dollar volume at least 20 million and spread at most 15 basis points, rank by residual return. Buy the weakest decile and sell the strongest decile in equal notionals. Hold for the pre-registered number of sessions. Exit with the opposite order on the scheduled session.

The gross budget in the research configuration is 40,000 so the book can fit inside the production gross cap of 50,000 after the risk engine scales each name to 5,000 notional.

## Parameters that count as trials

Lookback 1 or 5. Hold 1 or 5. Decile is fixed at 0.1. Changing the decile would be a new trial and must be recorded before the run.

## What the strategy cannot do

It cannot submit an order, read a broker, raise a risk limit, or open the sealed window. Regime scaling, when requested, multiplies the budget by a factor of at most 1.

## Promotion

All of the following are required, and the function `promote` still refuses live states:

- Stress validation Sharpe positive.
- A neighbor cell with the same sign and at least half the magnitude.
- Real market data, not the synthetic panel.
- A survivorship review that is actually possible with the dataset.
- Skeptic veto absent.
- Sealed window still unread during fitting.

The current artifact fails these tests. See the study output.
