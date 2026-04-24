"""Tests for get_input_adapter() factory."""

from __future__ import annotations

import pytest

from realm.core.exceptions import PersonalityEmbeddingError
from realm.personality.adapters import (
    AstrologicalAdapter,
    BigFiveAdapter,
    DemographicAdapter,
    get_input_adapter,
)


class TestGetInputAdapter:
    def test_astrological(self):
        a = get_input_adapter("astrological")
        assert isinstance(a, AstrologicalAdapter)
        assert a.adapter_type == "astrological"

    def test_big_five(self):
        a = get_input_adapter("big_five")
        assert isinstance(a, BigFiveAdapter)
        assert a.adapter_type == "big_five"

    def test_demographic(self):
        a = get_input_adapter("demographic")
        assert isinstance(a, DemographicAdapter)
        assert a.adapter_type == "demographic"

    def test_unknown_raises(self):
        with pytest.raises(PersonalityEmbeddingError, match="unknown input adapter"):
            get_input_adapter("quantum_telepathy")

    def test_default_reads_config(self):
        """With no arg, falls back to realm.yaml or 'astrological' default."""
        a = get_input_adapter()
        # Regardless of config state, must be a valid adapter
        assert a.adapter_type in ("astrological", "big_five", "demographic")
