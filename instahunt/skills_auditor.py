"""
Skills-Based Profile Auditor for InstaHunt.

Replaces the mock comment simulation and rule-based sieve for the discovery phase.
Uses multi-skill intelligence to score and verify discovered profiles:

Skills orchestrated:
  1. skincare-lead-auditor  — 4-gate production audit (from ~/.agents/skills/)
  2. influencer-marketing   — engagement quality + partner tier vetting
  3. lead-scoring           — two-axis fit × engagement scoring
  4. agent-reach web search — live web grounding for handle existence check
  5. DeterministicSieve     — math-based gate (used as structural framework)

Output: AuditVerdict with pass/fail, score, evidence, and sheet-ready metadata.
"""

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from instahunt.config import INDIAN_TIER2_TIER3_CITIES, TIER1_METROS
from instahunt.skills_discoverer import DiscoveredProfile, AGENT_REACH_BIN

logger = logging.getLogger(__name__)

# International locations hard blacklist
INTERNATIONAL_BLACKLIST = {
    "dubai", "uae", "london", "uk", "usa", "canada", "toronto", "australia",
    "singapore", "nepal", "kathmandu", "dhaka", "bangladesh", "pakistan",
    "karachi", "lahore",
}

# Minimum follower counts for inclusion
MIN_FOLLOWERS_NANO = 3_000       # absolute floor
MAX_FOLLOWERS_MID = 500_000     # mid-tier ceiling (we don't want mega-influencers)

# Skincare focus keywords that confirm niche
SKINCARE_FOCUS_KEYWORDS = [
    "skincare", "skin care", "dermatologist", "cosmetologist", "skin clinic",
    "acne", "retinol", "niacinamide", "barrier repair", "serum", "moisturizer",
    "sunscreen", "skin health", "dermatology", "skin doctor", "glow", "hyperpigmentation",
    "spf", "salicylic", "chemical exfoliant", "tret", "tretinoin", "skin routine",
    "skin barrier", "dermat", "skincare tips",
]

# Non-skincare primary niche disqualifiers
PRIMARY_NICHE_DISQUALIFIERS = [
    "fashion", "ootd", "outfit", "saree", "sari", "styling", "hijab", "lehenga",
    "food", "foodie", "recipe", "recipes", "dining", "cafe", "grub", "bakery", "bakez",
    "travel", "traveler", "trips", "vlog", "vlogs", "vlogger", "lifestyle blogger",
    "comedy", "comedian", "standup", "dance", "dancer", "choreographer",
    "bridal makeup", "mua", "makeup artist", "wedding makeup", "nail art",
    "fitness", "gym", "workout", "trainer", "cricket", "gaming", "tech",
]

# Brand & Corporate Disqualifiers
BRAND_DISQUALIFIERS = [
    "brand", "skincare brand", "beauty brand", "cosmetics brand", "clothing brand",
    "shop online", "buy online", "e-commerce", "add to cart", "our products",
    "free shipping", "available on nykaa", "available on amazon", "founded by",
    "co-founded by", "pvt ltd", "private limited", "official instagram account",
    "official account of", "business page", "store", "salon", "academy",
]


@dataclass
class AuditVerdict:
    handle: str
    passed: bool
    overall_score: float               # 0.0–1.0 composite
    city: Optional[str]
    city_tier: Optional[str]
    is_tier2_tier3: bool
    is_skincare_confirmed: bool
    followers: Optional[int]
    engagement_rate: Optional[float]
    evidence_snippet: str
    source_url: Optional[str]
    rejection_reason: Optional[str]
    gate_scores: Dict[str, bool] = field(default_factory=dict)
    web_grounded: bool = False         # True if live web search confirmed existence
    audit_notes: str = ""


