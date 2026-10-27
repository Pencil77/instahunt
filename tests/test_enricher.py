import pytest
from instahunt.enricher import CommentQualityAuditor
from instahunt.service_account import ServiceAccountManager


def test_comment_quality_genuine():
    auditor = CommentQualityAuditor()
    comments = [
        "Is this serum good for acne and oily skin?",
        "How to use this retinol in night routine?",
        "Where to buy? Link please!",
        "Kaha se liya ye sunscreen? Review please",
    ]
    res = auditor.audit_sample_comments(comments)
    assert res.quality_grade == "A"
    assert res.authenticity_score >= 0.70
    assert res.genuine_signals_count >= 3


def test_comment_quality_spam():
    auditor = CommentQualityAuditor()
    comments = [
        "🔥🔥",
        "❤️❤️❤️",
        "nice",
        "super",
        "follow me",
        "cool",
    ]
    res = auditor.audit_sample_comments(comments)
    assert res.quality_grade == "C"
    assert res.authenticity_score < 0.40
    assert res.spam_signals_count >= 4


def test_service_account_manager_fallback():
    # Tests that manager gracefully handles absent or mock environment
    mgr = ServiceAccountManager()
    status = mgr.get_status()
    assert "has_credentials" in status
    assert "is_authenticated" in status
