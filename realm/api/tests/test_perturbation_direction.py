"""Sprint 20 — scenario perturbation direction correctness.

The Sprint 20 question-blindness diagnosis (outputs/
sprint20_question_blindness.md) found the heuristic (LLM-off) scenario
path DIRECTION-BLIND: bullish, bearish and neutral feeds all produced
the same +0.08 perturbation because (a) predict.py used the strict
base-only word inventory, which missed obvious words like "panic" /
"fear" / "insolvency" / "optimism", and (b) a neutral parse fell back
to a POSITIVE nudge — fabricating a direction the feed never expressed.

Since the 2026-08-18 repositioning makes the scenario delta REALM's
primary product, direction correctness of this fallback is load-bearing.
These tests pin the fixed contract:
    - recognized bearish feed → negative scalar (magnitude ≥ floor)
    - recognized bullish feed → positive scalar (magnitude ≥ floor)
    - genuinely neutral feed → 0.0 (no fabricated direction)
"""

from __future__ import annotations

from realm.api.predict import _MIN_PERTURBATION, _perturbation_for_feed

BULLISH_FEED = (
    "Massive institutional adoption announced; regulators approve "
    "spot ETFs across Europe and Asia; optimism grows."
)
BEARISH_FEED = (
    "Major exchange declares insolvency; billions in customer funds "
    "frozen; panic selling and fear spread across markets."
)
NEUTRAL_FEED = (
    "Trading volumes remain unchanged this week; analysts note "
    "markets are calm and stable."
)


def test_bullish_feed_produces_positive_perturbation() -> None:
    scalar = _perturbation_for_feed(BULLISH_FEED)
    assert scalar >= _MIN_PERTURBATION


def test_bearish_feed_produces_negative_perturbation() -> None:
    scalar = _perturbation_for_feed(BEARISH_FEED)
    assert scalar <= -_MIN_PERTURBATION


def test_neutral_feed_produces_zero_not_fabricated_positive() -> None:
    """A direction the parser cannot resolve must NOT be invented."""
    assert _perturbation_for_feed(NEUTRAL_FEED) == 0.0


def test_opposite_feeds_produce_opposite_signs() -> None:
    up = _perturbation_for_feed(BULLISH_FEED)
    down = _perturbation_for_feed(BEARISH_FEED)
    assert up > 0 > down
