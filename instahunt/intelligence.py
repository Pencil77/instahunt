"""
Unified Multi-Provider AI Intelligence Engine for InstaHunt.
Provides cascading AI reasoning across free-tier and fast LLM providers:
1. Groq (Fast Inference: openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b)
2. OpenRouter Free (nvidia/nemotron-3.5-lightning:free, openrouter/free)
3. NVIDIA NIM / NVIDIA Build (https://integrate.api.nvidia.com/v1)
4. Deterministic Rule-Based Fallback (100% offline-ready & mobile safe)
"""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from instahunt.config import (
    DISQUALIFYING_NICHE_KEYWORDS,
    INDIAN_TIER2_TIER3_CITIES,
    REGIONAL_SKINCARE_MARKERS,
    SKINCARE_KEYWORDS,
    TIER1_METROS,
)

logger = logging.getLogger(__name__)


@dataclass
class LocationAnalysis:
    detected_city: Optional[str]
    detected_state: Optional[str]
    city_tier: str  # "Tier 2", "Tier 3", "Tier 1", "Unknown"
    is_tier2_tier3: bool
    confidence: float
    evidence: str
    provider_used: str


@dataclass
class NicheAnalysis:
    is_skincare_creator: bool
    niche_score: float  # 0.0 to 1.0
    primary_focus: str
    vernacular_signals: List[str]
    summary: str
    provider_used: str


@dataclass
class CommunityAudit:
    community_grade: str  # "A", "B", "C", "F"
    authenticity_score: float  # 0.0 to 1.0
    spam_pod_ratio: float  # 0.0 to 1.0
    summary: str
    provider_used: str


@dataclass
class Pass2AuditorResult:
    """Gate 3 & Gate 4 Structured Output Schema (Argon Specification)."""
    username: str
    is_individual_creator: bool
    skincare_posts_out_of_10: int
    is_strictly_skincare_niche: bool
    detected_city: str
    detected_state: str
    city_tier: str  # "Tier 2" | "Tier 3" | "Tier 1" | "Unknown"
    city_evidence: str
    passes_all_criteria: bool
    rejection_reason: Optional[str] = None
    provider_used: str = "fallback"


class BaseLLMProvider:
    """Abstract interface for LLM provider implementations."""
    name: str = "base"

    def is_configured(self) -> bool:
        raise NotImplementedError

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.1,
        timeout: int = 15,
    ) -> Optional[str]:
        raise NotImplementedError

    def ping(self) -> Tuple[bool, float, str]:
        """Test provider connectivity and return (success, latency_ms, message)."""
        t0 = time.time()
        try:
            res = self.chat_completion(
                messages=[{"role": "user", "content": "Ping. Reply with PONG."}],
                max_tokens=250,
                temperature=0.0,
                timeout=12,
            )
            lat = round((time.time() - t0) * 1000, 1)
            if res:
                return True, lat, res.strip()
            return False, lat, "Empty response"
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 1)
            return False, lat, str(e)


