import pytest
from pathlib import Path
from instahunt.db import (
    boost_related_priority,
    enqueue_profiles,
    get_next_queued_profile,
    get_qualified_profiles,
    get_stats,
    init_db,
    is_profile_seen,
    mark_queue_status,
    upsert_profile,
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_instahunt.db"
    init_db(db_file)
    return db_file


def test_enqueue_and_fifo_priority(test_db):
    added = enqueue_profiles(["creator1", "creator2"], source="test", priority=10, db_path=test_db)
    assert added == 2

    # Add a high priority creator
    enqueue_profiles(["creator_vip"], source="vip", priority=100, db_path=test_db)

    # Next item should be VIP
    item = get_next_queued_profile(test_db)
    assert item is not None
    _, username, source = item
    assert username == "creator_vip"
    assert source == "vip"


def test_deduplication(test_db):
    enqueue_profiles(["creator1"], source="test", priority=10, db_path=test_db)
    # Re-enqueue should not duplicate
    added2 = enqueue_profiles(["creator1"], source="test", priority=10, db_path=test_db)
    assert added2 == 0
    assert is_profile_seen("creator1", test_db)


def test_upsert_and_qualified_retrieval(test_db):
    profile = {
        "username": "sonali.rao22",
        "full_name": "Sonali Rao",
        "biography": "Jaipur skincare educator",
        "followers_count": 45000,
        "avg_comments": 140.5,
        "detected_city": "Jaipur",
        "city_tier": "Tier 2",
        "is_skincare": True,
        "status": "qualified",
        "evidence": "Passed test criteria",
    }
    upsert_profile(profile, test_db)

    qualified = get_qualified_profiles(test_db)
    assert len(qualified) == 1
    assert qualified[0]["username"] == "sonali.rao22"
    assert qualified[0]["detected_city"] == "Jaipur"

    stats = get_stats(test_db)
    assert stats["total_profiles"] == 1
    assert stats["qualified"] == 1
