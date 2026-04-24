"""Tests for the prompt YAML loader."""

from __future__ import annotations

import pytest

from realm.core.exceptions import DataError
from realm.llm.prompts import clear_cache, load_prompt


def setup_function(fn):
    clear_cache()


class TestLoadPrompt:
    def test_load_personality_system(self):
        p = load_prompt("personality/system")
        assert p.name.startswith("personality_system")
        assert p.version >= 1
        assert "natal chart" in p.content.lower()

    def test_load_personality_user_template(self):
        p = load_prompt("personality/user_template")
        # must contain a placeholder
        assert "$chart_json" in p.content

    def test_load_spotlight_narrative(self):
        p = load_prompt("spotlight/narrative")
        for placeholder in ("$name", "$age", "$country", "$topic", "$sentiment_descriptor"):
            assert placeholder in p.content

    def test_unknown_prompt_raises(self):
        with pytest.raises(DataError):
            load_prompt("does/not/exist")


class TestRender:
    def test_substitutes_placeholders(self):
        p = load_prompt("personality/user_template")
        rendered = p.render(chart_json='{"sun":"Aries"}')
        assert '{"sun":"Aries"}' in rendered
        assert "$chart_json" not in rendered

    def test_missing_placeholder_left_intact(self):
        """safe_substitute shouldn't blow up on missing keys."""
        p = load_prompt("spotlight/narrative")
        # Render with only a subset of placeholders
        rendered = p.render(name="Test", age="30")
        assert "Test" in rendered
        assert "$country" in rendered   # remaining placeholder stays