class GroqProvider(BaseLLMProvider):
    """Groq Free-Tier API provider (blistering fast inference)."""
    name = "groq"
    DEFAULT_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
    ]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or self.DEFAULT_MODELS[0]
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.1,
        timeout: int = 15,
    ) -> Optional[str]:
        if not self.is_configured():
            return None

        models_to_try = [self.model] + [m for m in self.DEFAULT_MODELS if m != self.model]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            try:
                resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "")
                elif resp.status_code == 404:
                    # Model might be retired; try next candidate in list
                    continue
                else:
                    logger.warning("Groq API returned HTTP %s: %s", resp.status_code, resp.text[:120])
            except Exception as e:
                logger.warning("Groq request failed for %s: %s", model_name, e)
        return None


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter provider supporting Gemini and high-precision models."""
    name = "openrouter"
    DEFAULT_MODELS = [
        "google/gemini-3.8-flash",
        "google/gemini-3.7-flash",
        "google/gemini-4-argon",
        "nvidia/nemotron-3.5-lightning:free",
        "openrouter/free",
    ]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPEN_ROUTER_KEY")
        self.model = model or self.DEFAULT_MODELS[0]
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self._insufficient_credits = False

    def is_configured(self) -> bool:
        return bool(not self._insufficient_credits and self.api_key and len(self.api_key.strip()) > 5)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.1,
        timeout: int = 18,
    ) -> Optional[str]:
        if not self.is_configured():
            return None

        models_to_try = [self.model] + [m for m in self.DEFAULT_MODELS if m != self.model]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Pencil77/instahunt",
            "X-Title": "InstaHunt Creator Discovery",
        }

        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            try:
                resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "")
                elif resp.status_code == 402:
                    logger.info("OpenRouter returned 402 Insufficient credits; bypassing OpenRouter.")
                    self._insufficient_credits = True
                    break
                elif resp.status_code in (404, 429):
                    continue
                else:
                    logger.warning("OpenRouter returned HTTP %s: %s", resp.status_code, resp.text[:120])
            except Exception as e:
                logger.warning("OpenRouter request failed for %s: %s", model_name, e)
        return None


class NvidiaNIMProvider(BaseLLMProvider):
    """NVIDIA NIM / NVIDIA Build API provider."""
    name = "nvidia"
    DEFAULT_MODELS = [
        "meta/llama-3.2-11b-vision-instruct",
        "deepseek-ai/deepseek-v4.1-flash",
        "mistralai/mistral-large-2-instruct",
    ]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY")
        if not self.api_key:
            # Fallback check ~/.local/share/opencode/auth.json
            auth_path = Path.home() / ".local/share/opencode/auth.json"
            if auth_path.exists():
                try:
                    with open(auth_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.api_key = data.get("nvidia", {}).get("key")
                except Exception:
                    pass

        self.model = model or self.DEFAULT_MODELS[0]
        self.endpoint = "https://integrate.api.nvidia.com/v1/chat/completions"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.1,
        timeout: int = 6,
    ) -> Optional[str]:
        if not self.is_configured():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        for model_name in self.DEFAULT_MODELS:
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            try:
                resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=min(timeout, 5))
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "")
            except Exception as e:
                logger.warning("NVIDIA NIM request failed for %s: %s", model_name, e)
        return None


class AIIntelligenceEngine:
    """
    Unified Cascading Multi-Provider AI Intelligence Engine for InstaHunt.
    Automatically routes requests through active providers with fallback to rule-based heuristics.
    """

    def __init__(self, providers: Optional[List[BaseLLMProvider]] = None):
        self.providers = providers if providers is not None else [
            OpenRouterProvider(),
            GroqProvider(),
        ]

    def is_available(self) -> bool:
        """Check if at least one LLM provider is configured."""
        return any(p.is_configured() for p in self.providers)

    def get_active_providers(self) -> List[str]:
        """Return names of all configured providers."""
        return [p.name for p in self.providers if p.is_configured()]

    def health_check(self) -> Dict[str, Dict[str, Any]]:
        """Run connectivity ping against all configured providers."""
        results = {}
        for p in self.providers:
            if not p.is_configured():
                results[p.name] = {
                    "configured": False,
                    "status": "unconfigured",
                    "latency_ms": None,
                    "message": "Missing API Key",
                }
                continue

            ok, lat, msg = p.ping()
            results[p.name] = {
                "configured": True,
                "status": "healthy" if ok else "error",
                "latency_ms": lat,
                "message": msg,
            }
        return results

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.1,
    ) -> Tuple[Optional[str], str]:
        """
        Execute completion with cascading failover across configured providers.
        Returns (content, provider_name). If all fail, returns (None, 'fallback').
        """
        for p in self.providers:
            if not p.is_configured():
                continue
            try:
                content = p.chat_completion(messages, max_tokens=max_tokens, temperature=temperature)
                if content and len(content.strip()) > 0:
                    return content.strip(), p.name
            except Exception as e:
                logger.warning("Provider %s failed during chat completion: %s", p.name, e)
        return None, "fallback"

    def _extract_json_block(self, text: str) -> Optional[Dict]:
        """Extract and parse JSON object from markdown or raw response."""
        if not text:
            return None
        # Try direct parse
        try:
            return json.loads(text.strip())
        except Exception:
            pass

        # Try markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try finding outermost braces
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return None

    # --------------------------------------------------------------------------
    # 1. Location & Geography Disambiguation
    # --------------------------------------------------------------------------
    def disambiguate_location(
        self,
        username: str,
        bio: str,
        post_locations: Optional[List[str]] = None,
        recent_captions: Optional[List[str]] = None,
    ) -> LocationAnalysis:
        """
        Disambiguate creator home base:
        - Accurately identifies Indian Tier 2 & Tier 3 cities.
        - Explicitly identifies and rejects Tier 1 metros (Mumbai, Delhi, Bangalore, etc.).
        - Provides fallback rule-based matching if LLM is offline.
        """
        post_locations = post_locations or []
        recent_captions = recent_captions or []

        prompt = f"""You are an expert Indian geography and social media analyst for creator discovery.
