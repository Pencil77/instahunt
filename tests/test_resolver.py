import pytest
from instahunt.resolver import LocationResolver


def test_resolver_explicit_bio_city():
    resolver = LocationResolver()
    profile = {
        "biography": "Skincare enthusiast in Jaipur. Loving organic products.",
        "full_name": "Pooja Sharma",
        "timeline_posts": [],
    }
    res = resolver.resolve(profile)
    assert res.is_qualified
    assert res.detected_city == "Jaipur"
    assert res.city_tier == "Tier 2"
    assert res.state == "Rajasthan"


def test_resolver_bio_alias():
    resolver = LocationResolver()
    # Pinkcity is alias for Jaipur
    profile = {
        "biography": "Beauty creator from Pinkcity | Skincare lover",
        "full_name": "Pinkcity Glow",
        "timeline_posts": [],
    }
    res = resolver.resolve(profile)
    assert res.is_qualified
    assert res.detected_city == "Jaipur"
    assert res.city_tier == "Tier 2"


def test_resolver_geo_tag_match():
    resolver = LocationResolver()
    profile = {
        "biography": "Daily skin routines and lifestyle reviews",
        "full_name": "Priya V",
        "timeline_posts": [
            {"location_name": "Hazratganj, Lucknow", "caption": "Fun day in town!"},
            {"location_name": "Lucknow, Uttar Pradesh", "caption": "Cafe review"},
        ],
    }
    res = resolver.resolve(profile)
    assert res.is_qualified
    assert res.detected_city == "Lucknow"
    assert res.city_tier == "Tier 2"
    assert res.state == "Uttar Pradesh"


def test_resolver_hashtag_match():
    resolver = LocationResolver()
    profile = {
        "biography": "Passionate about healthy glowing skin",
        "full_name": "Ananya",
        "timeline_posts": [
            {"location_name": "", "caption": "My favorite routine step! #indoreblogger #skincare"},
        ],
    }
    res = resolver.resolve(profile)
    assert res.is_qualified
    assert res.detected_city == "Indore"
    assert res.city_tier == "Tier 2"


def test_resolver_unknown_city():
    resolver = LocationResolver()
    profile = {
        "biography": "Travel and beauty addict living life to the fullest",
        "full_name": "Nomad Girl",
        "timeline_posts": [
            {"location_name": "Somewhere over the rainbow", "caption": "Sunshine days"},
        ],
    }
    res = resolver.resolve(profile)
    assert not res.is_qualified
    assert res.city_tier == "Unknown"
