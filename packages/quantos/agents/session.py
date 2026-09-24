"""Research agents. They debate. They cannot submit orders.

The skeptic veto blocks promotion. A cheerful strategy memo is not enough.
"""

from __future__ import annotations

from quantos.contracts.models import Claim, ClaimKind, SkepticVerdict


def research_memo(summary: dict) -> list[Claim]:
    return [
        Claim(
            agent="research",
            kind=ClaimKind.HYPOTHESIS,
            statement="Liquid names with weak recent residual returns might outperform strong names over 1 to 5 sessions after costs.",
            refs=["Jegadeesh 1990", "Lehmann 1990"],
        ),
        Claim(
            agent="quant",
            kind=ClaimKind.FACT,
            statement=f"Pre-registered trial count is {summary.get('n_trials')}. The sealed window was not opened.",
            refs=["config/sealed_window.yml"],
        ),
        Claim(
            agent="data",
            kind=ClaimKind.FACT,
            statement="This run used a synthetic panel. IEX and SIP market data were not ingested. Survivorship is unresolved.",
            refs=[summary.get("experiments", [{}])[0].get("data_version", "synthetic")],
        ),
        Claim(
            agent="ml",
            kind=ClaimKind.FACT,
            statement="The linear baseline is stored and not promoted. No model sits on the order path.",
        ),
        Claim(
            agent="execution",
            kind=ClaimKind.STATISTICAL_EVIDENCE,
            statement="Optimistic, expected, and stress fills were all recorded. Promotion looks at the stress model only.",
        ),
        Claim(
            agent="news",
            kind=ClaimKind.FACT,
            statement="News is outside the selected program and was not used as a feature.",
        ),
        Claim(
            agent="code_review",
            kind=ClaimKind.FACT,
            statement="Reversal features use past pct_change only. Forward labels live in a separate module.",
        ),
        Claim(
            agent="risk",
            kind=ClaimKind.HYPOTHESIS,
            statement="A short book can lose more than the gross budget if spreads gap. Hard loss limits stay in force.",
        ),
    ]


def skeptic_review(summary: dict) -> SkepticVerdict:
    objections: list[Claim] = []
    if summary.get("real_market_evidence") is not True:
        objections.append(
            Claim(
                agent="skeptic",
                kind=ClaimKind.FACT,
                statement="There is no market evidence in this artifact. Promotion is refused.",
            )
        )
    best = (summary.get("best_stress_parameter") or {}).get("sharpe", 0) or 0
    if best <= 0:
        objections.append(
            Claim(
                agent="skeptic",
                kind=ClaimKind.STATISTICAL_EVIDENCE,
                statement="Stress-model validation Sharpe is not positive, so costs or the plant dominate.",
            )
        )
    if not summary.get("parameter_plateau"):
        objections.append(
            Claim(
                agent="skeptic",
                kind=ClaimKind.HYPOTHESIS,
                statement="A single parameter cell is not a plateau. Isolated winners are treated as overfit.",
            )
        )
    objections.append(
        Claim(
            agent="skeptic",
            kind=ClaimKind.SPECULATION,
            statement="Published reversal profits have often been bid-ask bounce. That remains the leading alternative explanation.",
            refs=["Jegadeesh and Titman microstructure papers", "Avramov, Chordia, Goyal"],
        )
    )
    return SkepticVerdict(veto=True, objections=objections)


def post_trade_note(expected_spread: float, observed_spread: float) -> Claim:
    kind = ClaimKind.FACT if observed_spread else ClaimKind.HYPOTHESIS
    return Claim(
        agent="post_trade",
        kind=kind,
        statement=f"Expected spread {expected_spread:.2f} bps versus observed {observed_spread:.2f} bps.",
    )


def session(summary: dict) -> dict:
    verdict = skeptic_review(summary)
    promoted = (not verdict.veto) and summary.get("promotion") == "accepted"
    return {
        "claims": [claim.model_dump() for claim in research_memo(summary)],
        "skeptic": verdict.model_dump(),
        "promoted": promoted,
    }