Task: Determine the geographic location (city and state) of the Instagram creator @{username}.

Information provided:
- Bio: {bio or 'N/A'}
- Recent Post Geo-tags: {', '.join(post_locations) if post_locations else 'N/A'}
- Recent Post Captions (sample): {' | '.join(c[:150] for c in recent_captions[:3]) if recent_captions else 'N/A'}

Rules:
1. Identify if the creator is based in an Indian city.
2. If the city is one of the 8 Tier 1 Metros (Mumbai, Delhi, NCR, Bengaluru/Bangalore, Hyderabad, Chennai, Kolkata, Pune), classify city_tier as "Tier 1" and is_tier2_tier3 as false.
3. If the city is an Indian Tier 2 or Tier 3 city (e.g., Indore, Bhopal, Surat, Vadodara, Jaipur, Lucknow, Kanpur, Patna, Chandigarh, Ludhiana, Coimbatore, Kochi, Bhubaneswar, Nagpur, Dehradun, etc.), classify city_tier as "Tier 2" or "Tier 3" and is_tier2_tier3 as true.
4. If location is uncertain or outside India, set city_tier as "Unknown" and is_tier2_tier3 as false.
5. Return ONLY a valid JSON object with exactly these keys:
{{
  "detected_city": "City name or null",
  "detected_state": "State name or null",
  "city_tier": "Tier 1" | "Tier 2" | "Tier 3" | "Unknown",
  "is_tier2_tier3": true | false,
  "confidence": 0.0 to 1.0,
  "evidence": "Brief 1-sentence reasoning"
}}"""

        content, provider = self.chat_completion(
            messages=[
                {"role": "system", "content": "You are a precise JSON-only geographical classification engine."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.0,
        )

        parsed = self._extract_json_block(content) if content else None
        if parsed and "city_tier" in parsed:
            city = parsed.get("detected_city")
            tier = parsed.get("city_tier", "Unknown")
            is_t23 = parsed.get("is_tier2_tier3", tier in ("Tier 2", "Tier 3"))
            conf = float(parsed.get("confidence", 0.8))
            state = parsed.get("detected_state")
            evidence = parsed.get("evidence", f"AI identified {city} as {tier}")

            return LocationAnalysis(
                detected_city=city.title() if city else None,
                detected_state=state.title() if state else None,
                city_tier=tier,
                is_tier2_tier3=is_t23,
                confidence=conf,
                evidence=f"[{provider.upper()}] {evidence}",
                provider_used=provider,
            )

        # Fallback to local deterministic check
        return self._fallback_location_disambiguation(bio, post_locations, recent_captions)

    def _fallback_location_disambiguation(
        self, bio: str, locations: List[str], captions: List[str]
    ) -> LocationAnalysis:
        """Deterministic rule-based fallback when LLM is unavailable."""
        combined_text = f"{bio} {' '.join(locations)} {' '.join(captions)}".lower()

        # Check Tier 1 metros first (instant rejection)
        for metro in TIER1_METROS:
            if re.search(r"\b" + re.escape(metro) + r"\b", combined_text):
                return LocationAnalysis(
                    detected_city=metro.title(),
                    detected_state=None,
                    city_tier="Tier 1",
                    is_tier2_tier3=False,
                    confidence=0.90,
                    evidence=f"Deterministic rule detected Tier 1 metro '{metro.title()}'",
                    provider_used="rule-based",
                )

        # Check Tier 2 / Tier 3 cities
        for city, (tier, state, aliases) in INDIAN_TIER2_TIER3_CITIES.items():
            all_terms = [city] + aliases
            for term in all_terms:
                if re.search(r"\b" + re.escape(term) + r"\b", combined_text):
                    return LocationAnalysis(
                        detected_city=city.title(),
                        detected_state=state,
                        city_tier=tier,
                        is_tier2_tier3=True,
                        confidence=0.85,
                        evidence=f"Deterministic rule matched {tier} city '{city.title()}' ({state})",
                        provider_used="rule-based",
                    )

        return LocationAnalysis(
            detected_city=None,
            detected_state=None,
            city_tier="Unknown",
            is_tier2_tier3=False,
            confidence=0.0,
            evidence="No clear Indian city detected in profile bio or recent posts",
            provider_used="rule-based",
        )

    # --------------------------------------------------------------------------
    # 2. Skincare Niche & Vernacular Disambiguation (Strict Exclusivity + Pan-India)
    # --------------------------------------------------------------------------
    def assess_skincare_niche(
        self,
        username: str,
        bio: str,
        recent_captions: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
    ) -> NicheAnalysis:
        """
        Evaluate skincare niche concentration and vernacular/regional authenticity:
        - Strict Niche Exclusivity: Requires dedication to skincare (ingredients, barrier, reviews, acne).
          Rejects general fashion, lifestyle, bridal MUA, vlogging, and nutrition.
        - Pan-India Scope: Recognizes that creators across South (Tamil, Telugu, Malayalam, Kannada),
          West (Gujarati, Marathi), East (Bengali, Odia), and North post in English, Hinglish, or regional terms.
        """
        recent_captions = recent_captions or []
        hashtags = hashtags or []

        prompt = f"""You are a strict creator auditor evaluating whether an Instagram account is EXCLUSIVELY focused on skincare.
