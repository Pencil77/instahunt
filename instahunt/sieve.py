"""
Pass 1 & Gate 1/2 Deterministic Zero-Cost Sieve for InstaHunt v2.
Implements:
- Gate 1: Anti-Giveaway & Robust Trimmed Comment Math
  * Excludes pinned posts and giveaway captions
  * Enforces minimum unpinned, non-giveaway posts (default: 8)
  * Calculates trimmed mean (dropping top 2 highest and bottom 1 lowest)
  * Enforces dual thresholds: trimmed_mean >= 100, median floor >= 75,
    and consistency >= 6 out of 10 posts with >= 65 comments.
- Gate 2: Exhaustive Tier-1 Metro & Suburb Blacklist (Python regex scan).
- Skincare keyword relevance and niche exclusivity verification.
"""

import json
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from instahunt.config import (
    CONSISTENCY_MIN_COMMENTS,
    CONSISTENCY_MIN_COUNT,
    DISQUALIFYING_NICHE_KEYWORDS,
    DROP_BOTTOM_POSTS,
    DROP_TOP_POSTS,
    EXCLUDE_PINNED_POSTS,
    GIVEAWAY_PATTERN_STR,
    MEDIAN_COMMENTS_FLOOR,
    MIN_AVG_COMMENTS,
    MIN_UNPINNED_POSTS,
    REGIONAL_SKINCARE_MARKERS,
    SAMPLE_POSTS_COUNT,
    SKINCARE_KEYWORDS,
    TIER1_METROS,
    TRIMMED_MEAN_COMMENTS_THRESHOLD,
)


@dataclass
class SieveResult:
    passed: bool
    avg_comments: float  # Raw average
    trimmed_mean_comments: float  # Gate 1 Trimmed Mean (dropping top 2, bottom 1)
    median_comments: float  # Gate 1 Median floor
    consistency_count: int  # Posts with >= 65 comments
    total_posts_evaluated: int
    unpinned_posts_count: int
    giveaway_posts_excluded: int
    comment_counts_sample: List[int]
    is_skincare: bool
    skincare_keywords_found: List[str]
    has_tier1_match: bool
    matched_tier1_metro: Optional[str] = None
    rejection_reason: Optional[str] = None
    evidence: str = ""


