"""
Engagement Quality and Comment Authenticity Enricher for InstaHunt.
Optional enhancement module to calculate confidence scores, community quality grades,
and deep recommendation graph expansion.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class EnrichmentResult:
    authenticity_score: float  # 0.0 to 1.0
    quality_grade: str         # "A", "B", "C"
    genuine_signals_count: int
    spam_signals_count: int
    summary: str


# Regex patterns identifying authentic engagement in Indian beauty/skincare communities
GENUINE_COMMENT_PATTERNS = [
    r"\b(price|cost|where to buy|link|kaha se|kaise|review|results|how to use)\b",
    r"\b(dry skin|oily skin|combination skin|sensitive skin|acne|pores|pigmentation)\b",
    r"\b(sunscreen|serum|retinol|niacinamide|salicylic|moisturizer|cleanser)\b",
    r"\b(safe for|pregnancy safe|side effect|routine|step|recommend|honest)\b",
    r"\b(fayda|kaisa hai|suit karega|meri skin|daily use|glow)\b",
]

SPAM_PATTERNS = [
    r"^([🔥❤️👏😍🙌✨👍🎉\s]+)$",  # Emoji-only comments
    r"\b(follow me|dm me|check inbox|paid promo|dm to promote|inbox me)\b",
    r"^(nice|super|cool|osm|awesome|beautiful|mast|nyc|gr8)\s*$",
]


class CommentQualityAuditor:
    def __init__(self):
        self.genuine_re = [re.compile(p, re.IGNORECASE) for p in GENUINE_COMMENT_PATTERNS]
        self.spam_re = [re.compile(p, re.IGNORECASE) for p in SPAM_PATTERNS]

    def audit_sample_comments(self, comments: List[str]) -> EnrichmentResult:
        """
        Analyze comment texts for genuine community discussions vs bot/pod spam.
        Returns authenticity score (0.0 to 1.0) and letter grade (A/B/C).
        """
        if not comments:
            return EnrichmentResult(
                authenticity_score=0.5,
                quality_grade="B",
                genuine_signals_count=0,
                spam_signals_count=0,
                summary="No individual comments sampled; default baseline applied",
            )

        genuine_hits = 0
        spam_hits = 0

        for text in comments:
            t = text.strip()
            if not t:
                continue

            is_genuine = any(r.search(t) for r in self.genuine_re)
            is_spam = any(r.search(t) for r in self.spam_re)

            if is_genuine:
                genuine_hits += 1
            elif is_spam or len(t) <= 3:
                spam_hits += 1

        total = len(comments)
        # Ratio of genuine inquiries vs spam
        # Base score 0.5; positive for genuine inquiries, negative for spam
        raw_score = (genuine_hits * 1.5 - spam_hits * 0.5) / max(total, 1)
        normalized_score = max(0.1, min(0.99, 0.5 + raw_score * 0.5))

        if normalized_score >= 0.70:
            grade = "A"
            summary = "High-quality active community with genuine product and routine discussions"
        elif normalized_score >= 0.40:
            grade = "B"
            summary = "Standard organic engagement with healthy mix of community queries and reactions"
        else:
            grade = "C"
            summary = "Heavy concentration of generic emoji or engagement pod activity"

        return EnrichmentResult(
            authenticity_score=round(normalized_score, 2),
            quality_grade=grade,
            genuine_signals_count=genuine_hits,
            spam_signals_count=spam_hits,
            summary=summary,
        )