Creator: @{username}
Bio: {bio or 'N/A'}
Sample Captions: {' | '.join(c[:140] for c in recent_captions[:4]) if recent_captions else 'N/A'}
Hashtags: {', '.join(hashtags[:15]) if hashtags else 'N/A'}

CRITICAL CLIENT CRITERIA:
1. STRICT EXCLUSIVITY: The account MUST be exclusively dedicated to skincare (cosmetic chemistry, ingredients like niacinamide/retinol/ceramides, barrier repair, acne/hyperpigmentation routines, product reviews, sunscreens, or herbal/ayurvedic facial skincare).
2. DISQUALIFICATIONS: If this creator is primarily a general beauty creator, fashion/OOTD blogger, bridal makeup artist (MUA), daily/travel vlogger, lifestyle influencer, fitness coach, or nutritionist/dietitian with occasional skincare posts, set "is_skincare_creator" to FALSE.
3. PAN-INDIA REGIONAL SCOPE: Creators in Indian Tier 2 & Tier 3 cities across South (Tamil Nadu, Kerala, Karnataka, Andhra), West (Gujarat, Maharashtra), East (Bengal, Odisha), and North write primarily in English or regional bilingual formats. DO NOT penalize non-Hindi or English language creators.

Return ONLY a valid JSON object:
{{
  "is_skincare_creator": true | false,
  "niche_score": 0.0 to 1.0,
  "primary_focus": "e.g. Pure Skincare & Ingredients / General Fashion / Lifestyle Vlogger / Bridal MUA",
  "vernacular_signals": ["term1", "term2"],
  "summary": "1-sentence assessment explaining qualification or disqualification"
}}"""

        content, provider = self.chat_completion(
            messages=[
                {"role": "system", "content": "You are a strict, objective creator qualification auditor outputting JSON only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.0,
        )

        parsed = self._extract_json_block(content) if content else None
        if parsed and "is_skincare_creator" in parsed:
            return NicheAnalysis(
                is_skincare_creator=bool(parsed.get("is_skincare_creator")),
                niche_score=float(parsed.get("niche_score", 0.5)),
                primary_focus=str(parsed.get("primary_focus", "Skincare")),
                vernacular_signals=list(parsed.get("vernacular_signals", [])),
                summary=f"[{provider.upper()}] {parsed.get('summary', 'AI evaluated niche')}",
                provider_used=provider,
            )

        # Fallback heuristic
        return self._fallback_niche_assessment(bio, recent_captions)

    def _fallback_niche_assessment(self, bio: str, captions: List[str]) -> NicheAnalysis:
        text = f"{bio} {' '.join(captions)}".lower()

        # Check disqualifying niche keywords
        for dq in DISQUALIFYING_NICHE_KEYWORDS:
            if re.search(r"\b" + re.escape(dq) + r"\b", text):
                return NicheAnalysis(
                    is_skincare_creator=False,
                    niche_score=0.1,
                    primary_focus=f"Disqualified Niche ({dq})",
                    vernacular_signals=[],
                    summary=f"Disqualified: content focuses on '{dq}' rather than exclusive skincare",
                    provider_used="rule-based",
                )

        # Collect regional signals across South, West, East, North, and English
        found_signals = []
        for lang, markers in REGIONAL_SKINCARE_MARKERS.items():
            for m in markers:
                if re.search(r"\b" + re.escape(m) + r"\b", text):
                    found_signals.append(m)

        # Collect core skincare terms
        core_skincare_matches = [
            kw for kw in SKINCARE_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text)
        ]

        has_bio_skincare = any(
            re.search(r"\b" + re.escape(kw) + r"\b", bio.lower())
            for kw in SKINCARE_KEYWORDS
        )

        # Require pure skincare focus: either bio is dedicated to skincare OR at least 3 distinct active terms
        is_skincare = has_bio_skincare or len(core_skincare_matches) >= 3
        if is_skincare:
            raw_score = 0.50 + (0.15 if has_bio_skincare else 0.0) + (len(core_skincare_matches) * 0.08) + (len(found_signals) * 0.08)
            score = max(0.70, min(0.95, raw_score))
        else:
            score = 0.20

        return NicheAnalysis(
            is_skincare_creator=is_skincare,
            niche_score=round(score, 2) if is_skincare else 0.2,
            primary_focus="Dedicated Skincare" if is_skincare else "Non-Exclusive / General",
            vernacular_signals=found_signals[:5],
            summary=f"Rule-based matched {len(core_skincare_matches)} skincare terms (Bio dedicated: {has_bio_skincare})",
            provider_used="rule-based",
        )

    # --------------------------------------------------------------------------
    # 3. Community Quality & Engagement Pod Assessor
    # --------------------------------------------------------------------------
    def assess_community_quality(
        self,
        username: str,
        comments_sample: List[str],
        avg_comments: float,
    ) -> CommunityAudit:
        """
        Audit post comments for authentic user discussions vs bot/pod spam.
        """
        if not comments_sample:
            return CommunityAudit(
                community_grade="B",
                authenticity_score=0.5,
                spam_pod_ratio=0.3,
                summary="No comment texts available for deep audit; baseline applied",
                provider_used="baseline",
            )

        prompt = f"""Audit these sample comments from Instagram creator @{username} (Avg comments: {avg_comments:.1f}):
