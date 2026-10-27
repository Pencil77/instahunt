import pytest
from instahunt.sieve import DeterministicSieve


def test_sieve_low_comments():
    sieve = DeterministicSieve(min_avg_comments=100)
    profile = {
        "full_name": "Test Creator",
        "biography": "Skincare routine tips in Jaipur",
        "timeline_posts": [
            {"comments_count": 25, "is_pinned": False, "caption": "Morning skincare routine"},
            {"comments_count": 30, "is_pinned": False, "caption": "Sunscreen review"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert "low_comments" in res.rejection_reason
    assert res.avg_comments == 27.5


def test_sieve_pinned_post_exclusion():
    sieve = DeterministicSieve(min_avg_comments=100, exclude_pinned=True)
    # Post with 1000 comments is pinned giveaway, others have 20 comments
    profile = {
        "full_name": "Test Creator",
        "biography": "Skincare enthusiast in Indore",
        "timeline_posts": [
            {"comments_count": 1000, "is_pinned": True, "caption": "GIVEAWAY WINNER ANNOUNCEMENT!"},
            {"comments_count": 30, "is_pinned": False, "caption": "Daily cleanser review"},
            {"comments_count": 40, "is_pinned": False, "caption": "Moisturizer test"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert res.avg_comments == 35.0  # Pinned 1000 ignored!


def test_sieve_tier1_rejection():
    sieve = DeterministicSieve(min_avg_comments=100)
    profile = {
        "full_name": "Aanya Sharma",
        "biography": "Skincare and acne tips based in Mumbai. Glowing skin secrets.",
        "timeline_posts": [
            {"comments_count": 150, "is_pinned": False, "caption": "My favorite serums"},
            {"comments_count": 180, "is_pinned": False, "caption": "Retinol guide"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert res.has_tier1_match
    assert res.matched_tier1_metro == "mumbai"
    assert "tier1_metro" in res.rejection_reason


def test_sieve_not_skincare():
    sieve = DeterministicSieve(min_avg_comments=100)
    profile = {
        "full_name": "Tech Guy",
        "biography": "Smartphone unboxing and gadget reviews. Bhopal.",
        "timeline_posts": [
            {"comments_count": 200, "is_pinned": False, "caption": "iPhone 16 unboxing"},
            {"comments_count": 150, "is_pinned": False, "caption": "Best laptops 2026"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert res.rejection_reason == "not_skincare"


def test_sieve_qualified_candidate():
    sieve = DeterministicSieve(min_avg_comments=100)
    profile = {
        "full_name": "Sonali Rao",
        "biography": "Skincare educator based in Jaipur 🌸 Honest acne & serum reviews",
        "timeline_posts": [
            {"comments_count": 140, "is_pinned": False, "caption": "Sunscreen test for acne prone skin"},
            {"comments_count": 120, "is_pinned": False, "caption": "Glow routine with niacinamide"},
        ],
    }
    res = sieve.evaluate(profile)
    assert res.passed
    assert res.avg_comments == 130.0
    assert res.is_skincare
    assert not res.has_tier1_match
