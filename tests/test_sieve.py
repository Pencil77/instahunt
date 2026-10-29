import pytest
from instahunt.sieve import DeterministicSieve


def test_sieve_rejects_private_account():
    sieve = DeterministicSieve(min_avg_comments=100)
    profile = {
        "full_name": "Private User",
        "biography": "Skincare enthusiast in Jaipur",
        "is_private": True,
        "timeline_posts": [
            {"comments_count": 200, "is_pinned": False, "caption": "Morning skincare routine"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert res.rejection_reason == "private_account"
    assert "Private account" in res.evidence


def test_sieve_insufficient_posts():
    sieve = DeterministicSieve(min_avg_comments=100, min_unpinned_posts=8)
    profile = {
        "full_name": "Test Creator",
        "biography": "Skincare routine tips in Jaipur",
        "timeline_posts": [
            {"comments_count": 150, "is_pinned": False, "caption": "Morning skincare routine"},
            {"comments_count": 130, "is_pinned": False, "caption": "Sunscreen review"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert "insufficient_unpinned_posts" in res.rejection_reason


def test_sieve_low_trimmed_mean():
    sieve = DeterministicSieve(min_avg_comments=100, min_unpinned_posts=8)
    # 8 posts: sorted [20, 25, 30, 35, 40, 45, 50, 1000]
    # Dropping bottom 1 (20) and top 2 (50, 1000) -> [25, 30, 35, 40, 45] -> avg = 35 < 100
    profile = {
        "full_name": "Test Creator",
        "biography": "Skincare routine tips in Jaipur",
        "timeline_posts": [
            {"comments_count": 20, "is_pinned": False, "caption": "Post 1 skincare"},
            {"comments_count": 25, "is_pinned": False, "caption": "Post 2 sunscreen"},
            {"comments_count": 30, "is_pinned": False, "caption": "Post 3 serum"},
            {"comments_count": 35, "is_pinned": False, "caption": "Post 4 cleanser"},
            {"comments_count": 40, "is_pinned": False, "caption": "Post 5 moisturizer"},
            {"comments_count": 45, "is_pinned": False, "caption": "Post 6 barrier care"},
            {"comments_count": 50, "is_pinned": False, "caption": "Post 7 retinol"},
            {"comments_count": 1000, "is_pinned": False, "caption": "Viral reel"},
        ],
    }
    res = sieve.evaluate(profile)
    assert not res.passed
    assert "low_comments" in res.rejection_reason or "low_median" in res.rejection_reason


def test_sieve_pinned_and_giveaway_exclusion():
    sieve = DeterministicSieve(min_avg_comments=100, min_unpinned_posts=8)
    # 10 posts: 1 pinned, 1 giveaway, 8 valid with comments >= 110
    profile = {
        "full_name": "Test Creator",
        "biography": "Skincare educator in Indore",
        "timeline_posts": [
            {"comments_count": 5000, "is_pinned": True, "caption": "Pinned intro"},
            {"comments_count": 2500, "is_pinned": False, "caption": "Big GIVEAWAY! Tag 3 friends to win a kit"},
            {"comments_count": 120, "is_pinned": False, "caption": "Niacinamide review"},
            {"comments_count": 110, "is_pinned": False, "caption": "Daily cleanser review"},
            {"comments_count": 130, "is_pinned": False, "caption": "Moisturizer test"},
            {"comments_count": 115, "is_pinned": False, "caption": "Barrier repair routine"},
            {"comments_count": 140, "is_pinned": False, "caption": "Sunscreen texture test"},
            {"comments_count": 125, "is_pinned": False, "caption": "Ceramide creams for acne"},
            {"comments_count": 135, "is_pinned": False, "caption": "Retinol for beginners"},
            {"comments_count": 120, "is_pinned": False, "caption": "Salicylic acid face wash"},
        ],
    }
    res = sieve.evaluate(profile)
    assert res.passed
    assert res.giveaway_posts_excluded == 1
    assert res.unpinned_posts_count == 8
    assert res.trimmed_mean_comments >= 100.0


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


def test_sieve_suburb_rejection():
    sieve = DeterministicSieve(min_avg_comments=100)
    # Testing suburb blacklist (Bandra, Noida, Koramangala)
    profile_bandra = {
        "full_name": "Riya Bandra",
        "biography": "Skincare tips | Bandra girl 🌸",
        "timeline_posts": [{"comments_count": 150, "is_pinned": False, "caption": "Serum review"}],
    }
    res = sieve.evaluate(profile_bandra)
    assert not res.passed
    assert res.matched_tier1_metro == "bandra"

    profile_noida = {
        "full_name": "Simran V",
        "biography": "Skincare routine | Sector 62 Noida",
        "timeline_posts": [{"comments_count": 150, "is_pinned": False, "caption": "Sunscreen review"}],
    }
    res2 = sieve.evaluate(profile_noida)
    assert not res2.passed
    assert res2.matched_tier1_metro == "noida"


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
    sieve = DeterministicSieve(min_avg_comments=100, min_unpinned_posts=8)
    profile = {
        "full_name": "Sonali Rao",
        "biography": "Skincare educator based in Jaipur 🌸 Honest acne & serum reviews",
        "timeline_posts": [
            {"comments_count": 140, "is_pinned": False, "caption": "Sunscreen test for acne prone skin"},
            {"comments_count": 120, "is_pinned": False, "caption": "Glow routine with niacinamide"},
            {"comments_count": 130, "is_pinned": False, "caption": "Salicylic acid cleanser routine"},
            {"comments_count": 110, "is_pinned": False, "caption": "Ceramide barrier repair cream"},
            {"comments_count": 125, "is_pinned": False, "caption": "Centella calming serum review"},
            {"comments_count": 135, "is_pinned": False, "caption": "Pharmacy skincare finds in Jaipur"},
            {"comments_count": 115, "is_pinned": False, "caption": "Acne dark spots routine"},
            {"comments_count": 128, "is_pinned": False, "caption": "Double cleansing guide for glowing skin"},
        ],
    }
    res = sieve.evaluate(profile)
    assert res.passed
    assert res.trimmed_mean_comments >= 100.0
    assert res.median_comments >= 75.0
    assert res.consistency_count >= 6
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
    sieve = DeterministicSieve(min_avg_comments=100, min_unpinned_posts=8)

    # South India (Tamil Nadu) - English/Tamil skincare terms
    p_tamil = {
        "full_name": "Keerthi Skin Lab",
        "biography": "Coimbatore | Pharmacy skincare & barrier repair tips 🧴 #tamilskincare",
        "timeline_posts": [
            {"comments_count": 180, "is_pinned": False, "caption": "Niacinamide serum for acne prone skin. Best budget finds in Tamil Nadu."},
            {"comments_count": 170, "is_pinned": False, "caption": "Salicylic acid cleanser review #tamilskincare"},
            {"comments_count": 165, "is_pinned": False, "caption": "Barrier repair moisturizer in Coimbatore"},
            {"comments_count": 160, "is_pinned": False, "caption": "Sunscreen for humid weather"},
            {"comments_count": 175, "is_pinned": False, "caption": "Ceramide cream comparison"},
            {"comments_count": 155, "is_pinned": False, "caption": "Centella soothing gel"},
            {"comments_count": 185, "is_pinned": False, "caption": "Hyaluronic acid vs glycerin"},
            {"comments_count": 190, "is_pinned": False, "caption": "Daily skin health routine"},
        ],
    }
    res_tamil = sieve.evaluate(p_tamil)
    assert res_tamil.passed
    assert res_tamil.is_skincare
