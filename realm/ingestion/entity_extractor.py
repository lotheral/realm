"""Lightweight entity / topic / sentiment extraction (no ML deps).

- Topic: keyword-weighted scoring across 6 canonical topics.
- Entities: capitalized multi-word sequences, filtered by stopwords and length.
- Sentiment: Hu & Liu lexicon-style positive/negative word lists (compact).
- Geography: ISO2 detection from country name mentions.

This is a Phase 4 MVP. A future phase will swap in spaCy / transformer NER when
LLM inference is wired in.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace

from realm.ingestion.interfaces import ISeedProcessor, SeedEvent

# ---- Topic classification -------------------------------------------------

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "politics": (
        "election", "parliament", "senator", "president", "prime minister",
        "congress", "party", "vote", "diplomat", "referendum", "sanction",
        "treaty", "legislation", "ministry", "government", "court ruling",
        "impeach", "oligarch", "protest",
    ),
    "tech": (
        "AI", "software", "startup", "chip", "processor", "cloud", "quantum",
        "smartphone", "app", "algorithm", "silicon", "semiconductor", "open source",
        "programming", "hackathon", "datacenter", "GPU", "LLM", "machine learning",
        "robotics", "crypto", "blockchain", "bitcoin", "ethereum",
    ),
    "finance": (
        "stock", "equity", "bond", "market", "inflation", "interest rate",
        "federal reserve", "ecb", "earnings", "revenue", "ipo", "acquisition",
        "merger", "hedge fund", "recession", "GDP", "unemployment", "currency",
        "fiscal", "deficit", "trade war", "tariff",
        "financial", "finance", "bank", "banking", "banks", "crisis",
        "debt", "loan", "credit", "dollar", "euro", "yen", "yuan",
    ),
    "culture": (
        "film", "movie", "festival", "music", "album", "concert", "artist",
        "museum", "novel", "author", "book", "award", "oscar", "grammy",
        "literature", "theatre", "painter", "sculpture", "fashion",
    ),
    "personal": (
        "celebrity", "scandal", "wedding", "divorce", "feud", "lifestyle",
        "relationship", "family", "gossip", "viral video", "influencer",
        "instagram", "tiktok", "memoir", "life story",
    ),
    "news": (
        "breaking", "alert", "update", "report", "official", "announce",
        "statement", "press release", "investigation", "disaster", "storm",
        "earthquake", "flood", "wildfire", "pandemic", "outbreak",
    ),
}


def classify_topic(text: str) -> str:
    """Return the highest-scoring topic for `text`. Defaults to 'news' on ties."""
    low = text.lower()
    scores: dict[str, int] = dict.fromkeys(_TOPIC_KEYWORDS, 0)
    for topic, keywords in _TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in low:
                scores[topic] += 1
    best_topic = "news"
    best_score = 0
    for t, s in scores.items():
        if s > best_score:
            best_topic, best_score = t, s
    return best_topic


# ---- Sentiment ------------------------------------------------------------
# Compact positive/negative lexicons. Tuned for news-style English.

_POSITIVE = frozenset({
    "good", "great", "excellent", "success", "successful", "win", "wins", "wonderful",
    "strong", "record", "breakthrough", "boost", "surge", "rally", "soar", "gain",
    "positive", "approve", "approved", "agreement", "deal", "recovery", "improve",
    "improved", "optimistic", "celebrate", "thriving", "profit", "profitable",
    "innovative", "safe", "achievement", "hope",
})

_NEGATIVE = frozenset({
    "bad", "terrible", "awful", "crash", "plunge", "fall", "falls", "falling",
    "loss", "losses", "weak", "fail", "fails", "failure", "scandal", "crisis",
    "decline", "collapse", "drop", "slump", "concern", "concerns", "worry", "worries",
    "fear", "fears", "threat", "attack", "conflict", "war", "dead", "death", "killed",
    "injured", "victim", "violence", "corruption", "fraud", "dispute", "opposition",
    "controversy", "chaos", "sanction", "sanctions", "accused", "arrested", "jailed",
})

_NEGATORS = frozenset({"not", "no", "never", "without", "lacking", "hardly", "barely"})


_WORD_RE = re.compile(r"[A-Za-z']+")


def _stem(word: str) -> str:
    """Strip the most common English inflectional suffixes (Porter-lite).

    Not linguistically exhaustive — just enough to collapse ing/ed/es/s onto the
    root so a fixed lexicon catches inflected forms like 'boosting'/'plunged'.
    """
    for suffix in ("ing", "ied", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            root = word[: -len(suffix)]
            return root
    return word


def _matches_lexicon(word: str, lexicon: frozenset[str]) -> bool:
    return word in lexicon or _stem(word) in lexicon


def score_sentiment(text: str) -> float:
    """Return sentiment score in [-1, 1]. 0 = neutral."""
    if not text:
        return 0.0
    tokens = [w.lower() for w in _WORD_RE.findall(text)]
    if not tokens:
        return 0.0

    score = 0
    total_hits = 0
    negation_window = 3
    for i, w in enumerate(tokens):
        negated = any(
            tokens[j] in _NEGATORS
            for j in range(max(0, i - negation_window), i)
        )
        if _matches_lexicon(w, _POSITIVE):
            score += -1 if negated else 1
            total_hits += 1
        elif _matches_lexicon(w, _NEGATIVE):
            score += 1 if negated else -1
            total_hits += 1

    if total_hits == 0:
        return 0.0
    # Normalize by number of hits, clamp to [-1, 1]
    raw = score / max(total_hits, 1)
    return max(-1.0, min(1.0, raw))


# ---- Entity extraction ----------------------------------------------------

_STOPWORD_CAPS = frozenset({
    "The", "A", "An", "This", "That", "These", "Those",
    "He", "She", "It", "We", "They", "You", "I",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
    "Breaking", "Update", "News", "Report",
})

_CAP_SEQ_RE = re.compile(r"\b(?:[A-Z][a-zA-Z\-']{1,})(?:\s+(?:[A-Z][a-zA-Z\-']{1,}|of|the|and|de|la|van|von|bin)){0,4}")


def extract_entities(text: str, max_entities: int = 10) -> tuple[str, ...]:
    """Return up to `max_entities` proper-noun phrases from `text`.

    Heuristic: a sequence of capitalized words (plus low-case connectors like
    'of', 'the'). Filters out single-word stopwords and beginning-of-sentence
    false positives.
    """
    if not text:
        return ()

    seen: set[str] = set()
    out: list[str] = []
    for match in _CAP_SEQ_RE.finditer(text):
        phrase = match.group(0).strip()
        tokens = phrase.split()
        while tokens and tokens[-1].lower() in {"of", "the", "and", "de", "la", "van", "von", "bin"}:
            tokens.pop()
        if not tokens:
            continue
        phrase = " ".join(tokens)
        if phrase in _STOPWORD_CAPS:
            continue
        if len(phrase) < 3:
            continue
        if phrase in seen:
            continue
        seen.add(phrase)
        out.append(phrase)
        if len(out) >= max_entities:
            break
    return tuple(out)


# ---- Geography tagging ----------------------------------------------------
# Lazy-loaded from countries.json so we tag known countries by name.

_GEO_CACHE: dict[str, str] | None = None


def _load_geo_index() -> dict[str, str]:
    global _GEO_CACHE
    if _GEO_CACHE is not None:
        return _GEO_CACHE
    from realm.demographics.country_data import load_countries
    index: dict[str, str] = {}
    for c in load_countries():
        name = str(c["name"]).lower()
        iso = str(c["iso2"])
        index[name] = iso
        # Also index major short aliases
        if name.startswith("united "):
            short = name.split()[-1]
            if len(short) >= 4:
                index[short] = iso
    _GEO_CACHE = index
    return index


def detect_geography(text: str) -> str | None:
    """Return the ISO2 code of the first recognized country mentioned, or None."""
    index = _load_geo_index()
    low = text.lower()
    # Longest-name-first, to prefer 'United Kingdom' over 'kingdom'
    for name in sorted(index.keys(), key=len, reverse=True):
        if name in low:
            return index[name]
    return None


# ---- Pipeline processor ---------------------------------------------------

class EnrichingProcessor(ISeedProcessor):
    """Fills in missing topic / sentiment / entities / geography on events.

    Non-destructive: if the source already provided a non-default value, it is
    preserved.
    """

    def process(self, events: Iterable[SeedEvent]) -> list[SeedEvent]:
        out: list[SeedEvent] = []
        for e in events:
            text = f"{e.headline}\n{e.body}"
            updates: dict[str, object] = {}
            if e.topic == "news":
                updates["topic"] = classify_topic(text)
            if e.sentiment == 0.0:
                updates["sentiment"] = score_sentiment(text)
            if not e.entities:
                updates["entities"] = extract_entities(text)
            if e.geography is None:
                updates["geography"] = detect_geography(text)
            out.append(replace(e, **updates) if updates else e)
        return out
