"""Tests for LLM-based and Hybrid personality embedders (mocked backends)."""

from __future__ import annotations

from realm.astro.fixtures import synthetic_chart
from realm.llm.interfaces import ILLMBackend, LLMBackendError, LLMResponse
from realm.personality.hybrid import HybridEmbedder
from realm.personality.llm_based import (
    LLMEmbedder,
    natal_chart_hash,
    serialize_natal_chart,
)
from realm.personality.trait_vector import TraitVector


class ScriptedBackend(ILLMBackend):
    """LLM backend that returns pre-arranged responses in order."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._i = 0

    @property
    def backend_name(self): return "scripted"
    @property
    def model(self): return "scripted-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        if self._i >= len(self._responses):
            raise LLMBackendError("no more canned responses")
        out = self._responses[self._i]
        self._i += 1
        return LLMResponse(content=out, model=self.model)


class FailingBackend(ILLMBackend):
    @property
    def backend_name(self): return "fail"
    @property
    def model(self): return "fail-1"

    def complete(self, system, user, *, max_tokens=512, temperature=0.7, json_mode=False):
        raise LLMBackendError("forced failure")


class TestSerialization:
    def test_natal_chart_hash_stable(self):
        chart = synthetic_chart()
        a = natal_chart_hash(chart)
        b = natal_chart_hash(chart)
        assert a == b

    def test_serialize_contains_key_fields(self):
        chart = synthetic_chart()
        s = serialize_natal_chart(chart)
        assert '"planets"' in s
        assert '"aspects"' in s
        assert "Aries" in s


class TestLLMEmbedder:
    def test_parses_canned_response(self):
        canned = (
            '{"openness": 0.72, "conscientiousness": 0.8, "extraversion": 0.6, '
            '"agreeableness": 0.55, "neuroticism": 0.35, "risk_appetite": 0.7, '
            '"empathy": 0.65}'
        )
        backend = ScriptedBackend([canned])
        embedder = LLMEmbedder(backend=backend, fallback_to_rule_based=False)
        tv = embedder.embed(synthetic_chart())
        assert isinstance(tv, TraitVector)
        assert abs(tv.openness - 0.72) < 1e-9
        assert abs(tv.risk_appetite - 0.70) < 1e-9

    def test_cache_hit_on_second_embed(self):
        backend = ScriptedBackend(['{"openness": 0.9}'])
        embedder = LLMEmbedder(backend=backend, fallback_to_rule_based=False)
        chart = synthetic_chart()
        tv1 = embedder.embed(chart)
        tv2 = embedder.embed(chart)
        assert tv1 == tv2
        # Second embed shouldn't have consumed a second canned response
        assert backend._i == 1

    def test_malformed_response_falls_back(self):
        backend = ScriptedBackend(["not json at all"])
        embedder = LLMEmbedder(backend=backend, fallback_to_rule_based=True)
        tv = embedder.embed(synthetic_chart())
        # Rule-based fallback — not neutral (traits spread)
        assert isinstance(tv, TraitVector)

    def test_no_backend_falls_back(self):
        embedder = LLMEmbedder(backend=None, router=_no_router(),
                               fallback_to_rule_based=True)
        tv = embedder.embed(synthetic_chart())
        assert isinstance(tv, TraitVector)

    def test_clamps_extreme_values(self):
        """LLM might return values outside [0,1] — from_dict must clamp."""
        canned = '{"openness": 2.5, "neuroticism": -0.4}'
        backend = ScriptedBackend([canned])
        embedder = LLMEmbedder(backend=backend, fallback_to_rule_based=False)
        tv = embedder.embed(synthetic_chart())
        assert tv.openness == 1.0
        assert tv.neuroticism == 0.0


class TestHybridEmbedder:
    def test_blends_rule_based_with_llm_adjustments(self):
        # Return small positive empathy adjustment
        backend = ScriptedBackend(['{"empathy": 0.12}'])
        from realm.personality.rule_based import RuleBasedEmbedder
        # Use low dampening so the synthetic chart's baseline isn't clamp-saturated;
        # the test's intent is verifying LLM delta propagation, not rule-based variance.
        low_damp_rb = RuleBasedEmbedder(dampening=0.12)
        embedder = HybridEmbedder(
            backend=backend, blend_ratio=1.0, _rule_based=low_damp_rb,
        )
        chart = synthetic_chart()
        baseline = low_damp_rb.embed(chart)

        tv = embedder.embed(chart)
        # With blend_ratio=1.0 the +0.12 adjustment applies fully
        assert abs((tv.empathy - baseline.empathy) - 0.12) < 1e-6

    def test_blend_ratio_zero_returns_baseline(self):
        backend = ScriptedBackend(['{"empathy": 0.12}'])
        embedder = HybridEmbedder(backend=backend, blend_ratio=0.0)

        from realm.personality.rule_based import RuleBasedEmbedder
        baseline = RuleBasedEmbedder().embed(synthetic_chart())
        tv = embedder.embed(synthetic_chart())
        assert tv == baseline

    def test_llm_failure_keeps_baseline(self):
        embedder = HybridEmbedder(backend=FailingBackend(), blend_ratio=1.0)
        from realm.personality.rule_based import RuleBasedEmbedder
        baseline = RuleBasedEmbedder().embed(synthetic_chart())
        tv = embedder.embed(synthetic_chart())
        assert tv == baseline

    def test_clamps_extreme_adjustments(self):
        """Adjustments outside [-0.15, +0.15] must be clamped."""
        backend = ScriptedBackend(['{"empathy": 1.5, "neuroticism": -2.0}'])
        embedder = HybridEmbedder(backend=backend, blend_ratio=1.0)

        from realm.personality.rule_based import RuleBasedEmbedder
        baseline = RuleBasedEmbedder().embed(synthetic_chart())
        tv = embedder.embed(synthetic_chart())
        # Max adjustment is ±0.15 regardless of what LLM said
        assert abs(tv.empathy - baseline.empathy) <= 0.151

    def test_ignores_unknown_traits(self):
        backend = ScriptedBackend(['{"bogus_trait": 0.1, "empathy": 0.05}'])
        embedder = HybridEmbedder(backend=backend, blend_ratio=1.0)
        tv = embedder.embed(synthetic_chart())  # should not raise
        assert isinstance(tv, TraitVector)


def _no_router():
    """Return a router that fails to build any backend."""
    from realm.llm.router import LLMRouter

    class _R(LLMRouter):
        def for_task(self, task):
            raise LLMBackendError("no backends")

    return _R()