Comments:
{json.dumps(comments_sample[:25], ensure_ascii=False)}

Evaluate:
1. Do commenters ask genuine questions about products, ingredients, prices, routine steps, or skin suitability?
2. Or is it dominated by generic emoji strings (🔥❤️😍), follow pods, or self-promotion bots?
3. Output ONLY a valid JSON object:
{{
  "community_grade": "A" | "B" | "C" | "F",
  "authenticity_score": 0.0 to 1.0,
  "spam_pod_ratio": 0.0 to 1.0,
  "summary": "1-sentence description of audience engagement quality"
}}"""

        content, provider = self.chat_completion(
            messages=[
                {"role": "system", "content": "You are a fraud and engagement quality auditor outputting JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.0,
        )

        parsed = self._extract_json_block(content) if content else None
        if parsed and "community_grade" in parsed:
            return CommunityAudit(
                community_grade=str(parsed.get("community_grade", "B")),
                authenticity_score=float(parsed.get("authenticity_score", 0.5)),
                spam_pod_ratio=float(parsed.get("spam_pod_ratio", 0.2)),
                summary=f"[{provider.upper()}] {parsed.get('summary', 'AI community audit')}",
                provider_used=provider,
            )

        # Fallback to simple regex ratio
        from instahunt.enricher import CommentQualityAuditor
        auditor = CommentQualityAuditor()
        res = auditor.audit_sample_comments(comments_sample)
        spam_ratio = round(res.spam_signals_count / max(len(comments_sample), 1), 2)

        return CommunityAudit(
            community_grade=res.quality_grade,
            authenticity_score=res.authenticity_score,
            spam_pod_ratio=spam_ratio,
            summary=f"[RULE-BASED] {res.summary}",
            provider_used="rule-based",
        )

    # --------------------------------------------------------------------------
    # 4. Smart Dork Query Generator
    # --------------------------------------------------------------------------
    def generate_smart_dorks(
        self,
        cities: Optional[List[str]] = None,
        brands: Optional[List[str]] = None,
        max_queries: int = 15,
    ) -> List[Dict[str, str]]:
        """
        Generate contextual search dork queries combining Tier 2/3 cities with
        regional skincare trends and popular Indian D2C skincare brands.
        """
        target_cities = cities or ["Indore", "Surat", "Chandigarh", "Jaipur", "Lucknow", "Bhopal", "Coimbatore"]
        target_brands = brands or ["Minimalist", "Foxtale", "Dot & Key", "Dr Sheth", "Plum", "Mamaearth", "Derma Co"]

        dorks = []
        templates = [
            'site:instagram.com "{city}" ("skincare" OR "skin care")',
            'site:instagram.com "{city}" ("{brand}" OR "sunscreen" OR "serum")',
            'site:instagram.com "{city}" ("skincare blogger" OR "beauty creator")',
            'site:instagram.com "#{city_lower}blogger" ("skincare" OR "routine")',
        ]

        for city in target_cities:
            c_title = city.title()
            c_lower = city.lower().replace(" ", "")
            for tmpl in templates:
                for brand in target_brands[:2]:
                    q = tmpl.format(city=c_title, city_lower=c_lower, brand=brand)
                    dorks.append({
                        "query": q,
                        "city": c_title,
                        "brand_context": brand,
                    })
                    if len(dorks) >= max_queries:
                        return dorks
        return dorks

    # --------------------------------------------------------------------------
    # 4. Gate 3 & Gate 4: Comprehensive Creator Audit (Argon Specification)
    # --------------------------------------------------------------------------
    def audit_creator_pass2(self, profile_data: Dict) -> Pass2AuditorResult:
        """
        Gate 3 (Mandatory Positive Tier-2/3 City Verification) and
        Gate 4 (Strict 50% Skincare Content Ratio) Auditor.
        Implements the exact Argon Specification prompt and structured JSON schema.
        """
        username = str(profile_data.get("username", "") or "")
        full_name = str(profile_data.get("full_name", "") or "")
        category_name = str(profile_data.get("category_name", "") or "")
        bio = str(profile_data.get("biography", "") or "")
        posts = profile_data.get("timeline_posts", []) or []

        # Filter out pinned posts for post evaluation
        unpinned_posts = [p for p in posts if not p.get("is_pinned", False)] or posts
        recent_10 = unpinned_posts[:10]

        # Extract post geo-tags (last 12 posts)
        post_locations = [
            str(p.get("location_name", "") or "") for p in posts[:12] if p.get("location_name")
        ]
        post_locations_unique = list(dict.fromkeys(filter(None, post_locations)))

        # Format recent posts summary
        posts_summary_lines = []
        for i, p in enumerate(recent_10):
            cap = str(p.get("caption", "") or "").replace("\n", " ")[:140]
            cc = int(p.get("comments_count", 0) or 0)
            posts_summary_lines.append(f"Post {i+1} ({cc} comments): {cap}")
        recent_posts_summary = "\n".join(posts_summary_lines) if posts_summary_lines else "None provided"

        prompt = f"""You are a strict Manual Quality Assurance Auditor evaluating Instagram creator profiles for an Indian skincare brand campaign.