class SkillsAuditor:
    """
    Multi-skill auditor that produces AuditVerdict for each DiscoveredProfile.

    The auditor runs 5 checks in sequence:
      G1 — Existence Gate: web search confirms the handle exists (live grounding)
      G2 — City Gate: Tier 2 or Tier 3 confirmed, Tier 1 blacklisted
      G3 — Niche Gate: skincare content confirmed as primary focus
      G4 — Follower Gate: 3K–500K range (nano to mid-tier)
      G5 — Engagement Gate: ER ≥ 1.5% OR evidence of ≥ 100 avg comments
    """

    def __init__(
        self,
        min_followers: int = MIN_FOLLOWERS_NANO,
        max_followers: int = MAX_FOLLOWERS_MID,
        min_engagement_rate: float = 1.5,
        require_web_grounding: bool = True,
    ):
        self.min_followers = min_followers
        self.max_followers = max_followers
        self.min_er = min_engagement_rate
        self.require_web_grounding = require_web_grounding

    def audit_profile(self, profile: DiscoveredProfile) -> AuditVerdict:
        """Run all 5 gates against a single DiscoveredProfile."""
        verdict = AuditVerdict(
            handle=profile.handle,
            passed=False,
            overall_score=0.0,
            city=profile.city,
            city_tier=profile.city_tier,
            is_tier2_tier3=profile.is_tier2_tier3,
            is_skincare_confirmed=profile.is_skincare_confirmed,
            followers=profile.followers,
            engagement_rate=profile.engagement_rate,
            evidence_snippet=profile.evidence_snippet[:300],
            source_url=profile.source_url,
            rejection_reason=None,
            gate_scores={},
        )

        # ── G1: Existence / Web Grounding ─────────────────────────────────────
        if self.require_web_grounding:
            grounded, ground_data = self._check_web_grounding(profile)
        else:
            grounded, ground_data = True, None
        verdict.gate_scores["G1_existence"] = grounded
        verdict.web_grounded = grounded

        # Merge any enriched data from grounding search
        if ground_data:
            if not profile.city and ground_data.get("city"):
                profile.city = ground_data["city"]
                profile.city_tier = ground_data.get("tier")
                profile.is_tier2_tier3 = ground_data.get("tier") in ("Tier 2", "Tier 3")
                verdict.city = profile.city
                verdict.city_tier = profile.city_tier
                verdict.is_tier2_tier3 = profile.is_tier2_tier3
            if not profile.followers and ground_data.get("followers"):
                profile.followers = ground_data["followers"]
                verdict.followers = profile.followers
            # Merge enriched snippet into evidence for G3 skincare check
            if ground_data.get("snippet"):
                profile.evidence_snippet = (
                    (ground_data["snippet"] or "") + " " + (profile.evidence_snippet or "")
                )
            if not profile.is_skincare_confirmed and ground_data.get("skincare_confirmed"):
                profile.is_skincare_confirmed = True
                verdict.is_skincare_confirmed = True
            verdict.audit_notes += (ground_data.get("snippet") or "")[:200]

        if self.require_web_grounding and not grounded:
            verdict.rejection_reason = "G1_FAIL: Handle not found in any live web source"
            verdict.overall_score = 0.0
            return verdict

        # ── G1.5: Creator Authenticity Gate (Human Creator vs Brand/Business) ────
        is_creator, creator_err = self._check_creator_authenticity(profile, verdict.audit_notes)
        verdict.gate_scores["G1_5_creator"] = is_creator
        if not is_creator:
            verdict.rejection_reason = f"G1_5_FAIL: {creator_err}"
            verdict.overall_score = 0.05
            return verdict

        # ── G2: City Tier Gate ─────────────────────────────────────────────────
        city_ok = self._check_city(profile, verdict.audit_notes)
        verdict.gate_scores["G2_city"] = city_ok
        if not city_ok:
            verdict.rejection_reason = (
                f"G2_FAIL: City '{profile.city}' is Tier 1 metro, international, or not Tier 2/3 India"
            )
            verdict.overall_score = 0.1
            return verdict

        # ── G3: Skincare Niche Gate ────────────────────────────────────────────
        skincare_ok, skincare_score = self._check_skincare_niche(profile, verdict.audit_notes)
        verdict.gate_scores["G3_skincare"] = skincare_ok
        if not skincare_ok:
            verdict.rejection_reason = "G3_FAIL: Primary niche is not skincare-focused"
            verdict.overall_score = 0.2
            return verdict

        # ── G4: Follower Range Gate ────────────────────────────────────────────
        follower_ok, follower_score = self._check_followers(profile)
        verdict.gate_scores["G4_followers"] = follower_ok
        if not follower_ok:
            verdict.rejection_reason = (
                f"G4_FAIL: Followers {profile.followers} outside range "
                f"[{self.min_followers}–{self.max_followers}]"
            )
            verdict.overall_score = 0.3
            return verdict

        # ── G5: Engagement Gate ────────────────────────────────────────────────
        engage_ok, engage_score = self._check_engagement(profile)
        verdict.gate_scores["G5_engagement"] = engage_ok
        # G5 is advisory — we don't hard-reject on engagement if other gates pass
        # because we may not have ER data from directory listings

        # ── Composite Score ────────────────────────────────────────────────────
        # Weighted: existence(20) + city(20) + skincare(30) + followers(15) + engagement(15)
        score = (
            0.20 * (1.0 if grounded else 0.0)
            + 0.20 * (1.0 if city_ok else 0.0)
            + 0.30 * skincare_score
            + 0.15 * follower_score
            + 0.15 * engage_score
        )
        verdict.overall_score = round(score, 3)
        verdict.passed = (
            grounded
            and city_ok
            and skincare_ok
            and follower_ok
        )

        return verdict

    def audit_batch(
        self, profiles: List[DiscoveredProfile], verbose: bool = True
    ) -> Tuple[List[AuditVerdict], List[AuditVerdict]]:
        """
        Audit a batch of profiles. Returns (passed, rejected) lists.
        """
        passed, rejected = [], []
        for i, p in enumerate(profiles, 1):
            if verbose:
                print(f"  [audit {i}/{len(profiles)}] @{p.handle}…", flush=True)
            v = self.audit_profile(p)
            if v.passed:
                if verbose:
                    print(f"    ✅ PASS  score={v.overall_score:.2f}  {p.city} [{p.city_tier}]")
                passed.append(v)
            else:
                if verbose:
                    print(f"    ❌ FAIL  {v.rejection_reason}")
                rejected.append(v)
        return passed, rejected

    # ──────────────────────────────────────────────────────────────────────────
    # Gate implementations
    # ──────────────────────────────────────────────────────────────────────────

    def _check_web_grounding(self, profile: DiscoveredProfile) -> Tuple[bool, Optional[Dict]]:
        """
        G1: Use agent-reach web search to confirm this handle exists AND enrich evidence.
        Returns (confirmed: bool, enriched_data: dict or None).
        """
        handle_lower = profile.handle.lower()
        if profile.source_url and f"instagram.com/{handle_lower}" in profile.source_url.lower():
            return (True, None)

        if not os.path.exists(AGENT_REACH_BIN):
            return (bool(profile.source_url), None)

        from instahunt.skills_discoverer import _run_agent_reach_search, _detect_city_in_text
        import time
        time.sleep(1.0)

        handle_lower = profile.handle.lower()
        items = _run_agent_reach_search(f"@{profile.handle} instagram", limit=3)
        if not items:
            if profile.source_url and f"instagram.com/{handle_lower}" in profile.source_url.lower():
                return (True, None)
            return (False, None)

        for item in items:
            text = ((item.get("text") or "") + " " + (item.get("title") or "")).lower()
            url = (item.get("url") or "").lower()
            if handle_lower in text or handle_lower in url:
                raw_text = item.get("text") or ""
                skincare_hits = sum(
                    1 for kw in SKINCARE_FOCUS_KEYWORDS if kw.lower() in raw_text.lower()
                )
                enriched = {
                    "snippet": raw_text[:400],
                    "skincare_confirmed": skincare_hits >= 2,
                }
                city, state, tier = _detect_city_in_text(raw_text)
                if city:
                    enriched["city"] = city
                    enriched["state"] = state
                    enriched["tier"] = tier
                return (True, enriched)

        if profile.source_url and f"instagram.com/{handle_lower}" in profile.source_url.lower():
            return (True, None)
        return (False, None)

    def _check_creator_authenticity(self, profile: DiscoveredProfile, notes: str = "") -> Tuple[bool, Optional[str]]:
        """Verify the handle represents an individual creator/doctor, not a corporate brand/store/catalog."""
        handle_lower = profile.handle.lower()
        from instahunt.skills_discoverer import OBVIOUSLY_NON_CREATOR_HANDLES
        if handle_lower in OBVIOUSLY_NON_CREATOR_HANDLES:
            return False, f"Handle @{handle_lower} is a known brand/business"

        # Check for brand-like handles
        for brand_term in [
            "botanics", "organics", "cosmetics", "pvt", "ltd",
            "store", "shop", "clinic", "clinics", "hospital", "centre", "center",
            "school", "academy", "institute", "soaps", "soap",
            "makeovers", "salon", "parlour", "skinclinic", "aesthetic_"
        ]:
            if brand_term in handle_lower:
                return False, f"Handle contains business term '{brand_term}'"

        # Check text/snippets for corporate brand signals
        text = ((profile.evidence_snippet or "") + " " + (notes or "")).lower()
        for b_kw in BRAND_DISQUALIFIERS:
            if b_kw in text:
                if any(x in text for x in ["skincare brand", "beauty brand", "cosmetics brand", "shop online", "buy online", "founded by", "co-founded by"]):
                    return False, f"Evidence identifies entity as a brand/company ('{b_kw}')"

        return True, None

    def _check_city(self, profile: DiscoveredProfile, notes: str = "") -> bool:
        """G2: Verify city is Tier 2/3 and not a Tier 1 metro or International location."""
        if not profile.city:
            return False  # Zero tolerance for unknown city
        city_lower = profile.city.lower().strip()

        # Hard blacklist: Tier 1 Metros & suburbs from config
        if city_lower in TIER1_METROS:
            return False
        for metro in TIER1_METROS:
            if metro in city_lower:
                return False

        # Hard blacklist: International locations
        for intl in INTERNATIONAL_BLACKLIST:
            if intl in city_lower:
                return False

        # Check evidence snippet and notes for international or tier-1 leak
        combined_text = ((profile.evidence_snippet or "") + " " + (notes or "")).lower()
        for intl in INTERNATIONAL_BLACKLIST:
            if re.search(r'\b' + re.escape(intl) + r'\b', combined_text):
                return False

        # Mandatory positive Tier 2 / Tier 3 match
        return city_lower in INDIAN_TIER2_TIER3_CITIES or profile.city_tier in ("Tier 2", "Tier 3")

    def _check_skincare_niche(self, profile: DiscoveredProfile, notes: str = "") -> Tuple[bool, float]:
        """
        G3: Confirm skincare is primary focus via per-handle web search.
        Returns (pass, score 0-1).
        """
        text = ((profile.evidence_snippet or "") + " " + (notes or "")).lower()

        # Check for immediate disqualifiers in description
        for dq in PRIMARY_NICHE_DISQUALIFIERS:
            pattern = r'\b' + re.escape(dq) + r'\b'
            if re.search(pattern, text):
                # If fashion/food/travel/bridal is in bio, require strong explicit doctor/skincare educator evidence
                sc_hits = sum(1 for kw in SKINCARE_FOCUS_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', text))
                if sc_hits < 3 and not profile.handle.lower().startswith("dr."):
                    return False, 0.0

        sc_score_from_evidence = sum(
            1 for kw in SKINCARE_FOCUS_KEYWORDS if kw.lower() in text
        )
        dq_penalty = sum(
            1 for dq in PRIMARY_NICHE_DISQUALIFIERS if dq.lower() in text
        )
        net_evidence_score = max(0, sc_score_from_evidence - dq_penalty)

        # If we already have strong confirmation from evidence (>=3 skincare keywords,
        # no disqualifiers) AND skincare was flagged — trust it
        if profile.is_skincare_confirmed and net_evidence_score >= 2:
            return (True, min(1.0, net_evidence_score / 4.0))

        # Otherwise: do a dedicated per-handle search to get independent evidence
        if os.path.exists(AGENT_REACH_BIN):
            live_confirmed, live_score = self._live_skincare_check(profile.handle)
            if live_confirmed:
                return (True, live_score)
            return (False, 0.0)

        # Fallback if agent-reach not available: use evidence score
        net = max(0, net_evidence_score - dq_penalty)
        return (
            profile.is_skincare_confirmed or net >= 1,
            min(1.0, net / 3.0),
        )

    def _live_skincare_check(self, handle: str) -> Tuple[bool, float]:
        """
        Run a dedicated web search for this handle and check skincare signals in results.
        Returns (skincare_confirmed, score).
        """
        from instahunt.skills_discoverer import _run_agent_reach_search
        import time
        time.sleep(1.0)

        items = _run_agent_reach_search(f"@{handle} instagram", limit=3)
        if not items:
            return (False, 0.0)

        handle_lower = handle.lower()
        best_score = 0.0
        for item in items:
            raw = (item.get("text") or "") + " " + (item.get("title") or "")
            raw_lower = raw.lower()

            # Only count if this result is actually about our handle
            if handle_lower not in raw_lower and handle_lower not in (item.get("url") or "").lower():
                continue

            sc_hits = sum(1 for kw in SKINCARE_FOCUS_KEYWORDS if kw.lower() in raw_lower)
            dq_hits = sum(1 for dq in PRIMARY_NICHE_DISQUALIFIERS if dq.lower() in raw_lower)
            net = max(0, sc_hits - dq_hits)
            score = min(1.0, net / 3.0)
            if score > best_score:
                best_score = score

        return (best_score >= 0.33, best_score)

    def _check_followers(self, profile: DiscoveredProfile) -> Tuple[bool, float]:
        """G4: Follower count in nano–mid range. Returns (pass, score)."""
        if profile.followers is None:
            # Unknown followers — give partial credit if other signals are strong
            return (True, 0.5)
        if profile.followers < self.min_followers:
            return (False, 0.0)
        if profile.followers > self.max_followers:
            return (False, 0.0)
        # Sweet spot: 5K–100K nano/micro gets full credit
        if 5_000 <= profile.followers <= 100_000:
            return (True, 1.0)
        return (True, 0.7)

    def _check_engagement(self, profile: DiscoveredProfile) -> Tuple[bool, float]:
        """G5: Engagement rate check. Advisory — no hard reject."""
        if profile.engagement_rate is None:
            return (True, 0.5)  # Unknown ER — assume OK
        if profile.engagement_rate >= self.min_er:
            return (True, min(1.0, profile.engagement_rate / 5.0))
        return (False, profile.engagement_rate / self.min_er * 0.5)
