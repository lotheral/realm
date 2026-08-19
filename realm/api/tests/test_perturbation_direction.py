"""Sprint 20 — scenario perturbation direction correctness.
Sprint 26 — magnitude de-quantization.

The Sprint 20 question-blindness diagnosis (outputs/
sprint20_question_blindness.md) found the heuristic (LLM-off) scenario
path DIRECTION-BLIND: bullish, bearish and neutral feeds all produced
the same +0.08 perturbation because (a) predict.py used the strict
base-only word inventory, which missed obvious words like "panic" /
"fear" / "insolvency" / "optimism", and (b) a neutral parse fell back
to a POSITIVE nudge — fabricating a direction the feed never expressed.

Study A then showed the surviving floor/cap clamp QUANTIZED magnitudes:
across the 22 design events the parser produced 15 distinct sentiment
scores, but the [0.08, 0.15] clamp collapsed them to 6 distinct
magnitudes (7 events pinned at the floor, 5 at the cap), so predicted
magnitudes carried no rank information (magnitude ρ ≈ −0.12). Sprint 26
replaces the clamp with a smooth saturating map:

    magnitude = MAX * tanh(|sentiment| * GAIN / MAX)

which preserves the sign contract, keeps the same slope near zero
(GAIN = 2.0, matching the old linear gain), approaches MAX
asymptotically instead of pinning at it, and is strictly monotone in
sentiment strength — every distinct parse now yields a distinct
magnitude. The 0.08 floor is gone: a weakly-resolved direction gets a
proportionally weak perturbation, not a promoted one.

Contract pinned here:
    - recognized bearish feed → negative scalar; bullish → positive
    - genuinely neutral feed → 0.0 (no fabricated direction)
    - stronger sentiment → strictly larger magnitude (no plateaus)
    - magnitude < _PERTURBATION_MAX always (asymptotic cap)
"""

from __future__ import annotations

from realm.api.predict import _PERTURBATION_MAX, _perturbation_for_feed

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

# One negative token diluted to different densities: same direction,
# different strengths. Filler token matches nothing in the inventory.
_WEAK_BEARISH = "war " + "zzz " * 39      # sentiment −1/40
_MILD_BEARISH = "war " + "zzz " * 29      # sentiment −1/30
_DENSE_BEARISH = "war crash panic fear collapse crisis meltdown turmoil"


def test_bullish_feed_produces_positive_perturbation() -> None:
    assert _perturbation_for_feed(BULLISH_FEED) > 0.0


def test_bearish_feed_produces_negative_perturbation() -> None:
    assert _perturbation_for_feed(BEARISH_FEED) < 0.0


def test_neutral_feed_produces_zero_not_fabricated_positive() -> None:
    """A direction the parser cannot resolve must NOT be invented."""
    assert _perturbation_for_feed(NEUTRAL_FEED) == 0.0


def test_opposite_feeds_produce_opposite_signs() -> None:
    up = _perturbation_for_feed(BULLISH_FEED)
    down = _perturbation_for_feed(BEARISH_FEED)
    assert up > 0 > down


def test_positive_noun_does_not_cancel_negative_verb() -> None:
    """Verification-pass regression: 'confidence' as a positive word
    cancelled 'collapses' in the token counter, turning a clearly bearish
    feed neutral (and thus into zero perturbation). Bare subject-nouns
    are excluded from the inventory so the verb's direction wins."""
    assert _perturbation_for_feed("Consumer confidence collapses across markets") < 0.0


def test_magnitude_is_strictly_monotone_no_floor_plateau() -> None:
    """Sprint 26 de-quantization: two feeds with the same direction but
    different sentiment strengths must produce DIFFERENT magnitudes.
    Under the old clamp both of these pinned to the 0.08 floor."""
    weak = _perturbation_for_feed(_WEAK_BEARISH)
    mild = _perturbation_for_feed(_MILD_BEARISH)
    assert weak < 0.0 and mild < 0.0
    assert abs(mild) > abs(weak)


def test_weak_direction_gets_proportionally_weak_magnitude() -> None:
    """The 0.08 floor is gone: a barely-resolved direction must not be
    promoted to a large perturbation."""
    weak = _perturbation_for_feed(_WEAK_BEARISH)
    assert 0.0 < abs(weak) < 0.08


def test_magnitude_approaches_but_never_reaches_cap() -> None:
    """Dense sentiment saturates toward _PERTURBATION_MAX asymptotically
    instead of pinning exactly at it (which erased rank information)."""
    dense = _perturbation_for_feed(_DENSE_BEARISH)
    assert 0.9 * _PERTURBATION_MAX < abs(dense) < _PERTURBATION_MAX
