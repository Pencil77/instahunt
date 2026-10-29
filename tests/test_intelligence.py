"""
Unit tests for InstaHunt AI Intelligence Engine (Multi-provider LLM Layer).
Tests cascading failover, JSON extraction, geography disambiguation,
vernacular detection, community quality audit, and smart dork generation.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from instahunt.intelligence import (
    AIIntelligenceEngine,
    BaseLLMProvider,
    CommunityAudit,
    GroqProvider,
    LocationAnalysis,
    NicheAnalysis,
    NvidiaNIMProvider,
    OpenRouterProvider,
)


class DummyMockProvider(BaseLLMProvider):
    def __init__(self, name="mock", response=None, should_fail=False):
        self.name = name
        self.response = response
        self.should_fail = should_fail

    def is_configured(self) -> bool:
        return True

    def chat_completion(self, messages, max_tokens=500, temperature=0.1, timeout=15):
        if self.should_fail:
            raise ConnectionError("Mock network failure")
        return self.response


def test_json_extraction():
    engine = AIIntelligenceEngine(providers=[])

    # Direct JSON
    assert engine._extract_json_block('{"key": "value"}') == {"key": "value"}

    # Markdown block
    md = "Here is the result:\n```json\n{\"city\": \"Indore\", \"tier\": \"Tier 2\"}\n```\nHope it helps!"
    assert engine._extract_json_block(md) == {"city": "Indore", "tier": "Tier 2"}

    # Embedded braces
    raw = "Sure, result is {\"status\": \"ok\", \"code\": 200} with extra text."
    assert engine._extract_json_block(raw) == {"status": "ok", "code": 200}

    # Invalid JSON
    assert engine._extract_json_block("No json here") is None


def test_cascading_failover():
    # First provider fails, second succeeds
    p1 = DummyMockProvider(name="fail_prov", should_fail=True)
    p2 = DummyMockProvider(name="success_prov", response="pong")

    engine = AIIntelligenceEngine(providers=[p1, p2])
    content, prov_name = engine.chat_completion([{"role": "user", "content": "hi"}])
    assert content == "pong"
    assert prov_name == "success_prov"


def test_all_providers_fail_returns_fallback():
    p1 = DummyMockProvider(name="p1", should_fail=True)
    p2 = DummyMockProvider(name="p2", response=None)

    engine = AIIntelligenceEngine(providers=[p1, p2])
    content, prov_name = engine.chat_completion([{"role": "user", "content": "hi"}])
    assert content is None
    assert prov_name == "fallback"


def test_disambiguate_location_via_mock():
    mock_json = json.dumps({
        "detected_city": "Bhopal",
        "detected_state": "Madhya Pradesh",
        "city_tier": "Tier 2",
        "is_tier2_tier3": True,
        "confidence": 0.95,
        "evidence": "Creator explicitly tagged MP Nagar, Bhopal",
    })
    mock_prov = DummyMockProvider(name="mock_ai", response=mock_json)
    engine = AIIntelligenceEngine(providers=[mock_prov])

    res = engine.disambiguate_location(
        username="bhopal_glow",
        bio="Skin influencer based in Bhopal",
        post_locations=["MP Nagar, Bhopal"],
    )

    assert isinstance(res, LocationAnalysis)
    assert res.detected_city == "Bhopal"
    assert res.city_tier == "Tier 2"
    assert res.is_tier2_tier3 is True
    assert res.confidence == 0.95
    assert res.provider_used == "mock_ai"


def test_disambiguate_location_tier1_metro_rejection():
    mock_json = json.dumps({
        "detected_city": "Mumbai",
        "detected_state": "Maharashtra",
        "city_tier": "Tier 1",
        "is_tier2_tier3": False,
        "confidence": 0.99,
        "evidence": "Bandra, Mumbai",
    })
    mock_prov = DummyMockProvider(name="mock_ai", response=mock_json)
    engine = AIIntelligenceEngine(providers=[mock_prov])

    res = engine.disambiguate_location(
        username="mumbai_chic",
        bio="Mumbai fashion and beauty creator",
    )

    assert res.is_tier2_tier3 is False
    assert res.city_tier == "Tier 1"


def test_fallback_location_disambiguation():
    # Engine with no active providers triggers local deterministic rules
    engine = AIIntelligenceEngine(providers=[])

    # Tier 2 city
    res = engine.disambiguate_location(
        username="jaipur_skin",
        bio="Loving organic beauty in Jaipur, Rajasthan!",
    )
    assert res.detected_city == "Jaipur"
    assert res.city_tier == "Tier 2"
    assert res.is_tier2_tier3 is True
    assert res.provider_used == "rule-based"

    # Tier 1 metro
    res_metro = engine.disambiguate_location(
        username="delhi_beauty",
        bio="Delhi based beauty blogger",
    )
    assert res_metro.city_tier == "Tier 1"
    assert res_metro.is_tier2_tier3 is False
    assert res_metro.provider_used == "rule-based"


def test_niche_assessment_vernacular_detection():
    engine = AIIntelligenceEngine(providers=[])  # triggers fallback heuristic

    res = engine.assess_skincare_niche(
        username="desi_nuskhe",
        bio="Ghar ke nuskhe and haldi ubtan remedies for glowing acne free skin",
        recent_captions=["Sharing my daily dahi besan mask for pigmentation"],
    )

    assert isinstance(res, NicheAnalysis)
    assert res.is_skincare_creator is True
    assert res.niche_score >= 0.70
    assert "ghar ke nuskhe" in res.vernacular_signals or "haldi" in res.vernacular_signals


def test_community_quality_audit():
    mock_json = json.dumps({
        "community_grade": "A",
        "authenticity_score": 0.92,
        "spam_pod_ratio": 0.08,
        "summary": "Authentic audience discussions on acne and sunscreen textures",
    })
    mock_prov = DummyMockProvider(name="mock_ai", response=mock_json)
    engine = AIIntelligenceEngine(providers=[mock_prov])

    audit = engine.assess_community_quality(
        username="skin_doc",
        comments_sample=["Is this good for oily skin?", "Does it leave white cast?"],
        avg_comments=140.0,
    )

    assert isinstance(audit, CommunityAudit)
    assert audit.community_grade == "A"
    assert audit.authenticity_score == 0.92
    assert audit.spam_pod_ratio == 0.08


def test_smart_dorks_generation():
    engine = AIIntelligenceEngine(providers=[])
    dorks = engine.generate_smart_dorks(
        cities=["Indore", "Surat"],
        brands=["Minimalist", "Foxtale"],
        max_queries=4,
    )

    assert len(dorks) == 4
    for d in dorks:
        assert "site:instagram.com" in d["query"]
        assert d["city"] in ("Indore", "Surat")


def test_pass2_auditor_zero_tolerance_unknown_city():
    # When no city can be verified, Pass 2 must reject with zero unknown tolerance
    engine = AIIntelligenceEngine(providers=[])
    profile = {
        "username": "skincare_india_glow",
        "full_name": "Indian Glow",
        "biography": "Best skincare tips across India! Glowing skin and serums.",
        "timeline_posts": [
            {"comments_count": 120, "caption": "Niacinamide routine for glowing skin"} for _ in range(10)
        ],
    }
    res = engine.audit_creator_pass2(profile)
    assert not res.passes_all_criteria
    assert res.city_tier == "Unknown"
    assert res.rejection_reason == "unverified_city_zero_tolerance"


def test_pass2_auditor_tier1_rejection():
    engine = AIIntelligenceEngine(providers=[])
    profile = {
        "username": "mumbai_glow_expert",
        "full_name": "Pooja Mumbai",
        "biography": "Skincare educator based in Andheri, Mumbai 🧴",
        "timeline_posts": [
            {"comments_count": 140, "caption": "Double cleansing guide for glowing skin"} for _ in range(10)
        ],
    }
    res = engine.audit_creator_pass2(profile)
    assert not res.passes_all_criteria
    assert res.city_tier == "Tier 1"
    assert "tier1_metro" in res.rejection_reason


def test_pass2_auditor_skincare_ratio_rule():
    # Only 2 out of 10 posts are skincare, 8 are fashion/lifestyle -> must reject (< 50%)
    engine = AIIntelligenceEngine(providers=[])
    profile = {
        "username": "jaipur_fashion_girl",
        "full_name": "Simran Jaipur",
        "biography": "Jaipur creator ✨ Fashion & occasional skincare",
        "timeline_posts": [
            {"comments_count": 120, "caption": "My favorite sunscreen review"},
            {"comments_count": 130, "caption": "Acne routine with salicylic acid"},
            {"comments_count": 110, "caption": "OOTD styling my lehenga for wedding"},
            {"comments_count": 115, "caption": "Cafe hopping and fashion vlog"},
            {"comments_count": 125, "caption": "GRWM outfit for summer"},
            {"comments_count": 135, "caption": "Zara haul and try on video"},
            {"comments_count": 140, "caption": "Saree draping tutorial in Jaipur"},
            {"comments_count": 110, "caption": "Jewelry collection styling"},
            {"comments_count": 105, "caption": "My daily vlog in Jaipur"},
            {"comments_count": 115, "caption": "Street food tour in pink city"},
        ],
    }
    res = engine.audit_creator_pass2(profile)
    assert not res.passes_all_criteria
    assert res.skincare_posts_out_of_10 == 2
    assert "low_skincare_ratio" in res.rejection_reason


def test_pass2_auditor_qualified_tier2_creator():
    # Positive Tier 2 proof (Indore) + >= 50% skincare posts + individual creator
    engine = AIIntelligenceEngine(providers=[])
    profile = {
        "username": "indore_skin_notes",
        "full_name": "Rhea S - Skincare",
        "biography": "Indore | Certified aesthetician sharing barrier care & honest sunscreen reviews 🧴",
        "timeline_posts": [
            {"comments_count": 120, "caption": "Ceramide barrier repair moisturizer review in Indore"},
            {"comments_count": 130, "caption": "How to treat active acne with salicylic acid"},
            {"comments_count": 110, "caption": "Sunscreen texture testing with UV camera"},
            {"comments_count": 115, "caption": "Morning skincare routine for glowing skin"},
            {"comments_count": 125, "caption": "Niacinamide vs Vitamin C for hyperpigmentation"},
            {"comments_count": 135, "caption": "Pharmacy skincare gems under 500"},
            {"comments_count": 140, "caption": "Double cleansing routine for clogged pores"},
            {"comments_count": 110, "caption": "Retinol dos and donts for beginners"},
            {"comments_count": 105, "caption": "Centella soothing serum test"},
            {"comments_count": 115, "caption": "My current night time routine"},
        ],
    }
    res = engine.audit_creator_pass2(profile)
    assert res.passes_all_criteria
    assert res.city_tier == "Tier 2"
    assert res.detected_city == "Indore"
    assert res.skincare_posts_out_of_10 >= 5
    assert res.is_individual_creator is True
    assert res.rejection_reason is None

