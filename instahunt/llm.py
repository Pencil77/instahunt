"""
Free-Tier LLM Classification Module for InstaHunt.
Supports Groq, OpenRouter, and Gemini Free tiers with structured JSON outputs.
"""

import json
import os
from typing import Dict, List, Optional
import requests


class LLMClassifier:
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "auto",  # "groq", "openrouter", "auto"
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("OPEN_ROUTER_KEY")
        self.provider = provider
        
        if self.provider == "auto":
            if os.getenv("GROQ_API_KEY"):
                self.provider = "groq"
            elif os.getenv("OPEN_ROUTER_KEY"):
                self.provider = "openrouter"
            else:
                self.provider = "none"

    def is_available(self) -> bool:
        return bool(self.api_key and self.provider != "none")

    def classify_profile(
        self,
        username: str,
        bio: str,
        post_locations: List[str],
        recent_captions: List[str],
    ) -> Optional[Dict]:
        """Classify ambiguous profile location and skincare niche."""
        if not self.is_available():
            return None

        prompt = f"""
You are an expert social media research auditor classifying Indian Instagram creators for a brand campaign.
Criteria:
1. Niche: Must be a skincare creator (posts routines, product reviews, acne/glow tips).
2. Location: Must be based in an Indian Tier 2 or Tier 3 city. Creators from Tier 1 metros (Mumbai, Delhi/NCR, Bengaluru, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad) are STRICTLY DISQUALIFIED.

Candidate:
Username: {username}
Bio: {bio}
Post Locations: {', '.join(post_locations[:6])}
Recent Captions: {' | '.join(recent_captions[:3])}

Output STRICT JSON only:
{{
  "is_skincare_creator": true/false,
  "detected_city": "City Name or null",
  "detected_state": "State Name or null",
  "city_tier": "Tier 2" or "Tier 3" or "Tier 1" or "Unknown",
  "evidence": "Short 1-sentence justification"
}}
"""
        try:
            if self.provider == "groq":
                return self._call_groq(prompt)
            elif self.provider == "openrouter":
                return self._call_openrouter(prompt)
        except Exception:
            return None
        return None

    def _call_groq(self, prompt: str) -> Optional[Dict]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        return None

    def _call_openrouter(self, prompt: str) -> Optional[Dict]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "meta-llama/llama-3.2-3b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # Clean markdown if returned
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        return None
