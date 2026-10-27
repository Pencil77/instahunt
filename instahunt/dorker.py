"""
Search Engine Dorking Module for InstaHunt.
Discovers new Tier 2 & Tier 3 Indian skincare creators via external search queries,
bypassing Instagram rate limits and account risk during discovery.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set
import requests

from instahunt.config import INDIAN_TIER2_TIER3_CITIES

IGNORED_PATHS = {
    "p", "reel", "reels", "explore", "stories", "accounts", "about",
    "developer", "legal", "terms", "directory", "web", "graphql",
}


class SearchDorker:
    def __init__(self, user_agent: Optional[str] = None, ai_engine: Optional[Any] = None):
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.ai_engine = ai_engine

    def generate_dork_queries(
        self,
        target_cities: Optional[List[str]] = None,
        max_queries: int = 20,
        use_ai: bool = False,
    ) -> List[Dict]:
        """Generate targeted dork queries for Tier 2 and Tier 3 cities."""
        if use_ai and self.ai_engine and hasattr(self.ai_engine, "generate_smart_dorks"):
            return self.ai_engine.generate_smart_dorks(cities=target_cities, max_queries=max_queries)

        queries = []
        cities = target_cities or list(INDIAN_TIER2_TIER3_CITIES.keys())

        templates = [
            'site:instagram.com "skincare" "{city}"',
            'site:instagram.com ("skincare routine" OR "skin care") "{city}"',
            'site:instagram.com ("skincare blogger" OR "skincare creator") "{city}"',
        ]

        for city in cities:
            canonical = city.title()
            for tmpl in templates:
                q = tmpl.format(city=canonical)
                queries.append({"query": q, "city": canonical})
                if len(queries) >= max_queries:
                    return queries
        return queries

    def extract_handles_from_text(self, text: str) -> List[str]:
        """Extract valid Instagram profile handles from HTML or snippet text."""
        # Matches instagram.com/{username}
        matches = re.findall(r"instagram\.com/([a-zA-Z0-9_\.]+)/?", text, re.IGNORECASE)
        handles = set()
        
        for h in matches:
            clean = h.strip().lower()
            if clean in IGNORED_PATHS or len(clean) < 3 or clean.startswith("_next") or "." in clean.split("/")[0]:
                continue
            # Extract just handle before any query params or subpath
            pure_handle = clean.split("?")[0].split("/")[0]
            if pure_handle not in IGNORED_PATHS and len(pure_handle) >= 3:
                handles.add(pure_handle)

        return sorted(list(handles))

    def dork_bing(self, query: str) -> List[str]:
        """Execute query against Bing search HTML."""
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return self.extract_handles_from_text(resp.text)
        except Exception:
            pass
        return []

    def dork_duckduckgo_lite(self, query: str) -> List[str]:
        """Execute query against DuckDuckGo Lite endpoint."""
        url = "https://lite.duckduckgo.com/lite/"
        try:
            resp = self.session.post(url, data={"q": query}, timeout=10)
            if resp.status_code == 200:
                return self.extract_handles_from_text(resp.text)
        except Exception:
            pass
        return []

    def search_city(self, city: str) -> List[str]:
        """Run search dorks for a specific city and return discovered handles."""
        canonical = city.title()
        discovered: Set[str] = set()

        q1 = f'site:instagram.com "skincare" "{canonical}"'
        q2 = f'site:instagram.com "skincare blogger" "{canonical}"'

        for q in [q1, q2]:
            h1 = self.dork_bing(q)
            discovered.update(h1)
            h2 = self.dork_duckduckgo_lite(q)
            discovered.update(h2)

        return sorted(list(discovered))
