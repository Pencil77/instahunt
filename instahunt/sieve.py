"""
Pass 1 Deterministic Zero-Cost Sieve for InstaHunt.
Applies mathematical comment threshold, Tier 1 metro blacklist,
and skincare keyword density without calling any LLM.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from instahunt.config import (
    EXCLUDE_PINNED_POSTS,
    MIN_AVG_COMMENTS,
    SAMPLE_POSTS_COUNT,
    SKINCARE_KEYWORDS,
    TIER1_METROS,
)


@dataclass
class SieveResult:
    passed: bool
    avg_comments: float
    total_posts_evaluated: int
    is_skincare: bool
    skincare_keywords_found: List[str]
    has_tier1_match: bool
    matched_tier1_metro: Optional[str] = None
    rejection_reason: Optional[str] = None
    evidence: str = ""


class DeterministicSieve:
    def __init__(
        self,
        min_avg_comments: float = MIN_AVG_COMMENTS,
        exclude_pinned: bool = EXCLUDE_PINNED_POSTS,
        sample_posts_count: int = SAMPLE_POSTS_COUNT,
    ):
        self.min_avg_comments = min_avg_comments
        self.exclude_pinned = exclude_pinned
        self.sample_posts_count = sample_posts_count

        # Pre-compile regex for Tier 1 metros with word boundaries
        escaped_metros = [re.escape(m) for m in TIER1_METROS.keys()]
        self.tier1_pattern = re.compile(
            r"\b(" + "|".join(escaped_metros) + r")\b",
            re.IGNORECASE,
        )

        # Pre-compile regex for skincare keywords
        escaped_keywords = [re.escape(k) for k in SKINCARE_KEYWORDS]
        self.skincare_pattern = re.compile(
            r"\b(" + "|".join(escaped_keywords) + r")\b",
            re.IGNORECASE,
        )

    def evaluate(self, profile_data: Dict) -> SieveResult:
        """
        Evaluate profile against Stage 1 deterministic criteria.
        profile_data keys expected:
        - biography: str
        - full_name: str
        - timeline_posts: List[Dict] with 'comments_count', 'is_pinned', 'caption', 'location_name'
        """
        bio = profile_data.get("biography", "") or ""
        full_name = profile_data.get("full_name", "") or ""
        posts = profile_data.get("timeline_posts", []) or []

        # 1. Comment Math Evaluation
        # Filter posts
        eval_posts = posts
        if self.exclude_pinned:
            unpinned = [p for p in posts if not p.get("is_pinned", False)]
            if unpinned:
                eval_posts = unpinned
        
        # Take up to sample_posts_count
        eval_posts = eval_posts[: self.sample_posts_count]

        if not eval_posts:
            avg_comments = 0.0
            total_evaluated = 0
        else:
            total_comments = sum(int(p.get("comments_count", 0) or 0) for p in eval_posts)
            total_evaluated = len(eval_posts)
            avg_comments = total_comments / total_evaluated

        if avg_comments < self.min_avg_comments:
            return SieveResult(
                passed=False,
                avg_comments=avg_comments,
                total_posts_evaluated=total_evaluated,
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason=f"low_comments_{avg_comments:.1f}_below_{self.min_avg_comments}",
                evidence=f"Average comments {avg_comments:.1f} across {total_evaluated} posts (Threshold: {self.min_avg_comments})",
            )

        # 2. Hard Tier 1 Metro Blacklist Evaluation
        # Aggregate text from bio, full_name, and post locations
        locations = [p.get("location_name", "") for p in posts if p.get("location_name")]
        locations_text = " ".join(filter(None, locations))
        captions_text = " ".join(p.get("caption", "")[:200] for p in eval_posts if p.get("caption"))
        
        text_corpus = f"{bio} {full_name} {locations_text}".lower()

        tier1_match = self.tier1_pattern.search(text_corpus)
        if tier1_match:
            matched_name = tier1_match.group(1).lower()
            return SieveResult(
                passed=False,
                avg_comments=avg_comments,
                total_posts_evaluated=total_evaluated,
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=True,
                matched_tier1_metro=matched_name,
                rejection_reason=f"tier1_metro_{matched_name}",
                evidence=f"Matched Tier 1 blacklisted metro '{matched_name}' in bio/locations",
            )

        # 3. Skincare Niche Relevance Evaluation
        niche_corpus = f"{bio} {captions_text}".lower()
        found_keywords = list(set(self.skincare_pattern.findall(niche_corpus)))

        if not found_keywords:
            return SieveResult(
                passed=False,
                avg_comments=avg_comments,
                total_posts_evaluated=total_evaluated,
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason="not_skincare",
                evidence="Zero skincare-related keywords found in bio or recent captions",
            )

        # Passed Pass 1 Sieve
        return SieveResult(
            passed=True,
            avg_comments=avg_comments,
            total_posts_evaluated=total_evaluated,
            is_skincare=True,
            skincare_keywords_found=found_keywords,
            has_tier1_match=False,
            rejection_reason=None,
            evidence=f"Passed sieve with {avg_comments:.1f} avg comments and keywords: {', '.join(found_keywords[:3])}",
        )
