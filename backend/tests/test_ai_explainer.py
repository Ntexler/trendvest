"""
Tests for AIExplainer — rate limiting, cache eviction, fallback behavior.
"""
import pytest
from datetime import date
from app.services.ai_explainer import AIExplainer


class TestRateLimiting:
    def test_fresh_user_has_quota(self):
        explainer = AIExplainer()
        allowed, remaining = explainer.check_rate_limit("user1")
        assert allowed is True
        assert remaining == 3

    def test_usage_decrements_remaining(self):
        explainer = AIExplainer()
        explainer.record_usage("user1")
        allowed, remaining = explainer.check_rate_limit("user1")
        assert allowed is True
        assert remaining == 2

    def test_limit_reached_after_3(self):
        explainer = AIExplainer()
        for _ in range(3):
            explainer.record_usage("user1")
        allowed, remaining = explainer.check_rate_limit("user1")
        assert allowed is False
        assert remaining == 0

    def test_separate_users_independent(self):
        explainer = AIExplainer()
        for _ in range(3):
            explainer.record_usage("user1")
        allowed, remaining = explainer.check_rate_limit("user2")
        assert allowed is True
        assert remaining == 3

    def test_stale_user_cleanup(self):
        explainer = AIExplainer()
        # Simulate a user from yesterday
        explainer._daily_usage["old_user"] = {"date": date(2020, 1, 1), "count": 5}
        # Checking a different user should clean up old_user
        explainer.check_rate_limit("new_user")
        assert "old_user" not in explainer._daily_usage

    def test_date_reset(self):
        explainer = AIExplainer()
        # Simulate usage from yesterday
        explainer._daily_usage["user1"] = {"date": date(2020, 1, 1), "count": 3}
        allowed, remaining = explainer.check_rate_limit("user1")
        assert allowed is True
        assert remaining == 3


class TestCacheEviction:
    def test_cache_set_basic(self):
        explainer = AIExplainer()
        explainer._cache_set("key1", "value1")
        assert explainer._cache["key1"] == "value1"
        assert "key1" in explainer._cache_order

    def test_cache_update_existing(self):
        explainer = AIExplainer()
        explainer._cache_set("key1", "value1")
        explainer._cache_set("key1", "value2")
        assert explainer._cache["key1"] == "value2"
        # Should not duplicate in order list
        assert explainer._cache_order.count("key1") == 1

    def test_cache_eviction_at_limit(self):
        explainer = AIExplainer()
        explainer.MAX_CACHE_SIZE = 3
        explainer._cache_set("k1", "v1")
        explainer._cache_set("k2", "v2")
        explainer._cache_set("k3", "v3")
        explainer._cache_set("k4", "v4")  # should evict k1
        assert "k1" not in explainer._cache
        assert "k4" in explainer._cache
        assert len(explainer._cache) == 3


class TestFallbackBehavior:
    @pytest.mark.asyncio
    async def test_ask_without_api_key_returns_fallback_he(self):
        explainer = AIExplainer()
        explainer.api_key = ""
        result = await explainer.ask("מה זה ETF?", user_id="test_user", language="he")
        assert "AI" in result["answer"] or "API" in result["answer"]
        assert isinstance(result["suggested_questions"], list)
        assert result["questions_remaining"] >= 0

    @pytest.mark.asyncio
    async def test_ask_without_api_key_returns_fallback_en(self):
        explainer = AIExplainer()
        explainer.api_key = ""
        result = await explainer.ask("What is an ETF?", user_id="test_user", language="en")
        assert "unavailable" in result["answer"].lower() or "api" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_explain_term_without_api_returns_term(self):
        explainer = AIExplainer()
        explainer.api_key = ""
        result = await explainer.explain_term("P/E Ratio", "en")
        assert result == "P/E Ratio"

    @pytest.mark.asyncio
    async def test_explain_section_without_api_returns_fallback(self):
        explainer = AIExplainer()
        explainer.api_key = ""
        result = await explainer.explain_section("AAPL", "financials", {"pe": 25}, "en")
        assert "unavailable" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_officer_bio_without_api_returns_empty(self):
        explainer = AIExplainer()
        explainer.api_key = ""
        result = await explainer.generate_officer_bio("Tim Cook", "CEO", "Apple", "en")
        assert result == ""

    @pytest.mark.asyncio
    async def test_translate_without_api_returns_original(self):
        explainer = AIExplainer()
        explainer.api_key = ""
        text = "Apple designs consumer electronics."
        result = await explainer.translate_text(text, "he", "AAPL")
        assert result == text

    @pytest.mark.asyncio
    async def test_translate_non_hebrew_returns_original(self):
        explainer = AIExplainer()
        text = "Some text"
        result = await explainer.translate_text(text, "en", "AAPL")
        assert result == text
