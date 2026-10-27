"""
Pass 2 Location & Niche Resolver for InstaHunt.
Resolves Tier 2 / Tier 3 Indian cities using hierarchical rule-based matching
across bio, post geo-tags, captions, and optional free-tier LLM inference.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from instahunt.config import INDIAN_TIER2_TIER3_CITIES, TIER1_METROS


@dataclass
class ResolutionResult:
    is_qualified: bool
    detected_city: Optional[str]
    city_tier: str  # "Tier 2", "Tier 3", "Tier 1", "Unknown"
    state: Optional[str]
    confidence: float
    evidence: str


class LocationResolver:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._build_city_regex_map()

    def _build_city_regex_map(self):
        """Pre-compile regex patterns for Tier 2/3 cities and their aliases."""
        self.city_patterns = []  # List of (pattern, canonical_city, tier, state)

        for canonical_city, (tier, state, aliases) in INDIAN_TIER2_TIER3_CITIES.items():
            all_terms = [canonical_city] + aliases
            for term in all_terms:
                escaped = re.escape(term)
                # Word boundary match
                pattern = re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)
                # Hashtag pattern (#jaipurblogger, #indore, etc.)
                ht_pattern = re.compile(r"#" + escaped + r"(?:blogger|influencer|creator|fashion|beauty|city)?\b", re.IGNORECASE)
                self.city_patterns.append((pattern, ht_pattern, canonical_city, tier, state))

    def resolve(self, profile_data: Dict) -> ResolutionResult:
        """
        Resolve location and verify eligibility for Tier 2/3 classification.
        profile_data keys expected:
        - biography: str
        - full_name: str
        - timeline_posts: List[Dict] with 'location_name', 'caption'
        """
        bio = profile_data.get("biography", "") or ""
        full_name = profile_data.get("full_name", "") or ""
        posts = profile_data.get("timeline_posts", []) or []

        # Extract locations and captions
        post_locations = [p.get("location_name", "") for p in posts if p.get("location_name")]
        locations_text = " | ".join(filter(None, post_locations))
        captions_text = " ".join(p.get("caption", "") for p in posts if p.get("caption"))

        # Step 1: Scan Bio (Highest Confidence)
        bio_corpus = f"{bio} {full_name}"
        for pattern, ht_pattern, city, tier, state in self.city_patterns:
            if pattern.search(bio_corpus) or ht_pattern.search(bio_corpus):
                capitalized_city = city.title()
                return ResolutionResult(
                    is_qualified=True,
                    detected_city=capitalized_city,
                    city_tier=tier,
                    state=state,
                    confidence=0.95,
                    evidence=f"Explicit {tier} city '{capitalized_city}' ({state}) declared in bio",
                )

        # Step 2: Scan Post Geo-Tags (High Confidence)
        if locations_text:
            for pattern, ht_pattern, city, tier, state in self.city_patterns:
                if pattern.search(locations_text):
                    capitalized_city = city.title()
                    return ResolutionResult(
                        is_qualified=True,
                        detected_city=capitalized_city,
                        city_tier=tier,
                        state=state,
                        confidence=0.88,
                        evidence=f"Geo-tag matched {tier} city '{capitalized_city}' in recent posts: '{locations_text[:80]}'",
                    )

        # Step 3: Scan Captions & Hashtags (Medium Confidence)
        if captions_text:
            for pattern, ht_pattern, city, tier, state in self.city_patterns:
                if ht_pattern.search(captions_text) or pattern.search(captions_text):
                    capitalized_city = city.title()
                    return ResolutionResult(
                        is_qualified=True,
                        detected_city=capitalized_city,
                        city_tier=tier,
                        state=state,
                        confidence=0.75,
                        evidence=f"Found hashtag/regional reference for {tier} city '{capitalized_city}' in captions",
                    )

        # Step 4: Fallback to LLM if configured
        if self.llm_client and self.llm_client.is_available():
            llm_result = self.llm_client.classify_profile(
                username=profile_data.get("username", ""),
                bio=bio,
                post_locations=post_locations,
                recent_captions=[p.get("caption", "")[:300] for p in posts[:5]],
            )
            if llm_result:
                city = llm_result.get("detected_city")
                tier = llm_result.get("city_tier", "Unknown")
                is_qual = tier in ("Tier 2", "Tier 3") and llm_result.get("is_skincare_creator", False)
                return ResolutionResult(
                    is_qualified=is_qual,
                    detected_city=city,
                    city_tier=tier,
                    state=llm_result.get("detected_state"),
                    confidence=0.80,
                    evidence=f"LLM Classification: {llm_result.get('evidence', '')}",
                )

        # Step 5: Unresolved Location
        return ResolutionResult(
            is_qualified=False,
            detected_city=None,
            city_tier="Unknown",
            state=None,
            confidence=0.0,
            evidence="Location could not be determined from bio, geo-tags, or captions (no Tier 2/3 city detected)",
        )
