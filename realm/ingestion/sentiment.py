"""Lightweight sentiment heuristic shared by predict.py and feed_parser.py.

Sprint 13 first introduced the `_POSITIVE_WORDS` / `_NEGATIVE_WORDS` lists
inside `realm/api/predict.py` to drive scenario perturbation direction.
Sprint 14 WP5 extracts them into a module so the new feed parser uses the
SAME word inventory, keeping the manual textarea path and RSS path on a
single sentiment model. Domain-specific extensions (crypto, politics) can
be appended here without touching the API surface.

This is a coarse heuristic — economic / political contexts often invert
sentiment (a "rate hike" is bad for borrowers, good for savers). Callers
should treat the sign as a directional hint, not a measurement.
"""

from __future__ import annotations

# Core inventory inherited verbatim from realm/api/predict.py (Sprint 13).
_POSITIVE_WORDS_BASE: tuple[str, ...] = (
    "support", "growth", "rally", "peace", "agreement", "success",
    "breakthrough", "recovery", "boost", "win", "gain", "cut", "cuts",
    "cutting", "dovish", "easing", "ease", "ceasefire", "settlement",
    "approval", "boom", "drops", "drop", "falls", "fall", "declines",
    "stimulus", "soft", "easier", "lower", "lowered", "improves",
    "approve", "passes", "wins", "elected",
)
_NEGATIVE_WORDS_BASE: tuple[str, ...] = (
    "attack", "war", "crash", "fail", "crisis", "threat", "strike",
    "collapse", "sanction", "loss", "decline", "conflict", "destroy",
    "invasion", "tightening", "tighten", "hawkish", "warns", "weapon",
    "missile", "casualty", "shock", "raises", "raise", "hike", "hikes",
    "hiking", "elevated", "surges", "surging", "accelerates", "prolonged",
    "rejected", "loses", "defeated",
)

# Sprint 14 WP5 domain-specific extensions. Kept as a SEPARATE tuple so the
# regression contract with predict.py's Sprint 13 numbers can be reproduced
# by importing only the *_BASE tuples.
_POSITIVE_WORDS_DOMAIN: tuple[str, ...] = (
    # crypto
    "moon", "halving", "etf", "bullish", "adoption", "all-time-high",
    # markets
    "outperform", "upgrade", "beat", "buyback",
    # politics
    "mandate", "endorsement", "ratify", "reform",
    # culture / sports / science
    "viral", "headline", "championship", "discovery",
    # Sprint 20 — generic affect terms the diagnosis found missing
    # (bullish/bearish feeds parsed as neutral without them). NOTE:
    # bare nouns that routinely appear as the SUBJECT of a negative verb
    # ("confidence collapses", "hopes dashed") are deliberately excluded —
    # the verification pass showed they cancel the verb's signal in this
    # token counter and neutralize clearly-bearish feeds.
    "optimism", "optimistic", "hopeful", "relief", "celebrate",
    "milestone", "stabilize",
)
_NEGATIVE_WORDS_DOMAIN: tuple[str, ...] = (
    # crypto
    "rug", "rugpull", "hack", "exploit", "delisting", "bearish",
    # markets
    "downgrade", "miss", "guidance-cut", "bankruptcy",
    # politics
    "scandal", "impeachment", "indictment", "censure",
    # culture / sports / science
    "cancel", "boycott", "recall", "outage", "outbreak",
    # Sprint 20 — generic affect terms the diagnosis found missing.
    "panic", "fear", "insolvency", "insolvent", "plunge", "plunges",
    "tumble", "turmoil", "meltdown", "contagion", "crackdown",
    "pessimism", "pessimistic", "distress", "default",
)

# Public combined inventory used by parse_sentiment(). Since Sprint 20 this
# full inventory is what realm/api/predict.py uses for scenario perturbation;
# the *_BASE tuples remain for callers that want the historical Sprint 13
# behavior.
POSITIVE_WORDS: tuple[str, ...] = _POSITIVE_WORDS_BASE + _POSITIVE_WORDS_DOMAIN
NEGATIVE_WORDS: tuple[str, ...] = _NEGATIVE_WORDS_BASE + _NEGATIVE_WORDS_DOMAIN


def parse_sentiment(
    feed: str,
    *,
    positive_words: tuple[str, ...] | None = None,
    negative_words: tuple[str, ...] | None = None,
) -> float:
    """Return net sentiment in [-1, +1] from a token-frequency heuristic.

    By default scans against the combined BASE+DOMAIN inventory. Pass the
    ``*_BASE`` tuples explicitly to reproduce Sprint 13 predict.py behavior
    exactly (no domain extensions).
    """
    if not feed or not feed.strip():
        return 0.0
    pos = positive_words if positive_words is not None else POSITIVE_WORDS
    neg = negative_words if negative_words is not None else NEGATIVE_WORDS
    words = feed.lower().split()
    pos_count = sum(1 for w in words if any(p in w for p in pos))
    neg_count = sum(1 for w in words if any(n in w for n in neg))
    total = max(len(words), 1)
    return (pos_count - neg_count) / total


def parse_sentiment_strict(feed: str) -> float:
    """Sprint 13 contract — base inventory only, no domain extensions.
    HISTORICAL as of Sprint 20: realm/api/predict.py now uses the full
    inventory (`parse_sentiment`); this variant is retained only for
    reproducing the Sprint 13 acceptance numbers and has no production
    callers."""
    return parse_sentiment(
        feed,
        positive_words=_POSITIVE_WORDS_BASE,
        negative_words=_NEGATIVE_WORDS_BASE,
    )


__all__ = (
    "parse_sentiment",
    "parse_sentiment_strict",
    "POSITIVE_WORDS",
    "NEGATIVE_WORDS",
    "_POSITIVE_WORDS_BASE",
    "_NEGATIVE_WORDS_BASE",
    "_POSITIVE_WORDS_DOMAIN",
    "_NEGATIVE_WORDS_DOMAIN",
)