class DeterministicSieve:
    def __init__(
        self,
        min_avg_comments: float = TRIMMED_MEAN_COMMENTS_THRESHOLD,
        median_floor: float = MEDIAN_COMMENTS_FLOOR,
        consistency_min_count: int = CONSISTENCY_MIN_COUNT,
        consistency_min_comments: float = CONSISTENCY_MIN_COMMENTS,
        min_unpinned_posts: int = MIN_UNPINNED_POSTS,
        exclude_pinned: bool = EXCLUDE_PINNED_POSTS,
        sample_posts_count: int = SAMPLE_POSTS_COUNT,
        drop_top: int = DROP_TOP_POSTS,
        drop_bottom: int = DROP_BOTTOM_POSTS,
    ):
        self.min_avg_comments = min_avg_comments
        self.median_floor = median_floor
        self.consistency_min_count = consistency_min_count
        self.consistency_min_comments = consistency_min_comments
        self.min_unpinned_posts = min_unpinned_posts
        self.exclude_pinned = exclude_pinned
        self.sample_posts_count = sample_posts_count
        self.drop_top = drop_top
        self.drop_bottom = drop_bottom

        # Pre-compile regex for Giveaway indicators (Gate 1)
        self.giveaway_pattern = re.compile(GIVEAWAY_PATTERN_STR, re.IGNORECASE)

        # Pre-compile regex for Tier 1 metros with word boundaries (Gate 2)
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

    def calculate_engagement_metrics(
        self, posts: List[Dict]
    ) -> Tuple[bool, float, float, float, int, int, int, List[int], Optional[str], str]:
        """
        Gate 1: Anti-Giveaway & Robust Trimmed Comment Math.
        Returns:
        (passed, raw_avg, trimmed_mean, median, consistency_count,
         unpinned_count, giveaway_count, comment_counts, rejection_reason, evidence)
        """
        if not posts:
            return False, 0.0, 0.0, 0.0, 0, 0, 0, [], "no_posts", "Profile has 0 timeline posts"

        # 1. Exclude Pinned Posts
        unpinned = []
        for p in posts:
            if p.get("is_pinned") is True:
                continue
            unpinned.append(p)

        # Fallback if is_pinned flag is absent but grid has >= 4 posts:
        if len(unpinned) == len(posts) and len(posts) >= 4:
            ts4 = int(posts[3].get("taken_at_timestamp", 0) or 0)
            if ts4 > 0:
                filtered = []
                for i, p in enumerate(posts):
                    ts = int(p.get("taken_at_timestamp", 0) or 0)
                    if i < 3 and ts > 0 and ts < ts4:
                        continue  # pinned old post
                    filtered.append(p)
                unpinned = filtered

        # 2. Exclude Giveaway Posts
        non_giveaway = []
        giveaway_count = 0
        for p in unpinned:
            caption = str(p.get("caption", "") or "")
            if self.giveaway_pattern.search(caption):
                giveaway_count += 1
                continue
            non_giveaway.append(p)

        unpinned_count = len(non_giveaway)
        if unpinned_count == 0:
            return (
                False,
                0.0,
                0.0,
                0.0,
                0,
                0,
                giveaway_count,
                [],
                "no_unpinned_posts",
                "Profile has 0 unpinned non-giveaway posts",
            )

        # Enforce minimum unpinned posts requirement
        if self.min_unpinned_posts > 0 and unpinned_count < self.min_unpinned_posts:
            # If posts are fewer than min_unpinned_posts, compute basic average for reporting
            all_counts = [int(p.get("comments_count", 0) or 0) for p in non_giveaway]
            raw_avg = sum(all_counts) / len(all_counts) if all_counts else 0.0
            return (
                False,
                raw_avg,
                raw_avg,
                raw_avg,
                0,
                unpinned_count,
                giveaway_count,
                all_counts,
                f"insufficient_unpinned_posts_{unpinned_count}_min_{self.min_unpinned_posts}",
                f"Profile has only {unpinned_count} unpinned non-giveaway posts (Minimum required: {self.min_unpinned_posts})",
            )

        # Sample up to sample_posts_count
        eval_posts = non_giveaway[: self.sample_posts_count]
        comment_counts = [int(p.get("comments_count", 0) or 0) for p in eval_posts]
        raw_avg = sum(comment_counts) / len(comment_counts) if comment_counts else 0.0

        # Calculate Median on the unpinned posts (up to 10)
        recent_10_counts = comment_counts[:10]
        median_comments = float(statistics.median(recent_10_counts)) if recent_10_counts else 0.0

        # Consistency check: posts with >= 65 comments
        consistency_count = sum(1 for c in recent_10_counts if c >= self.consistency_min_comments)

        # 3. Trimmed Mean Calculation: Sort ascending, drop top 2 and bottom 1
        sorted_counts = sorted(comment_counts)
        if len(sorted_counts) >= (self.drop_top + self.drop_bottom + 2):
            trimmed_slice = sorted_counts[self.drop_bottom : -self.drop_top]
            trimmed_mean = sum(trimmed_slice) / len(trimmed_slice)
        else:
            trimmed_mean = raw_avg

        # Check Gate 1 Thresholds
        if trimmed_mean < self.min_avg_comments:
            return (
                False,
                raw_avg,
                trimmed_mean,
                median_comments,
                consistency_count,
                unpinned_count,
                giveaway_count,
                comment_counts,
                f"low_comments_{trimmed_mean:.1f}_below_{self.min_avg_comments:.0f}",
                f"Trimmed mean comments {trimmed_mean:.1f} (raw avg {raw_avg:.1f}) is below {self.min_avg_comments:.0f} threshold",
            )

        if median_comments < self.median_floor:
            return (
                False,
                raw_avg,
                trimmed_mean,
                median_comments,
                consistency_count,
                unpinned_count,
                giveaway_count,
                comment_counts,
                f"low_median_{median_comments:.1f}_below_floor_{self.median_floor:.0f}",
                f"Median comments {median_comments:.1f} is below floor of {self.median_floor:.0f}",
            )

        if consistency_count < self.consistency_min_count:
            return (
                False,
                raw_avg,
                trimmed_mean,
                median_comments,
                consistency_count,
                unpinned_count,
                giveaway_count,
                comment_counts,
                f"low_consistency_{consistency_count}_of_{len(recent_10_counts)}_min_{self.consistency_min_count}",
                f"Only {consistency_count}/{len(recent_10_counts)} posts have >= {self.consistency_min_comments:.0f} comments (Required: {self.consistency_min_count})",
            )

        return (
            True,
            raw_avg,
            trimmed_mean,
            median_comments,
            consistency_count,
            unpinned_count,
            giveaway_count,
            comment_counts,
            None,
            f"Gate 1 Passed: Trimmed Mean {trimmed_mean:.1f}, Median {median_comments:.1f}, Consistency {consistency_count}/{len(recent_10_counts)}",
        )

    def evaluate(self, profile_data: Dict) -> SieveResult:
        """
        Evaluate profile against Stage 1 deterministic criteria:
        0. Privacy check
        1. Gate 2: Hard Tier 1 Metro & Suburb Blacklist
        2. Strict Niche Exclusivity Disqualification
        3. Skincare Niche Relevance & Keyword Density
        4. Gate 1: Anti-Giveaway & Robust Trimmed Comment Math
        """
        bio = str(profile_data.get("biography", "") or "")
        full_name = str(profile_data.get("full_name", "") or "")
        posts = profile_data.get("timeline_posts", []) or []

        # 0. Privacy Check: Private accounts are strictly ineligible
        if profile_data.get("is_private") is True:
            return SieveResult(
                passed=False,
                avg_comments=0.0,
                trimmed_mean_comments=0.0,
                median_comments=0.0,
                consistency_count=0,
                total_posts_evaluated=0,
                unpinned_posts_count=0,
                giveaway_posts_excluded=0,
                comment_counts_sample=[],
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason="private_account",
                evidence="Private account: profile content and reels cannot be publicly accessed or verified",
            )

        # 1. Gate 2: Hard Tier 1 Metro & Suburb Blacklist Evaluation
        locations = [str(p.get("location_name", "") or "") for p in posts if p.get("location_name")]
        locations_text = " ".join(filter(None, locations))

        business_addr = profile_data.get("business_address_json") or ""
        if isinstance(business_addr, dict):
            business_addr = json.dumps(business_addr)
        else:
            business_addr = str(business_addr)

        text_corpus = f"{bio} {full_name} {locations_text} {business_addr}".lower()

        tier1_match = self.tier1_pattern.search(text_corpus)
        if tier1_match:
            matched_name = tier1_match.group(1).lower()
            return SieveResult(
                passed=False,
                avg_comments=0.0,
                trimmed_mean_comments=0.0,
                median_comments=0.0,
                consistency_count=0,
                total_posts_evaluated=len(posts),
                unpinned_posts_count=0,
                giveaway_posts_excluded=0,
                comment_counts_sample=[],
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=True,
                matched_tier1_metro=matched_name,
                rejection_reason=f"tier1_metro_{matched_name}",
                evidence=f"Gate 2 Disqualified: Matched Tier 1 blacklisted metro/suburb '{matched_name}' in bio/locations",
            )

        # 2. Strict Niche Exclusivity Disqualification Check
        captions_text = " ".join(
            str(p.get("caption", "") or "")[:200] for p in posts[:12] if p.get("caption")
        )
        niche_corpus = f"{bio} {full_name} {captions_text}".lower()

        disqualify_match = self.disqualifying_pattern.search(niche_corpus)
        if disqualify_match:
            matched_niche = disqualify_match.group(1).lower()
            return SieveResult(
                passed=False,
                avg_comments=0.0,
                trimmed_mean_comments=0.0,
                median_comments=0.0,
                consistency_count=0,
                total_posts_evaluated=len(posts),
                unpinned_posts_count=0,
                giveaway_posts_excluded=0,
                comment_counts_sample=[],
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason=f"disqualified_niche_{matched_niche}",
                evidence=f"Disqualified for non-exclusive skincare marker '{matched_niche}' (client requires pure skincare exclusivity)",
            )

        # 3. Skincare Niche Relevance & Keyword Density
        found_keywords = list(set(self.skincare_pattern.findall(niche_corpus)))
        found_regional = list(set(self.regional_pattern.findall(niche_corpus)))
        all_skincare_matches = list(set(found_keywords + found_regional))

        if not all_skincare_matches:
            return SieveResult(
                passed=False,
                avg_comments=0.0,
                trimmed_mean_comments=0.0,
                median_comments=0.0,
                consistency_count=0,
                total_posts_evaluated=len(posts),
                unpinned_posts_count=0,
                giveaway_posts_excluded=0,
                comment_counts_sample=[],
                is_skincare=False,
                skincare_keywords_found=[],
                has_tier1_match=False,
                rejection_reason="not_skincare",
                evidence="Zero skincare-related keywords found in bio or recent captions",
            )

        # Bio dedication check
        bio_lower = f"{bio} {full_name}".lower()
        has_skincare_in_bio = bool(
            self.skincare_pattern.search(bio_lower) or self.regional_pattern.search(bio_lower)
        )
        if not has_skincare_in_bio and len(all_skincare_matches) < 2:
            return SieveResult(
                passed=False,
                avg_comments=0.0,
                trimmed_mean_comments=0.0,
                median_comments=0.0,
                consistency_count=0,
                total_posts_evaluated=len(posts),
                unpinned_posts_count=0,
                giveaway_posts_excluded=0,
                comment_counts_sample=[],
                is_skincare=False,
                skincare_keywords_found=all_skincare_matches,
                has_tier1_match=False,
                rejection_reason="low_skincare_density",
                evidence=f"Only 1 casual skincare term found ('{all_skincare_matches[0]}') and bio lacks dedicated skincare focus",
            )

        # 4. Gate 1: Anti-Giveaway & Robust Comment Math
        (
            math_passed,
            raw_avg,
            trimmed_mean,
            median,
            consistency,
            unpinned_cnt,
            giveaway_cnt,
            counts_sample,
            math_rejection,
            math_evidence,
        ) = self.calculate_engagement_metrics(posts)

        if not math_passed:
            return SieveResult(
                passed=False,
                avg_comments=raw_avg,
                trimmed_mean_comments=trimmed_mean,
                median_comments=median,
                consistency_count=consistency,
                total_posts_evaluated=len(posts),
                unpinned_posts_count=unpinned_cnt,
                giveaway_posts_excluded=giveaway_cnt,
                comment_counts_sample=counts_sample,
                is_skincare=True,
                skincare_keywords_found=all_skincare_matches,
                has_tier1_match=False,
                rejection_reason=math_rejection,
                evidence=math_evidence,
            )

        # Passed Pass 1 Sieve (Gate 1 & Gate 2)
        return SieveResult(
            passed=True,
            avg_comments=raw_avg,
            trimmed_mean_comments=trimmed_mean,
            median_comments=median,
            consistency_count=consistency,
            total_posts_evaluated=len(posts),
            unpinned_posts_count=unpinned_cnt,
            giveaway_posts_excluded=giveaway_cnt,
            comment_counts_sample=counts_sample,
            is_skincare=True,
            skincare_keywords_found=all_skincare_matches,
            has_tier1_match=False,
            rejection_reason=None,
            evidence=f"Passed Gate 1 & 2: Trimmed Mean {trimmed_mean:.1f}, Median {median:.1f}, Consistency {consistency}, Skincare: {', '.join(all_skincare_matches[:3])}",
        )
