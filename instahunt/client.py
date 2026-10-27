"""
Instagram Web API Client and Session Manager for InstaHunt.
Handles authentication, cookie injection, network requests to web_profile_info,
rate-limiting, jitter, and response normalization.
"""

import json
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests

from instahunt.config import (
    BASE_DIR,
    MAX_JITTER_SECONDS,
    MIN_JITTER_SECONDS,
)


class RateLimitException(Exception):
    """Raised when Instagram responds with HTTP 429 Too Many Requests."""
    pass


class InstagramClient:
    WEB_PROFILE_ENDPOINT = "https://www.instagram.com/api/v1/users/web_profile_info/"
    IG_APP_ID = "936619743392459"
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        session_id: Optional[str] = None,
        cookie_file: Optional[Path] = None,
        use_jitter: bool = True,
        simulation_mode: bool = False,
    ):
        self.session_id = session_id or os.getenv("INSTAGRAM_SESSION_ID")
        self.cookie_file = cookie_file or (BASE_DIR / "cookies.json")
        self.use_jitter = use_jitter
        self.simulation_mode = simulation_mode

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.DEFAULT_UA,
            "x-ig-app-id": self.IG_APP_ID,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        })

        self._load_cookies()

    def _load_cookies(self):
        """Load sessionid from cookie file if present."""
        if self.cookie_file and Path(self.cookie_file).exists():
            try:
                with open(self.cookie_file, "r") as f:
                    cookies = json.load(f)
                    if isinstance(cookies, dict):
                        for k, v in cookies.items():
                            self.session.cookies.set(k, v, domain=".instagram.com")
                    elif isinstance(cookies, list):
                        for c in cookies:
                            self.session.cookies.set(c.get("name"), c.get("value"), domain=c.get("domain", ".instagram.com"))
            except Exception:
                pass

        if self.session_id:
            self.session.cookies.set("sessionid", self.session_id, domain=".instagram.com")

    def save_session_cookie(self, session_id: str, ds_user_id: Optional[str] = None):
        """Persist session credentials for future runs."""
        self.session_id = session_id
        self.session.cookies.set("sessionid", session_id, domain=".instagram.com")
        if ds_user_id:
            self.session.cookies.set("ds_user_id", ds_user_id, domain=".instagram.com")

        cookie_data = {"sessionid": session_id}
        if ds_user_id:
            cookie_data["ds_user_id"] = ds_user_id

        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_file, "w") as f:
            json.dump(cookie_data, f, indent=2)

    def apply_jitter(self):
        """Apply human-like pacing delay between requests."""
        if self.use_jitter and not self.simulation_mode:
            delay = random.uniform(MIN_JITTER_SECONDS, MAX_JITTER_SECONDS)
            time.sleep(delay)

    def fetch_profile(self, username: str) -> Dict:
        """
        Fetch profile data and recent timeline posts via web_profile_info.
        Returns standardized profile dictionary.
        """
        clean_u = username.strip().lower().replace("@", "")

        if self.simulation_mode:
            return self._simulate_profile(clean_u)

        self.apply_jitter()

        url = f"{self.WEB_PROFILE_ENDPOINT}?username={clean_u}"
        headers = {
            "Referer": f"https://www.instagram.com/{clean_u}/",
        }

        resp = self.session.get(url, headers=headers, timeout=15)

        if resp.status_code == 429:
            raise RateLimitException("Instagram HTTP 429: Too Many Requests / IP throttled.")
        elif resp.status_code == 404:
            raise ValueError(f"Profile @{clean_u} not found (404).")
        elif resp.status_code != 200:
            raise RuntimeError(f"Instagram API returned HTTP {resp.status_code}: {resp.text[:150]}")

        data = resp.json()
        return self._parse_api_response(data, clean_u)

    def _parse_api_response(self, data: Dict, username: str) -> Dict:
        """Normalize Instagram JSON into structured model."""
        user = data.get("data", {}).get("user", {}) or {}

        # Parse posts
        edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
        timeline_posts = []

        for e in edges:
            node = e.get("node", {})
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""
            
            loc = node.get("location") or {}
            location_name = loc.get("name", "") if loc else ""

            timeline_posts.append({
                "id": node.get("id"),
                "comments_count": node.get("edge_media_to_comment", {}).get("count", 0),
                "likes_count": node.get("edge_liked_by", {}).get("count", 0),
                "is_pinned": bool(node.get("is_pinned", False)),
                "is_video": bool(node.get("is_video", False)),
                "caption": caption,
                "location_name": location_name,
                "taken_at_timestamp": node.get("taken_at_timestamp"),
            })

        # Parse suggested / edge chaining profiles
        chaining_edges = user.get("edge_chaining", {}).get("edges", [])
        suggested_profiles = [
            e.get("node", {}).get("username")
            for e in chaining_edges
            if e.get("node", {}).get("username")
        ]

        return {
            "username": username,
            "full_name": user.get("full_name", ""),
            "biography": user.get("biography", ""),
            "followers_count": user.get("edge_followed_by", {}).get("count", 0),
            "posts_count": user.get("edge_owner_to_timeline_media", {}).get("count", 0),
            "timeline_posts": timeline_posts,
            "suggested_profiles": suggested_profiles,
            "is_business_account": user.get("is_business_account", False),
            "category_name": user.get("category_name", ""),
            "external_url": user.get("external_url", ""),
        }

    def _simulate_profile(self, username: str) -> Dict:
        """Simulation fixtures for testing without network/rate-limits."""
        # Built-in test cases reflecting real client requirements
        fixtures = {
            "sonali.rao22": {
                "full_name": "Sonali Rao | Skincare & Glow",
                "biography": "Skincare educator based in Jaipur 🌸 Honest acne & serum reviews",
                "followers_count": 48500,
                "posts_count": 210,
                "timeline_posts": [
                    {"comments_count": 142, "is_pinned": False, "caption": "My morning skincare routine for glowing skin! #jaipurblogger", "location_name": "Jaipur, Rajasthan"},
                    {"comments_count": 128, "is_pinned": False, "caption": "Best sunscreen picks under 500", "location_name": "C Scheme, Jaipur"},
                    {"comments_count": 115, "is_pinned": False, "caption": "Niacinamide vs Salicylic acid for acne", "location_name": ""},
                    {"comments_count": 134, "is_pinned": False, "caption": "Skin barrier repair tips", "location_name": "Jaipur"},
                ],
                "suggested_profiles": ["glowwithkasturi", "skinnbydeepanshu", "jaipur_glow_diary"],
            },
            "rekhasinghlife": {
                "full_name": "Rekha Singh",
                "biography": "Ayurvedic skincare & homemade face packs 🌿 Indore, MP",
                "followers_count": 320000,
                "posts_count": 650,
                "timeline_posts": [
                    {"comments_count": 450, "is_pinned": False, "caption": "DIY glowing skin remedy", "location_name": "Indore, Madhya Pradesh"},
                    {"comments_count": 380, "is_pinned": False, "caption": "Dark circle removal pack", "location_name": "Chappan Dukan, Indore"},
                    {"comments_count": 290, "is_pinned": False, "caption": "Natural hair & skincare tips", "location_name": ""},
                ],
                "suggested_profiles": ["indore_beauty_hub", "kavyabeautyandfashion"],
            },
            "kavyabeautyandfashion": {
                "full_name": "Kavya Beauty",
                "biography": "Skincare routine & beauty tips 💖 Lucknow | Daily Reels",
                "followers_count": 89000,
                "posts_count": 340,
                "timeline_posts": [
                    {"comments_count": 185, "is_pinned": False, "caption": "Glass skin routine step by step", "location_name": "Lucknow, Uttar Pradesh"},
                    {"comments_count": 160, "is_pinned": False, "caption": "Monsoon skincare guide", "location_name": "Hazratganj, Lucknow"},
                ],
                "suggested_profiles": ["lucknow_glow", "rekhasinghlife"],
            },
            "mumbai_skincare_star": {
                "full_name": "Aanya Sharma",
                "biography": "Dermatology resident in Mumbai. Skincare recommendations.",
                "followers_count": 120000,
                "posts_count": 400,
                "timeline_posts": [
                    {"comments_count": 250, "is_pinned": False, "caption": "Retinol dos and donts", "location_name": "Bandra, Mumbai"},
                ],
                "suggested_profiles": [],
            },
            "shraboni_454": {
                "full_name": "Shraboni",
                "biography": "Fashion & Lifestyle Vlogs",
                "followers_count": 15000,
                "posts_count": 80,
                "timeline_posts": [
                    {"comments_count": 22, "is_pinned": False, "caption": "Outfit of the day", "location_name": "Bhopal"},
                ],
                "suggested_profiles": [],
            },
        }

        if username in fixtures:
            data = fixtures[username]
            data["username"] = username
            data.setdefault("is_business_account", True)
            data.setdefault("category_name", "Creator")
            return data

        # Default generated fixture
        return {
            "username": username,
            "full_name": username.title(),
            "biography": f"Creator page for @{username}. Lifestyle & beauty tips.",
            "followers_count": 10000,
            "posts_count": 50,
            "timeline_posts": [
                {"comments_count": 45, "is_pinned": False, "caption": "New post!", "location_name": ""},
            ],
            "suggested_profiles": [],
            "is_business_account": False,
            "category_name": "Personal Blog",
        }
