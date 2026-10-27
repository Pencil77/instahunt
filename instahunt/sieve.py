"""
Pass 1 Deterministic Zero-Cost Sieve for InstaHunt.
Applies mathematical comment threshold, Tier 1 metro blacklist,
and skincare keyword density without calling any LLM.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from instahunt.config import (
    DISQUALIFYING_NICHE_KEYWORDS,
    EXCLUDE_PINNED_POSTS,
    MIN_AVG_COMMENTS,
    REGIONAL_SKINCARE_MARKERS,
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

        # Pre-compile regex for strict disqualifying niche keywords
        escaped_disqualifiers = [re.escape(k) for k in DISQUALIFYING_NICHE_KEYWORDS]
        self.disqualifying_pattern = re.compile(
            r"\b(" + "|".join(escaped_disqualifiers) + r")\b",
            re.IGNORECASE,
        )

        # Pre-compile regex for core skincare keywords
        escaped_keywords = [re.escape(k) for k in SKINCARE_KEYWORDS]
        self.skincare_pattern = re.compile(
            r"\b(" + "|".join(escaped_keywords) + r")\b",
            re.IGNORECASE,
        )

        # Pre-compile regex for Pan-Indian regional skincare markers
        all_regional_markers = []
        for marker_list in REGIONAL_SKINCARE_MARKERS.values():
            all_regional_markers.extend(marker_list)
        escaped_regional = [re.escape(m) for m in all_regional_markers]
        self.regional_pattern = re.compile(
            r"\b(" + "|".join(escaped_regional) + r")\b",
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

        # 0. Privacy Check: Private accounts are strictly ineligible
        if profile_data.get("is_private") is True:
            return SieveResult(
                passed=False,
                avg_comments=0.0,
                total_posts_evaluated=0,
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason="private_account",
                evidence="Private account: profile content and reels cannot be publicly accessed or verified",
            )

        # 1. Comment Math Evaluation
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

        # 3. Strict Niche Exclusivity Disqualification Check
        niche_corpus = f"{bio} {full_name} {captions_text}".lower()
        disqualify_match = self.disqualifying_pattern.search(niche_corpus)
        if disqualify_match:
            matched_niche = disqualify_match.group(1).lower()
            return SieveResult(
                passed=False,
                avg_comments=avg_comments,
                total_posts_evaluated=total_evaluated,
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason=f"disqualified_niche_{matched_niche}",
                evidence=f"Disqualified for non-exclusive skincare niche marker '{matched_niche}' (client requires pure skincare exclusivity)",
            )

        # 4. Skincare Niche Relevance & Density Evaluation
        found_keywords = list(set(self.skincare_pattern.findall(niche_corpus)))
        found_regional = list(set(self.regional_pattern.findall(niche_corpus)))
        all_skincare_matches = list(set(found_keywords + found_regional))

        if not all_skincare_matches:
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

        # Check skincare density / bio dedication
        bio_lower = f"{bio} {full_name}".lower()
        has_skincare_in_bio = bool(self.skincare_pattern.search(bio_lower) or self.regional_pattern.search(bio_lower))
        if not has_skincare_in_bio and len(all_skincare_matches) < 2:
            return SieveResult(
                passed=False,
                avg_comments=avg_comments,
                total_posts_evaluated=total_evaluated,
                is_skincare=False,
                skincare_keywords_found=all_skincare_matches,
                has_tier1_match=False,
                rejection_reason="low_skincare_density",
                evidence=f"Only 1 casual skincare term found ('{all_skincare_matches[0]}') and bio lacks dedicated skincare focus",
            )

        # Passed Pass 1 Sieve
        return SieveResult(
            passed=True,
            avg_comments=avg_comments,
            total_posts_evaluated=total_evaluated,
            is_skincare=True,
            skincare_keywords_found=all_skincare_matches,
            has_tier1_match=False,
            rejection_reason=None,
            evidence=f"Passed sieve with {avg_comments:.1f} avg comments and dedicated skincare markers: {', '.join(all_skincare_matches[:3])}",
        )
