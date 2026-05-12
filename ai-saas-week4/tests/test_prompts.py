import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark.prompts import (
    SHORT_PROMPTS,
    MEDIUM_PROMPTS,
    LONG_PROMPTS,
    get_prompts_by_length,
    estimate_token_count
)


class TestPromptLists:
    def test_short_prompts_not_empty(self):
        assert len(SHORT_PROMPTS) > 0

    def test_medium_prompts_not_empty(self):
        assert len(MEDIUM_PROMPTS) > 0

    def test_long_prompts_not_empty(self):
        assert len(LONG_PROMPTS) > 0

    def test_short_prompts_are_short(self):
        for prompt in SHORT_PROMPTS:
            assert len(prompt) <= 128

    def test_medium_prompts_are_medium(self):
        for prompt in MEDIUM_PROMPTS:
            assert len(prompt) >= 35

    def test_long_prompts_are_long(self):
        for prompt in LONG_PROMPTS:
            assert len(prompt) >= 110

    def test_all_prompts_are_strings(self):
        for prompt in SHORT_PROMPTS + MEDIUM_PROMPTS + LONG_PROMPTS:
            assert isinstance(prompt, str)
            assert len(prompt) > 0


class TestGetPromptsByLength:
    def test_get_short_prompts(self):
        prompts = get_prompts_by_length("short", count=10)
        assert len(prompts) == 10
        for p in prompts:
            assert p in SHORT_PROMPTS

    def test_get_medium_prompts(self):
        prompts = get_prompts_by_length("medium", count=10)
        assert len(prompts) == 10
        for p in prompts:
            assert p in MEDIUM_PROMPTS

    def test_get_long_prompts(self):
        prompts = get_prompts_by_length("long", count=10)
        assert len(prompts) == 10
        for p in prompts:
            assert p in LONG_PROMPTS

    def test_get_all_prompts(self):
        prompts = get_prompts_by_length("all", count=30)
        assert len(prompts) == 30

    def test_get_all_includes_all_lengths(self):
        prompts = get_prompts_by_length("all", count=500)
        has_short = any(p in SHORT_PROMPTS for p in prompts)
        has_medium = any(p in MEDIUM_PROMPTS for p in prompts)
        has_long = any(p in LONG_PROMPTS for p in prompts)
        assert has_short
        assert has_medium
        assert has_long

    def test_count_exact(self):
        prompts = get_prompts_by_length("short", count=5)
        assert len(prompts) == 5

    def test_count_larger_than_available(self):
        prompts = get_prompts_by_length("short", count=500)
        assert len(prompts) == 500

    def test_count_zero(self):
        prompts = get_prompts_by_length("short", count=0)
        assert len(prompts) == 0

    def test_count_one(self):
        prompts = get_prompts_by_length("short", count=1)
        assert len(prompts) == 1

    def test_default_count(self):
        prompts = get_prompts_by_length("short")
        assert len(prompts) == 100

    def test_short_prompts_cover_100(self):
        prompts = get_prompts_by_length("short", count=100)
        assert len(prompts) == 100

    def test_medium_prompts_cover_100(self):
        prompts = get_prompts_by_length("medium", count=100)
        assert len(prompts) == 100

    def test_long_prompts_cover_100(self):
        prompts = get_prompts_by_length("long", count=100)
        assert len(prompts) == 100

    def test_all_prompts_cover_100(self):
        prompts = get_prompts_by_length("all", count=100)
        assert len(prompts) == 100


class TestEstimateTokenCount:
    def test_empty_string(self):
        assert estimate_token_count("") == 0

    def test_short_text(self):
        tokens = estimate_token_count("Hello world")
        assert tokens == 2

    def test_medium_text(self):
        text = "This is a longer text with approximately twenty characters"
        tokens = estimate_token_count(text)
        assert tokens > 0

    def test_custom_chars_per_token(self):
        text = "Hello world, this is a test"
        tokens_default = estimate_token_count(text)
        tokens_custom = estimate_token_count(text, chars_per_token=2.0)
        assert tokens_custom > tokens_default

    def test_estimate_is_integer(self):
        result = estimate_token_count("Hello world")
        assert isinstance(result, int)
