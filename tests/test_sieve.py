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


def test_sieve_disqualifies_non_exclusive_niches():
    sieve = DeterministicSieve(min_avg_comments=100)
    
    # 1. Lifestyle vlogger
    p1 = {
        "full_name": "Meenu",
        "biography": "Daily vlogs, lifestyle creator & family moments in Bhopal",
        "timeline_posts": [
            {"comments_count": 150, "is_pinned": False, "caption": "My morning skincare and daily vlog"},
        ],
    }
    res1 = sieve.evaluate(p1)
    assert not res1.passed
    assert "disqualified_niche" in res1.rejection_reason

    # 2. Bridal MUA
    p2 = {
        "full_name": "Kanishka",
        "biography": "Bridal makeup artist & MUA Jaipur. Bookings open for weddings.",
        "timeline_posts": [
            {"comments_count": 220, "is_pinned": False, "caption": "Bridal glow skincare prep"},
        ],
    }
    res2 = sieve.evaluate(p2)
    assert not res2.passed
    assert "disqualified_niche" in res2.rejection_reason

    # 3. Nutritionist
    p3 = {
        "full_name": "Sarah",
        "biography": "Clinical nutritionist and dietitian in Chandigarh. Weight loss plans.",
        "timeline_posts": [
            {"comments_count": 140, "is_pinned": False, "caption": "Diet for glowing skin and acne"},
        ],
    }
    res3 = sieve.evaluate(p3)
    assert not res3.passed
    assert "disqualified_niche" in res3.rejection_reason

    # 4. Mens grooming & fashion
    p4 = {
        "full_name": "Dhamo",
        "biography": "Mens grooming & style blogger Coimbatore. OOTD & beard care.",
        "timeline_posts": [
            {"comments_count": 250, "is_pinned": False, "caption": "Daily sunscreen for men"},
        ],
    }
    res4 = sieve.evaluate(p4)
    assert not res4.passed
    assert "disqualified_niche" in res4.rejection_reason


def test_sieve_pan_india_regional_skincare():
    sieve = DeterministicSieve(min_avg_comments=100)

    # South India (Tamil Nadu) - English/Tamil skincare terms
    p_tamil = {
        "full_name": "Keerthi Skin Lab",
        "biography": "Coimbatore | Pharmacy skincare & barrier repair tips 🧴 #tamilskincare",
        "timeline_posts": [
            {"comments_count": 180, "is_pinned": False, "caption": "Niacinamide serum for acne prone skin. Best budget finds in Tamil Nadu."},
        ],
    }
    res_tamil = sieve.evaluate(p_tamil)
    assert res_tamil.passed
    assert res_tamil.is_skincare

    # West India (Gujarat) - Gujarati/English skincare
    p_gujarat = {
        "full_name": "Rutu Patel",
        "biography": "Surat | Dedicated skincare reviewer, sunscreen testing & ceramides ✨ #gujaratskincare",
        "timeline_posts": [
            {"comments_count": 160, "is_pinned": False, "caption": "Chamakti twacha and barrier restoration guide for dry skin in Surat."},
        ],
    }
    res_gujarat = sieve.evaluate(p_gujarat)
    assert res_gujarat.passed
    assert res_gujarat.is_skincare