Your job is to reject any profile that looks automated, off-niche, engagement-inflated, or located in a Tier-1 metropolitan city.

INPUT DATA FOR @{username}:
- Full Name: {full_name or 'N/A'}
- Category: {category_name or 'N/A'}
- Bio: {bio or 'N/A'}
- Post Geo-Tags (Last 12 Posts): {json.dumps(post_locations_unique)}
- Last 10 Unpinned Post Captions & Comment Counts:
{recent_posts_summary}

EVALUATION RULES:
1. SKINCARE NICHE (STRICT): Count how many of the last 10 posts are explicitly about skincare (product reviews, routines, sunscreens, serums, acne care, skin barrier, facial care). General makeup, hair styling, OOTD/fashion, travel, or lifestyle vlogs DO NOT count as skincare. Must be >= 5 out of 10.
2. CREATOR AUTHENTICITY: Must be an individual creator/influencer or dermatologist/esthetician. Reject brand pages, meme/repost pages, salon business catalogs, or fake/bot accounts.
3. LOCATION VERIFICATION (CRITICAL):
   - Identify the creator's city from their Bio, Post Geo-Tags, local salon/cafe collaborations, or regional hashtags (e.g., #indoreblogger, #jaipurdiaries).
   - REJECT immediately if they live in or primarily post from Tier-1 cities/suburbs: Mumbai/MMR/Thane/Navi Mumbai, Delhi/NCR/Noida/Gurgaon/Faridabad/Ghaziabad, Bengaluru, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad, or outside India.
   - REJECT immediately if no specific city can be verified ("Unknown" or just "India").
   - APPROVE ONLY if positively verified in an Indian Tier-2 or Tier-3 city.

