"""ExperienceDriftEngine — event-driven cumulative trait drift.

Agents in REALM have `frozen=True` `TraitVector`s, so drift cannot mutate the
agent. This module owns external per-agent cumulative drift state and exposes
it as delta dicts consumable by `TraitVector.apply_modifier`.

Determinism: drift is a pure function of (event_type, intensity) applied in
order, clamped to ``max_drift_ratio * original_trait_value``. No RNG is used
inside the engine; any event-selection randomness is the caller's concern.

Event-catalogue + decision-to-event translation
------------------------------------------------

Sprint 9 shipped 6 hand-authored event types with a hard-coded
`event_from_decision` heuristic that only emitted ``positive_social``,
``negative_social`` from posts/engages (4 of the 6 types never fired).

Sprint 10 WP3 adds 6 new event types (leadership_act, group_conformity,
group_dissent, financial_loss, financial_gain, cultural_experience) and a
config-driven `DriftEventBridge` that maps (Decision, Agent) pairs to a
single drift event via ordered rules. The hard-coded path is retained for
backwards compatibility — every existing test exercises it untouched.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from realm.personality.trait_vector import TraitVector

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from realm.agents.decision import Decision

# Per-unit-intensity trait delta applied by one event. The cumulative drift
# is additionally clamped to ±max_drift_ratio * original_value, so this
# constant mainly controls how many events it takes to reach the ceiling.
# Sprint 15: bumped from 0.01 → 0.025 (2.5×) so per-category asymmetry has
# enough per-tick headroom to actually bias the population mean within the
# typical 30-tick horizon. The cumulative cap (drift_volatility × 0.10)
# still binds asymptotically — but now after ~5 events instead of ~12 —
# letting the 3-knob differentiation system (volatility, asymmetry,
# sigmoid sensitivity) reach the prompt's ≥3pp spread target.
_BASE_DRIFT_COEFFICIENT: float = 0.025

# Hand-authored event → trait-direction map. Values are direction (+1/-1)
# weights in [-1, 1]; per-event delta = weight * intensity * _BASE_DRIFT_COEFFICIENT.
_EVENT_TRAIT_MAP: dict[str, dict[str, float]] = {
    "positive_social": {
        "empathy": +1.0,
        "agreeableness": +0.7,
        "social_dominance": +0.3,
        "neuroticism": -0.4,
    },
    "negative_social": {
        "contrarian_tendency": +0.8,
        "agreeableness": -0.7,
        "neuroticism": +0.8,
        "empathy": -0.3,
    },
    "successful_risk": {
        "risk_appetite": +1.0,
        "financial_optimism": +0.8,
        "loss_aversion": -0.7,
        "impulsivity": +0.3,
    },
    "failed_risk": {
        "risk_appetite": -0.9,
        "loss_aversion": +1.0,
        "patience": +0.5,
        "financial_optimism": -0.6,
    },
    "knowledge_acquisition": {
        "analytical_depth": +1.0,
        "openness": +0.7,
        "information_sharing": +0.3,
    },
    "stress_crisis": {
        "neuroticism": +1.0,
        "impulsivity": +0.7,
        "patience": -0.6,
        "authority_compliance": +0.3,
    },
}


@dataclass
class ExperienceDriftEngine:
    """Accumulates per-agent trait drift from named event sequences.

    Usage:
        engine = ExperienceDriftEngine(max_drift_ratio=0.10)
        engine.record_event("agent_42", "successful_risk", 0.8, agent.traits)
        effective_traits = engine.current_traits(agent)
    """

    max_drift_ratio: float = 0.10
    event_map: Mapping[str, Mapping[str, float]] = field(
        default_factory=lambda: _EVENT_TRAIT_MAP
    )
    # Sprint 15 WP3: per-event scaling driven by the event's NET effect on
    # the active category's primary traits. When the event pushes primary
    # traits up (sum of primary coefficients > 0), scale the WHOLE event by
    # positive_multiplier; when it pushes them down, scale by
    # negative_multiplier. Set primary_trait_set on construction so the
    # engine knows which traits to weigh when computing the event's net.
    # Defaults of 1.0 each + empty primary set preserve Sprint 14 behavior
    # bit-for-bit (no scaling fires when primary set is empty).
    positive_multiplier: float = 1.0
    negative_multiplier: float = 1.0
    primary_trait_set: frozenset[str] = field(default_factory=frozenset)
    # Sprint 15 WP2 (refined): per-event intensity scalar. Scales the
    # per-event base coefficient _BASE_DRIFT_COEFFICIENT so drift accumulates
    # FASTER in high-volatility categories (crypto 1.6) and SLOWER in
    # low-volatility ones (politics 0.5). This is the second knob that
    # drift_volatility wires into — together with the cap raise, it lets
    # baseline differentiation actually accumulate within 30 ticks. Default
    # 1.0 preserves Sprint 14 bit-for-bit.
    intensity_scale: float = 1.0
    # agent_id -> trait_name -> cumulative delta (signed)
    _drift: dict[str, dict[str, float]] = field(default_factory=dict)
    # agent_id -> count of recorded events (diagnostic)
    _event_count: dict[str, int] = field(default_factory=dict)
    # Sprint 20: event types we've already warned about — the silent
    # unknown-event no-op hid the Sprint 10 wiring bug for six sprints,
    # so misses now log a WARNING (once per type, to avoid spam).
    _warned_unknown: set[str] = field(default_factory=set, repr=False)

    def record_event(
        self,
        agent_id: str,
        event_type: str,
        intensity: float,
        original_traits: TraitVector,
    ) -> None:
        """Apply one event's contribution to this agent's cumulative drift.

        Clamped so that ``abs(cumulative_drift[trait]) <= max_drift_ratio * original_value``.
        Unknown ``event_type`` is silently ignored (for forward-compat).
        """
        weights = self.event_map.get(event_type)
        if not weights:
            if event_type not in self._warned_unknown:
                self._warned_unknown.add(event_type)
                logger.warning(
                    "drift: unknown event type %r ignored — engine's event_map "
                    "has %d entries; if this event should drift traits, build "
                    "the engine via DriftEventBridge.build_engine() so it "
                    "carries the full catalog",
                    event_type, len(self.event_map),
                )
            return
        intensity = max(0.0, min(1.0, float(intensity)))
        if intensity == 0.0:
            return
        agent_drift = self._drift.setdefault(agent_id, {})
        originals = original_traits.to_dict()
        # Sprint 15 WP3 — compute the event's net signed effect on the
        # ACTIVE CATEGORY's primary traits, then scale the whole event by
        # the corresponding asymmetry multiplier. Events that push primaries
        # UP get amplified (or dampened) by positive_multiplier; events
        # that push them DOWN get scaled by negative_multiplier. When no
        # primary_trait_set is configured (Sprint 14 path), event_scale
        # stays at 1.0 — bit-for-bit identical drift accumulation.
        if self.primary_trait_set:
            net_primary = sum(
                float(weights.get(t, 0.0)) for t in self.primary_trait_set
            )
            if net_primary > 0.0:
                event_scale = self.positive_multiplier
            elif net_primary < 0.0:
                event_scale = self.negative_multiplier
            else:
                event_scale = 1.0
        else:
            event_scale = 1.0
        for trait, direction in weights.items():
            original_value = originals.get(trait)
            if original_value is None:
                continue
            max_abs_delta = max(
                original_value, 1.0 - original_value
            ) * self.max_drift_ratio
            # Symmetric absolute cap prevents drift past [0, 1] via clamp interplay
            cap = original_value * self.max_drift_ratio
            delta = (
                direction * intensity * _BASE_DRIFT_COEFFICIENT
                * self.intensity_scale       # per-category speed
                * event_scale                # primary-net asymmetry
            )
            cumulative = agent_drift.get(trait, 0.0) + delta
            if cumulative > cap:
                cumulative = cap
            elif cumulative < -cap:
                cumulative = -cap
            # guard against floating-point creep past [0,1] after apply
            # (original_value + cumulative may exceed 1.0 when original near 1.0)
            effective_upper = 1.0 - original_value
            effective_lower = -original_value
            if cumulative > effective_upper:
                cumulative = effective_upper
            elif cumulative < effective_lower:
                cumulative = effective_lower
            # avoid unused-variable lint for max_abs_delta (kept for docstring clarity)
            _ = max_abs_delta
            agent_drift[trait] = cumulative
        self._event_count[agent_id] = self._event_count.get(agent_id, 0) + 1

    def drift_vector(self, agent_id: str) -> dict[str, float]:
        """Return a copy of the cumulative drift deltas for one agent."""
        return dict(self._drift.get(agent_id, {}))

    def current_traits(self, agent: Agent) -> TraitVector:
        """Return ``agent.traits`` with this engine's cumulative drift applied."""
        drift = self._drift.get(agent.agent_id)
        if not drift:
            return agent.traits
        return agent.traits.apply_modifier(drift)

    def cumulative_magnitude(self, agent_id: str) -> float:
        """L1 norm of this agent's cumulative drift — useful as a summary metric."""
        drift = self._drift.get(agent_id, {})
        return sum(abs(v) for v in drift.values())

    def event_count(self, agent_id: str) -> int:
        return self._event_count.get(agent_id, 0)

    def reset_agent(self, agent_id: str) -> None:
        """Clear cumulative drift for a single agent (e.g. on re-initialisation)."""
        self._drift.pop(agent_id, None)
        self._event_count.pop(agent_id, None)

    def reset_all(self) -> None:
        self._drift.clear()
        self._event_count.clear()

    def to_state(self) -> dict[str, Any]:
        """Serialisable state for JSON checkpointing.

        Sprint 20: serialises EVERY configuration knob, not just
        max_drift_ratio — the pre-Sprint-20 shape silently reverted a
        resumed engine to the legacy 6-event map and neutral multipliers,
        re-creating the Sprint 10 no-op bug on every checkpoint resume.
        """
        return {
            "max_drift_ratio": self.max_drift_ratio,
            "event_map": {ev: dict(w) for ev, w in self.event_map.items()},
            "positive_multiplier": self.positive_multiplier,
            "negative_multiplier": self.negative_multiplier,
            "primary_trait_set": sorted(self.primary_trait_set),
            "intensity_scale": self.intensity_scale,
            "drift": {aid: dict(d) for aid, d in self._drift.items()},
            "event_count": dict(self._event_count),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> ExperienceDriftEngine:
        raw_map = state.get("event_map")
        if raw_map is None:
            # Legacy (pre-Sprint-20) checkpoint: it was WRITTEN by an
            # engine whose live map was unrecorded. Restore the legacy
            # default so behavior matches what actually produced the
            # checkpoint, and say so.
            logger.warning(
                "drift: checkpoint has no event_map (pre-Sprint-20 format); "
                "restoring the legacy 6-event map — Sprint 10+ event types "
                "will not accumulate drift in this resumed engine",
            )
            event_map: Mapping[str, Mapping[str, float]] = _EVENT_TRAIT_MAP
        else:
            event_map = {ev: dict(w) for ev, w in raw_map.items()}
        engine = cls(
            max_drift_ratio=float(state.get("max_drift_ratio", 0.10)),
            event_map=event_map,
            positive_multiplier=float(state.get("positive_multiplier", 1.0)),
            negative_multiplier=float(state.get("negative_multiplier", 1.0)),
            primary_trait_set=frozenset(state.get("primary_trait_set", ())),
            intensity_scale=float(state.get("intensity_scale", 1.0)),
        )
        engine._drift = {aid: dict(d) for aid, d in state.get("drift", {}).items()}
        engine._event_count = dict(state.get("event_count", {}))
        return engine


# ---- Decision → event-type bridge ------------------------------------------

# The simulation engine's Decision has action ∈ {post, engage, lurk} plus a
# topic and sentiment. We translate those into drift event types so the engine
# can record drift without knowing the event catalogue internally.
_DECISION_TO_EVENT: dict[str, str] = {
    # Posting is an assertive social act — calibrate as positive_social when
    # the post sentiment is non-negative; when sentiment < 0 it is
    # negative_social (agent expresses grievance).
    # engage→positive_social by default (agent interacts constructively)
    # lurk→stress_crisis (mild) only when agent already has high neuroticism;
    # otherwise no drift event is emitted
}


def event_from_decision(action: str, sentiment: float | None = None) -> str | None:
    """Translate one Decision into a drift event_type. None = no drift this tick.

    Heuristics (Sprint 9 baseline, retained for backwards compat):
      * ``post`` with sentiment >= 0 → positive_social
      * ``post`` with sentiment <  0 → negative_social
      * ``engage`` → positive_social (light intensity is the caller's concern)
      * ``lurk`` → no drift event

    For richer decision→event mapping (Sprint 10 WP3), use `DriftEventBridge`.
    """
    if action == "post":
        if sentiment is not None and sentiment < 0:
            return "negative_social"
        return "positive_social"
    if action == "engage":
        return "positive_social"
    # lurk and unknown actions do not drift
    return None


# ---- Sprint 10 WP3 — config-driven rule bridge -----------------------------


@dataclass(frozen=True)
class _Rule:
    """One event-firing rule compiled from JSON config.

    Evaluation is pure: a rule either matches (decision, agent.traits) fully or
    not at all. Rules are consulted in declaration order; the first match fires.
    """

    name: str
    event_type: str
    intensity: float
    # Decision-field predicates
    action: str | None = None
    topic: str | None = None
    topic_in: tuple[str, ...] | None = None
    engagement_kind: str | None = None
    sentiment_gte: float | None = None
    sentiment_lt: float | None = None
    virality_gte: float | None = None
    virality_lt: float | None = None
    # Trait-vector predicates
    trait_gte: tuple[tuple[str, float], ...] = ()
    trait_lt: tuple[tuple[str, float], ...] = ()

    def matches(self, decision: Decision, traits: TraitVector) -> bool:
        if self.action is not None and decision.action != self.action:
            return False
        if self.topic is not None and decision.topic != self.topic:
            return False
        if self.topic_in is not None and decision.topic not in self.topic_in:
            return False
        if self.engagement_kind is not None and decision.engagement_kind != self.engagement_kind:
            return False
        if self.sentiment_gte is not None and decision.sentiment < self.sentiment_gte:
            return False
        if self.sentiment_lt is not None and decision.sentiment >= self.sentiment_lt:
            return False
        if self.virality_gte is not None and decision.virality < self.virality_gte:
            return False
        if self.virality_lt is not None and decision.virality >= self.virality_lt:
            return False
        # Trait thresholds are read via attribute access so TraitVector stays typed
        for trait_name, threshold in self.trait_gte:
            if getattr(traits, trait_name, 0.0) < threshold:
                return False
        for trait_name, threshold in self.trait_lt:
            if getattr(traits, trait_name, 0.0) >= threshold:
                return False
        return True


@dataclass(frozen=True)
class DriftEventBridge:
    """Maps (Decision, Agent) → (event_type, intensity) via ordered rules.

    Construct via `DriftEventBridge.from_json(path)`; the JSON schema is
    documented at config/drift_events.json. Rules are consulted in declaration
    order, first match fires, no rule matches → None (lurk behaviour).

    Sprint 14 WP1: when ``event_weights`` is supplied (mapping event_type →
    relative weight), `event_for` collects ALL matching rules and
    weight-samples among them using the caller-supplied ``rng``. When
    ``event_weights`` is None (default), behaviour is the pre-Sprint-14
    deterministic first-match-wins — every existing test passes untouched.
    """

    event_map: Mapping[str, Mapping[str, float]]
    rules: tuple[_Rule, ...]
    default_intensity: float = 0.5
    # Sprint 14 WP1: optional per-event relative weights. None = uniform
    # first-match (legacy). When set, all matching rules are collected and
    # one is sampled with weight = event_weights.get(rule.event_type, 1.0).
    event_weights: tuple[tuple[str, float], ...] | None = None

    def event_for(
        self,
        decision: Decision,
        traits: TraitVector,
        rng: Any | None = None,
    ) -> tuple[str, float] | None:
        """Return (event_type, intensity) for this decision, or None."""
        if decision.action == "lurk":
            return None
        if self.event_weights is None or rng is None:
            for rule in self.rules:
                if rule.matches(decision, traits):
                    return rule.event_type, rule.intensity
            return None
        # Sprint 14 WP1 weighted path: collect every matching rule, sample
        # one weighted by its event_type's category-conditioned weight.
        matching: list[_Rule] = [r for r in self.rules if r.matches(decision, traits)]
        if not matching:
            return None
        weights_map = dict(self.event_weights)
        weights = [max(0.0, float(weights_map.get(r.event_type, 1.0))) for r in matching]
        if sum(weights) <= 0.0:
            return matching[0].event_type, matching[0].intensity
        chosen = rng.choices(matching, weights=weights, k=1)[0]
        return chosen.event_type, chosen.intensity

    def with_weights(
        self, event_weights: Mapping[str, float] | None,
    ) -> DriftEventBridge:
        """Return a new bridge instance carrying the given event_weights.
        Pass None to disable weighting (returns an equivalent legacy bridge).
        """
        if event_weights is None:
            return DriftEventBridge(
                event_map=self.event_map,
                rules=self.rules,
                default_intensity=self.default_intensity,
                event_weights=None,
            )
        ew = tuple((str(k), float(v)) for k, v in event_weights.items())
        return DriftEventBridge(
            event_map=self.event_map,
            rules=self.rules,
            default_intensity=self.default_intensity,
            event_weights=ew,
        )

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> DriftEventBridge:
        """Build from a parsed JSON dict (see drift_events.json schema)."""
        default_intensity = float(cfg.get("default_intensity", 0.5))
        event_map = {
            name: dict(body.get("traits", {}))
            for name, body in cfg.get("event_types", {}).items()
        }
        rules: list[_Rule] = []
        for r in cfg.get("rules", []):
            when = r.get("when", {})
            rules.append(_Rule(
                name=r.get("name", r.get("fires", "")),
                event_type=r["fires"],
                intensity=float(r.get("intensity", default_intensity)),
                action=when.get("action"),
                topic=when.get("topic"),
                topic_in=tuple(when["topic_in"]) if when.get("topic_in") else None,
                engagement_kind=when.get("engagement_kind"),
                sentiment_gte=when.get("sentiment_gte"),
                sentiment_lt=when.get("sentiment_lt"),
                virality_gte=when.get("virality_gte"),
                virality_lt=when.get("virality_lt"),
                trait_gte=tuple((k, float(v)) for k, v in when.get("trait_gte", {}).items()),
                trait_lt=tuple((k, float(v)) for k, v in when.get("trait_lt", {}).items()),
            ))
        return cls(
            event_map=event_map,
            rules=tuple(rules),
            default_intensity=default_intensity,
        )

    @classmethod
    def from_json(cls, path: Path | str) -> DriftEventBridge:
        """Load bridge config from a JSON file."""
        p = Path(path)
        cfg = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(cfg)

    @classmethod
    def default(cls) -> DriftEventBridge:
        """Default bridge loaded from config/drift_events.json."""
        cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "drift_events.json"
        return cls.from_json(cfg_path)

    def build_engine(
        self,
        *,
        drift_volatility: float = 1.0,
        positive_multiplier: float = 1.0,
        negative_multiplier: float = 1.0,
        primary_traits: tuple[str, ...] | frozenset[str] = (),
        base_max_drift_ratio: float = 0.10,
    ) -> ExperienceDriftEngine:
        """Build an :class:`ExperienceDriftEngine` guaranteed to carry THIS
        bridge's full event catalog.

        Sprint 20: this factory exists because the bridge/engine coupling
        ("the engine's event_map must come from the same bridge whose rules
        emit the events") was previously enforced only by convention at
        call sites — and the one call site that forgot
        (``scripts/run_simulation.py``) silently no-op'd 9 of 15 event
        types for six sprints. Constructing through the bridge makes the
        invariant unbreakable.

        ``drift_volatility`` couples the two per-category speed knobs the
        way production always has: cumulative cap =
        ``base_max_drift_ratio * volatility`` and per-event
        ``intensity_scale = volatility``.
        """
        return ExperienceDriftEngine(
            max_drift_ratio=base_max_drift_ratio * float(drift_volatility),
            intensity_scale=float(drift_volatility),
            positive_multiplier=float(positive_multiplier),
            negative_multiplier=float(negative_multiplier),
            primary_trait_set=frozenset(primary_traits),
            event_map=self.event_map,
        )


# Forward reference for the type hint in current_traits without circular import.
from realm.agents.interfaces import Agent  # noqa: E402  (late import to avoid cycle)
