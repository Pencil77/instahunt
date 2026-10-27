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
                "biography": "Fashion & Lifestyle Vlogs in Bhopal",
                "followers_count": 15000,
                "posts_count": 80,
                "timeline_posts": [
                    {"comments_count": 22, "is_pinned": False, "caption": "Outfit of the day #fashion", "location_name": "Bhopal"},
                ],
                "suggested_profiles": [],
            },
            "mahigupta19923": {
                "full_name": "Mahi Gupta",
                "biography": "Daily vlogs, entertainment & fun reels Indore",
                "followers_count": 28000,
                "posts_count": 110,
                "timeline_posts": [
                    {"comments_count": 35, "is_pinned": False, "caption": "Daily vlog part 12", "location_name": "Indore"},
                ],
                "suggested_profiles": [],
            },
            "kanishka_dev_choudhary": {
                "full_name": "Kanishka Choudhary | Bridal MUA",
                "biography": "Bridal makeup artist & MUA Jaipur. Bookings open for bridal makeovers.",
                "followers_count": 65000,
                "posts_count": 280,
                "timeline_posts": [
                    {"comments_count": 140, "is_pinned": False, "caption": "Gorgeous bridal makeup look", "location_name": "Jaipur, Rajasthan"},
                ],
                "suggested_profiles": [],
            },
            "meenukutty_vlogs": {
                "full_name": "Meenukutty",
                "biography": "Daily family vlogs and lifestyle in Kochi 🌸",
                "followers_count": 42000,
                "posts_count": 190,
                "timeline_posts": [
                    {"comments_count": 85, "is_pinned": False, "caption": "A day in my life vlog", "location_name": "Kochi, Kerala"},
                ],
                "suggested_profiles": [],
            },
            "skinnbydeepanshu": {
                "full_name": "Deepanshu | Skincare",
                "biography": "Ludhiana | Dedicated Skincare & Chemical Sunscreen Enthusiast 🧴 Clear skin routines & honest reviews",
                "followers_count": 78000,
                "posts_count": 310,
                "timeline_posts": [
                    {"comments_count": 225, "is_pinned": False, "caption": "Best barrier repair moisturizers for cold winters in Ludhiana", "location_name": "Ludhiana, Punjab"},
                    {"comments_count": 195, "is_pinned": False, "caption": "Salicylic acid cleanser vs gel for stubborn blackheads", "location_name": "Model Town, Ludhiana"},
                ],
                "suggested_profiles": ["himanshi_freshfacebeauty"],
            },
            "freedom_chandel": {
                "full_name": "Dr. Freedom Chandel",
                "biography": "Dermatology educator & Skincare Consultant based in Lucknow, UP. Honest ingredient breakdowns.",
                "followers_count": 64000,
                "posts_count": 320,
                "timeline_posts": [
                    {"comments_count": 155, "is_pinned": False, "caption": "Ceramide barrier repair essentials for sensitive acne skin", "location_name": "Lucknow, Uttar Pradesh"},
                    {"comments_count": 142, "is_pinned": False, "caption": "Best chemical sunscreens for humid weather", "location_name": "Hazratganj, Lucknow"},
                    {"comments_count": 138, "is_pinned": False, "caption": "How to layer Niacinamide and Salicylic acid", "location_name": "Lucknow"},
                ],
                "suggested_profiles": ["kareenatekwani"],
            },
            "kareenatekwani": {
                "full_name": "Kareena Tekwani",
                "biography": "Jaipur based skincare educator ✨ Honest pharmacy skincare and acne solutions",
                "followers_count": 94000,
                "posts_count": 390,
                "timeline_posts": [
                    {"comments_count": 280, "is_pinned": False, "caption": "Best pharmacy skincare finds under ₹300 in Jaipur", "location_name": "Jaipur, Rajasthan"},
                    {"comments_count": 245, "is_pinned": False, "caption": "How I cleared cystic acne using simple routine", "location_name": "Malviya Nagar, Jaipur"},
                ],
                "suggested_profiles": ["glowwithaashi_"],
            },
            "glowwithaashi_": {
                "full_name": "Aashi | Skincare & Glow",
                "biography": "Indore, MP | Sharing my acne healing journey and honest skincare reviews 💖",
                "followers_count": 38000,
                "posts_count": 195,
                "timeline_posts": [
                    {"comments_count": 135, "is_pinned": False, "caption": "Morning skincare routine for oily acne prone skin in Indore weather", "location_name": "Indore, Madhya Pradesh"},
                    {"comments_count": 122, "is_pinned": False, "caption": "Foxtale ceramide moisturizer review after 30 days", "location_name": "Vijay Nagar, Indore"},
                ],
                "suggested_profiles": ["khyati.3am"],
            },
            "khyati.3am": {
                "full_name": "Khyati Sonigra",
                "biography": "Surat, Gujarat | Aesthetic skincare textures, serums & honest product empties 🧴",
                "followers_count": 39000,
                "posts_count": 175,
                "timeline_posts": [
                    {"comments_count": 148, "is_pinned": False, "caption": "Morning hydration routine for glass skin in Surat", "location_name": "Surat, Gujarat"},
                    {"comments_count": 132, "is_pinned": False, "caption": "K-beauty vs Indian D2C barrier creams", "location_name": "Vesu, Surat"},
                ],
                "suggested_profiles": ["dr_rutu_dermat_vadodara"],
            },
            "glow_withsandy": {
                "full_name": "Sandy | Glow with Sandy",
                "biography": "Coimbatore | Daily skincare routines, natural facial masks and dermat testing 🌿",
                "followers_count": 29000,
                "posts_count": 160,
                "timeline_posts": [
                    {"comments_count": 118, "is_pinned": False, "caption": "Hydrating toners and chemical sunscreen routine for Coimbatore weather", "location_name": "Coimbatore, Tamil Nadu"},
                    {"comments_count": 112, "is_pinned": False, "caption": "Ceramide creams for dry sensitive skin", "location_name": "Coimbatore"},
                ],
                "suggested_profiles": ["dr_anjali_skin_kochi"],
            },
            "dr_anjali_skin_kochi": {
                "full_name": "Dr. Anjali Nair | Kochi Dermat",
                "biography": "Kochi, Kerala | Aesthetic Dermatologist & Skincare Educator. Barrier repair & sun protection 🧴 #malayalamskincare",
                "followers_count": 82000,
                "posts_count": 290,
                "timeline_posts": [
                    {"comments_count": 195, "is_pinned": False, "caption": "Best sweat-resistant sunscreens for Kerala monsoon and humidity", "location_name": "Panampilly Nagar, Kochi"},
                    {"comments_count": 175, "is_pinned": False, "caption": "Treating fungal acne and post-inflammatory erythema", "location_name": "Kochi, Kerala"},
                ],
                "suggested_profiles": ["sneha_skincare_vizag"],
            },
            "sneha_skincare_vizag": {
                "full_name": "Sneha | Vizag Skincare Guide",
                "biography": "Visakhapatnam, AP | Dedicated skincare creator. Fading acne marks, pharmacy serums & honest reviews 🌸 #teluguskincare",
                "followers_count": 45000,
                "posts_count": 220,
                "timeline_posts": [
                    {"comments_count": 172, "is_pinned": False, "caption": "How to fade dark spots with Azelaic acid and Niacinamide in Vizag", "location_name": "Visakhapatnam, Andhra Pradesh"},
                    {"comments_count": 158, "is_pinned": False, "caption": "Affordable hydrating barrier serums under ₹500", "location_name": "Siripuram, Vizag"},
                ],
                "suggested_profiles": ["mysore_skin_lab"],
            },
            "mysore_skin_lab": {
                "full_name": "Pooja Hegde | Mysore Skin Lab",
                "biography": "Mysore, Karnataka | Science-backed skincare tips, ingredient analysis & sunscreen tests 🧴 #kannadaskincare",
                "followers_count": 52000,
                "posts_count": 260,
                "timeline_posts": [
                    {"comments_count": 148, "is_pinned": False, "caption": "Understanding comedogenic ingredients for acne-prone skin", "location_name": "Mysuru, Karnataka"},
                    {"comments_count": 136, "is_pinned": False, "caption": "My night routine for repairing compromised skin barrier", "location_name": "Gokulam, Mysore"},
                ],
                "suggested_profiles": ["tanvi_skin_nagpur"],
            },
            "tanvi_skin_nagpur": {
                "full_name": "Tanvi Joshi | Skincare",
                "biography": "Nagpur, Maharashtra | Daily skincare routines, barrier repair & acne guides 🌿 #marathiskincare",
                "followers_count": 61000,
                "posts_count": 240,
                "timeline_posts": [
                    {"comments_count": 168, "is_pinned": False, "caption": "Summer sunscreens tested in 42°C Nagpur heat - zero white cast", "location_name": "Nagpur, Maharashtra"},
                    {"comments_count": 152, "is_pinned": False, "caption": "Gentle salicylic acid face washes for oily skin", "location_name": "Dharampeth, Nagpur"},
                ],
                "suggested_profiles": ["dr_rutu_dermat_vadodara"],
            },
            "dr_rutu_dermat_vadodara": {
                "full_name": "Dr. Rutu Patel | Dermat",
                "biography": "Vadodara, Gujarat | Dermatology educator. Clinical skincare, retinoid guides & acne solutions 🧴 #gujaratskincare",
                "followers_count": 92000,
                "posts_count": 340,
                "timeline_posts": [
                    {"comments_count": 210, "is_pinned": False, "caption": "How to introduce Retinol without purging or peeling", "location_name": "Alkapuri, Vadodara"},
                    {"comments_count": 185, "is_pinned": False, "caption": "Best pharmacy sunscreens tested under UV camera", "location_name": "Vadodara, Gujarat"},
                ],
                "suggested_profiles": ["bhubaneswar_skincare_diaries"],
            },
            "bhubaneswar_skincare_diaries": {
                "full_name": "Itishree | Skincare",
                "biography": "Bhubaneswar, Odisha | East India skincare reviewer. Sunscreen guides, toners & barrier healing 🌸",
                "followers_count": 38000,
                "posts_count": 180,
                "timeline_posts": [
                    {"comments_count": 146, "is_pinned": False, "caption": "Budget skincare routine for coastal Odisha humidity", "location_name": "Bhubaneswar, Odisha"},
                    {"comments_count": 134, "is_pinned": False, "caption": "Soothing cica and centella serums for redness and rosacea", "location_name": "Saheed Nagar, Bhubaneswar"},
                ],
                "suggested_profiles": ["siliguri_skin_review"],
            },
            "siliguri_skin_review": {
                "full_name": "Rhea Sen | Skin Reviews",
                "biography": "Siliguri, West Bengal | Honest skincare reviews, barrier creams & salicylic acid routines 🧴",
                "followers_count": 31000,
                "posts_count": 150,
                "timeline_posts": [
                    {"comments_count": 130, "is_pinned": False, "caption": "Winter barrier repair routine for cold North Bengal weather", "location_name": "Siliguri, West Bengal"},
                    {"comments_count": 118, "is_pinned": False, "caption": "Top 3 non-comedogenic moisturizers under ₹400", "location_name": "Siliguri"},
                ],
                "suggested_profiles": ["udaipur_dermat_care"],
            },
            "udaipur_dermat_care": {
                "full_name": "Dr. Meera Sharma",
                "biography": "Udaipur, Rajasthan | Dermatology routines, hyperpigmentation solutions & pharmacy skincare 🧴",
                "followers_count": 67000,
                "posts_count": 270,
                "timeline_posts": [
                    {"comments_count": 160, "is_pinned": False, "caption": "Dermatologist guide to fading stubborn melasma and sun spots", "location_name": "Udaipur, Rajasthan"},
                    {"comments_count": 144, "is_pinned": False, "caption": "Ceramide creams vs Hyaluronic acid for dry desert skin", "location_name": "Fateh Sagar, Udaipur"},
                ],
                "suggested_profiles": ["himanshi_freshfacebeauty"],
            },
            "himanshi_freshfacebeauty": {
                "full_name": "Himanshi",
                "biography": "Skincare hacks, acne recovery & product reviews. Chandigarh based 🌿",
                "followers_count": 51000,
                "posts_count": 240,
                "timeline_posts": [
                    {"comments_count": 145, "is_pinned": False, "caption": "Daily skin routine to fade dark spots #chandigarh", "location_name": "Chandigarh"},
                    {"comments_count": 130, "is_pinned": False, "caption": "Hyaluronic acid serum common mistakes", "location_name": "Sector 35, Chandigarh"},
                ],
                "suggested_profiles": [],
            },
            "bolt_officiall": {
                "full_name": "Dhamotharan | Mens Grooming & Style",
                "biography": "Coimbatore, Tamil Nadu | Mens grooming, haircuts & beard styling",
                "followers_count": 240000,
                "posts_count": 450,
                "timeline_posts": [
                    {"comments_count": 290, "is_pinned": False, "caption": "Best beard styling and haircut trends", "location_name": "Coimbatore, Tamil Nadu"},
                ],
                "suggested_profiles": [],
            },
            "harshitakasera": {
                "full_name": "Harshita Kasera",
                "biography": "Jaipur | Luxury Beauty, Fashion & Lifestyle Creator ✨",
                "followers_count": 87000,
                "posts_count": 360,
                "timeline_posts": [
                    {"comments_count": 180, "is_pinned": False, "caption": "Luxury fashion haul and styling in Jaipur", "location_name": "Jaipur, Rajasthan"},
                ],
                "suggested_profiles": [],
            },
            "sarahgaur": {
                "full_name": "Sarah Gaur",
                "biography": "Clinical Nutrition & Dietitian. Based in Chandigarh 🌸 Meal plans and weight loss.",
                "followers_count": 58000,
                "posts_count": 270,
                "timeline_posts": [
                    {"comments_count": 152, "is_pinned": False, "caption": "Diet plans for weight loss and PCOS", "location_name": "Chandigarh"},
                ],
                "suggested_profiles": [],
            },
            "private_test_creator": {
                "full_name": "Private Personal User",
                "biography": "Personal account. Skincare enthusiast in Jaipur.",
                "followers_count": 450,
                "posts_count": 20,
                "is_private": True,
                "timeline_posts": [],
                "suggested_profiles": [],
            },
        }

        if username in fixtures:
            data = fixtures[username]
            data["username"] = username
            data.setdefault("is_business_account", True)
            data.setdefault("category_name", "Creator")
            data.setdefault("is_private", False)
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