Respond ONLY with valid JSON matching this exact schema:
{{
  "username": "{username}",
  "is_individual_creator": true,
  "skincare_posts_out_of_10": 0,
  "is_strictly_skincare_niche": false,
  "detected_city": "Exact City Name or Unknown",
  "detected_state": "State Name or Unknown",
  "city_tier": "Tier 2 | Tier 3 | Tier 1 | Unknown",
  "city_evidence": "Exact quote from bio, geo-tag, or hashtag proving city",
  "passes_all_criteria": false,
  "rejection_reason": "Clear explanation if rejected, or null if approved"
}}"""

        content, provider = self.chat_completion(
            messages=[
                {"role": "system", "content": "You are a strict manual quality assurance auditor outputting JSON only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.0,
        )

        parsed = self._extract_json_block(content) if content else None
        if parsed and "is_individual_creator" in parsed:
            is_indiv = bool(parsed.get("is_individual_creator", True))
            skincare_ratio = int(parsed.get("skincare_posts_out_of_10", 0) or 0)
            is_niche = bool(parsed.get("is_strictly_skincare_niche", skincare_ratio >= 5))
            detected_city = str(parsed.get("detected_city", "Unknown") or "Unknown")
            detected_state = str(parsed.get("detected_state", "Unknown") or "Unknown")
            city_tier = str(parsed.get("city_tier", "Unknown") or "Unknown")
            city_evidence = str(parsed.get("city_evidence", "") or "")

            # 1. Tier 1 hard reject
            if city_tier == "Tier 1" or detected_city.lower() in TIER1_METROS:
                return Pass2AuditorResult(
                    username=username,
                    is_individual_creator=is_indiv,
                    skincare_posts_out_of_10=skincare_ratio,
                    is_strictly_skincare_niche=is_niche,
                    detected_city=detected_city,
                    detected_state=detected_state,
                    city_tier="Tier 1",
                    city_evidence=city_evidence,
                    passes_all_criteria=False,
                    rejection_reason=f"tier1_metro_{detected_city.lower()}",
                    provider_used=provider,
                )

            # 2. Unknown city hard reject (Zero Unknown Tolerance)
            if detected_city.lower() in ("unknown", "india", "none", "") or city_tier not in ("Tier 2", "Tier 3"):
                return Pass2AuditorResult(
                    username=username,
                    is_individual_creator=is_indiv,
                    skincare_posts_out_of_10=skincare_ratio,
                    is_strictly_skincare_niche=is_niche,
                    detected_city="Unknown",
                    detected_state=detected_state,
                    city_tier="Unknown",
                    city_evidence=city_evidence,
                    passes_all_criteria=False,
                    rejection_reason="unverified_city_zero_tolerance",
                    provider_used=provider,
                )

            # 3. 50% Skincare ratio rule
            if skincare_ratio < 5 or not is_niche:
                return Pass2AuditorResult(
                    username=username,
                    is_individual_creator=is_indiv,
                    skincare_posts_out_of_10=skincare_ratio,
                    is_strictly_skincare_niche=False,
                    detected_city=detected_city,
                    detected_state=detected_state,
                    city_tier=city_tier,
                    city_evidence=city_evidence,
                    passes_all_criteria=False,
                    rejection_reason=f"low_skincare_ratio_{skincare_ratio}_of_10",
                    provider_used=provider,
                )

            # 4. Individual creator rule
            if not is_indiv:
                return Pass2AuditorResult(
                    username=username,
                    is_individual_creator=False,
                    skincare_posts_out_of_10=skincare_ratio,
                    is_strictly_skincare_niche=is_niche,
                    detected_city=detected_city,
                    detected_state=detected_state,
                    city_tier=city_tier,
                    city_evidence=city_evidence,
                    passes_all_criteria=False,
                    rejection_reason="not_individual_creator",
                    provider_used=provider,
                )

            return Pass2AuditorResult(
                username=username,
                is_individual_creator=True,
                skincare_posts_out_of_10=skincare_ratio,
                is_strictly_skincare_niche=True,
                detected_city=detected_city,
                detected_state=detected_state,
                city_tier=city_tier,
                city_evidence=city_evidence,
                passes_all_criteria=True,
                rejection_reason=None,
                provider_used=provider,
            )

        # Fallback to local deterministic Pass-2 audit
        return self._fallback_pass2_audit(profile_data)

    def _fallback_pass2_audit(self, profile_data: Dict) -> Pass2AuditorResult:
        """Deterministic rule-based Pass 2 audit when LLM is unavailable."""
        username = str(profile_data.get("username", "") or "")
        full_name = str(profile_data.get("full_name", "") or "")
        bio = str(profile_data.get("biography", "") or "")
        posts = profile_data.get("timeline_posts", []) or []

        # 1. Creator authenticity check (word boundary matching to avoid matching 'clinical' for 'clinic')
        combined_text = f"{username} {full_name} {bio}".lower()
        business_markers = ["salon", "spa", "clinic", "academy", "shop", "store", "brand", "official", "memes"]
        business_pattern = re.compile(r"\b(" + "|".join(re.escape(b) for b in business_markers) + r")\b", re.IGNORECASE)
        is_individual = not bool(business_pattern.search(combined_text))

        # 2. Location verification (Gate 3)
        post_locations = [str(p.get("location_name", "") or "") for p in posts[:12] if p.get("location_name")]
        location_corpus = f"{bio} {' '.join(post_locations)}".lower()

        # Check Tier 1
        for metro in TIER1_METROS:
            if re.search(r"\b" + re.escape(metro) + r"\b", location_corpus):
                return Pass2AuditorResult(
                    username=username,
                    is_individual_creator=is_individual,
                    skincare_posts_out_of_10=0,
                    is_strictly_skincare_niche=False,
                    detected_city=metro.title(),
                    detected_state="N/A",
                    city_tier="Tier 1",
                    city_evidence=f"Matched Tier 1 blacklisted city '{metro}'",
                    passes_all_criteria=False,
                    rejection_reason=f"tier1_metro_{metro}",
                    provider_used="rule-based",
                )

        detected_city = None
        detected_state = None
        city_tier = "Unknown"
        city_evidence = ""

        for city, (tier, state, aliases) in INDIAN_TIER2_TIER3_CITIES.items():
            for term in [city] + aliases:
                match = re.search(r"\b" + re.escape(term) + r"\b", location_corpus)
                if match:
                    detected_city = city.title()
                    detected_state = state
                    city_tier = tier
                    city_evidence = f"Matched {tier} city '{city.title()}' in bio/geotags"
                    break
            if detected_city:
                break

        if not detected_city or city_tier not in ("Tier 2", "Tier 3"):
            return Pass2AuditorResult(
                username=username,
                is_individual_creator=is_individual,
                skincare_posts_out_of_10=0,
                is_strictly_skincare_niche=False,
                detected_city="Unknown",
                detected_state="Unknown",
                city_tier="Unknown",
                city_evidence="No positive Tier 2/3 city evidence found",
                passes_all_criteria=False,
                rejection_reason="unverified_city_zero_tolerance",
                provider_used="rule-based",
            )

        # 3. 50% Skincare Rule (Gate 4)
        unpinned = [p for p in posts if not p.get("is_pinned", False)] or posts
        recent_10 = unpinned[:10]

        skincare_count = 0
        skincare_re = re.compile(
            r"\b(" + "|".join(re.escape(k) for k in SKINCARE_KEYWORDS) + r")\b",
            re.IGNORECASE,
        )
        disqualify_re = re.compile(
            r"\b(" + "|".join(re.escape(k) for k in DISQUALIFYING_NICHE_KEYWORDS) + r")\b",
            re.IGNORECASE,
        )

        for p in recent_10:
            cap = str(p.get("caption", "") or "").lower()
            if skincare_re.search(cap) and not disqualify_re.search(cap):
                skincare_count += 1

        is_niche = (skincare_count >= 5)

        if not is_individual:
            return Pass2AuditorResult(
                username=username,
                is_individual_creator=False,
                skincare_posts_out_of_10=skincare_count,
                is_strictly_skincare_niche=is_niche,
                detected_city=detected_city,
                detected_state=detected_state,
                city_tier=city_tier,
                city_evidence=city_evidence,
                passes_all_criteria=False,
                rejection_reason="not_individual_creator",
                provider_used="rule-based",
            )

        if not is_niche:
            return Pass2AuditorResult(
                username=username,
                is_individual_creator=True,
                skincare_posts_out_of_10=skincare_count,
                is_strictly_skincare_niche=False,
                detected_city=detected_city,
                detected_state=detected_state,
                city_tier=city_tier,
                city_evidence=city_evidence,
                passes_all_criteria=False,
                rejection_reason=f"low_skincare_ratio_{skincare_count}_of_10",
                provider_used="rule-based",
            )

        return Pass2AuditorResult(
            username=username,
            is_individual_creator=True,
            skincare_posts_out_of_10=skincare_count,
            is_strictly_skincare_niche=True,
            detected_city=detected_city,
            detected_state=detected_state,
            city_tier=city_tier,
            city_evidence=city_evidence,
            passes_all_criteria=True,
            rejection_reason=None,
            provider_used="rule-based",
        )
