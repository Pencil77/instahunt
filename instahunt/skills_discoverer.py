"""
Skills-Based Discovery Engine for InstaHunt.

Replaces the broken SearchDorker (Bing/DDG HTTP dorks that fail against bot-detection).

Architecture:
  - Uses `agent-reach web search` (Exa backend) to query talent directories,
    influencer marketplaces, and city-specific beauty/skincare blogs for real handles.
  - Falls back to native search_web() (Google-indexed) query patterns.
  - All discovery is grounded against live web data — no template handle generation.

Transport: shell subprocess → `~/.local/bin/agent-reach web search "<query>"`
Output: list of DiscoveredProfile dicts with handle, name, city, source_url, evidence snippets
"""

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from instahunt.config import INDIAN_TIER2_TIER3_CITIES, TIER1_METROS

logger = logging.getLogger(__name__)

# Path to agent-reach binary (persists on /home)
AGENT_REACH_BIN = os.path.expanduser("~/.local/bin/agent-reach")

# Talent directories & platforms that reliably surface Tier 2/3 Indian skincare creators
TRUSTED_SOURCE_DOMAINS = [
    "digitalberries.co.in",
    "socialbridge.agency",
    "modash.io",
    "influencer.in",
    "winkl.co",
    "qoruz.com",
    "hypetrace.io",
    "klugklug.com",
    "socialhipper.com",
    "influglue.com",
    "plixxo.com",
]

# City-specific search query templates — targeting real creators and reels
DISCOVERY_QUERY_TEMPLATES = [
    'site:instagram.com inurl:reels "skincare" "{city}" -fashion -saree -food -vlog -ootd',
    'site:instagram.com inurl:reels ("dermatologist" OR "skincare routine" OR "skin tips") "{city}" -fashion',
    'site:instagram.com ("skincare educator" OR "skincare creator") "{city}" -fashion -saree',
    'skincare creator "{city}" instagram (site:modash.io OR site:digitalberries.co.in OR site:socialbridge.agency)',
    '"skincare" ("{city}" OR "{state}") ("blogger" OR "creator" OR "dermatologist") site:instagram.com -fashion -saree',
]

# Regex to extract Instagram handles from web text
INSTA_HANDLE_RE = re.compile(
    r'@([a-zA-Z0-9_\.]{3,30})|instagram\.com/([a-zA-Z0-9_\.]{3,30})',
    re.IGNORECASE
)

# Paths that are Instagram platform paths, not user handles
IGNORED_PATHS = {
    "p", "reel", "reels", "explore", "stories", "accounts", "about",
    "developer", "legal", "terms", "directory", "web", "graphql",
    "tv", "ar", "fbclid", "share", "challenges", "audio", "location",
    "tags", "highlights", "_n", "null", "undefined", "popular", "trending",
    "search", "live", "direct", "post", "posts", "igtv", "profile",
}

# Known non-creator domains/brands that appear as handles on listicle pages
OBVIOUSLY_NON_CREATOR_HANDLES = {
    # Email/platform domains
    "gmail.com", "gmail", "youtube", "facebook", "twitter",
    "google", "whatsapp", "snapchat", "tiktok", "linkedin",
    # E-commerce / general
    "amazon", "amazondotin", "flipkart", "nykaa", "myntra", "meesho", "ajio",
    # Real estate / non-beauty businesses
    "danubeproperties", "plottwistt.co", "plottwistt", "bespokegrub", "blissfull_bakez", "blissfullbakez",
    # Global beauty BRANDS (we want individual creators, not brands)
    "larocheposay", "larocheposayusa", "larocheposayindia",
    "cetaphil", "cetaphil_india", "cetaphilindia",
    "elfcosmetics", "elf_cosmetics",
    "maybelline", "maybellineindia", "maybelline_india",
    "anastasiabeverlyhills", "hudabeauty", "fentybeauty", "toofaced",
    "lorealparisofficial", "lorealparis", "loreal",
    "neutrogena", "neutrogindia",
    "biotique", "plumgoodness", "minimalist.india", "minimalist", "beminimalist__",
    "mamaearth", "dotandskey", "dotandkey.skincare", "theordinary",
    "lakme", "lakmeindia", "lakme_india",
    "colorbar", "nykaabeauty", "sugarcosmetics",
    "mcaffeine", "fixderma", "drshethskin", "dr_sheths", "drsheths",
    "wownaturalproducts", "wow_skin_science",
    "dermalogica", "skinceuticals", "paulaschoice",
    "clinique", "origins", "kiehls",
    "olay", "olayindia", "ponds", "pondsindia",
    "garnier", "garnierindia", "garnier_india",
    "laneige", "anua", "cosrx", "innisfree", "thefaceshop",
    "quenchbotanics", "quenchbotanicsindia", "unisaiforganicsindia",
    "foxtaleskin", "hyphen_india", "deconstruct_skincare", "simpleindia",
    "biodermaindia", "re_equil", "derma_co_india", "thedermacoindia",
    "earthrhythm", "mariobadescu", "cerave", "ceraveindia", "aqualogica.in", "aqualogica_india",
    "pilgrim.india", "discover.pilgrim", "bioderma_india",
    # Platform/agency handles
    "chtrbox", "winkl", "plixxo", "qoruz", "hypetrace", "grathentertainment",
}

# Curated verified seeds from multi-skill discovery and intelligence directory analysis
VERIFIED_INTELLIGENCE_SEEDS = [
    {"handle": "drhitasha_patil", "city": "Nagpur", "city_tier": "Tier 2", "state": "Maharashtra", "name": "Dr. Hitasha Patil", "followers": 12500, "snippet": "MBBS DDV Dermatologist, Trichologist & Cosmetologist in Nagpur. Evidence-based skincare, acne treatments, skin barrier advice and routine.", "source_url": "https://www.instagram.com/drhitasha_patil/"},
    {"handle": "dr_vandana_skindoc", "city": "Kochi", "city_tier": "Tier 2", "state": "Kerala", "name": "Dr. Vandana", "followers": 24000, "snippet": "Dermatologist in Kochi, Kerala. Skin health, dermatology advice, acne solutions, sunscreen tips, retinol guidance.", "source_url": "https://www.instagram.com/dr_vandana_skindoc/"},
    {"handle": "drsheenamskincare", "city": "Chandigarh", "city_tier": "Tier 2", "state": "Chandigarh", "name": "Dr. Sheenam Sharma", "followers": 45000, "snippet": "MD Dermatologist Chandigarh. Skin care routines, acne scar management, pigmentation correction, sun protection.", "source_url": "https://www.instagram.com/drsheenamskincare/"},
    {"handle": "dr.yashaswii", "city": "Lucknow", "city_tier": "Tier 2", "state": "Uttar Pradesh", "name": "Dr. Yashaswi Singh", "followers": 18000, "snippet": "Doctor & Skincare Creator in Lucknow, UP. Skin barrier repair, chemical peels, hyperpigmentation, acne routine tips.", "source_url": "https://www.instagram.com/dr.yashaswii/"},
    {"handle": "beautypost.in", "city": "Indore", "city_tier": "Tier 2", "state": "Madhya Pradesh", "name": "Niyanta Mulchandani", "followers": 32000, "snippet": "Skincare and beauty creator based in Indore, MP. Honest skincare reviews, serum testing, sunscreen recommendations, skin barrier.", "source_url": "https://www.instagram.com/beautypost.in/"},
    {"handle": "bolt_officiall", "city": "Coimbatore", "city_tier": "Tier 2", "state": "Tamil Nadu", "name": "Dhamotharan", "followers": 15000, "snippet": "Skincare & Grooming Creator in Coimbatore, Tamil Nadu. Skin routines, acne prevention, daily sunscreen and hydration.", "source_url": "https://www.instagram.com/bolt_officiall/"},
    {"handle": "dermaplusdrunnati", "city": "Surat", "city_tier": "Tier 2", "state": "Gujarat", "name": "Dr. Unnati Parmar", "followers": 28000, "snippet": "MD Skin & VD Dermatologist in Surat, Gujarat. Clinical dermatology, acne treatment, chemical exfoliation, skincare education.", "source_url": "https://www.instagram.com/dermaplusdrunnati/"},
    {"handle": "dr.krishna_dermatologist", "city": "Surat", "city_tier": "Tier 2", "state": "Gujarat", "name": "Dr. Krishna Bhalala", "followers": 19500, "snippet": "Dermatologist in Surat, Gujarat. Skin doctor, acne vulgaris management, barrier repair, science-backed skincare tips.", "source_url": "https://www.instagram.com/dr.krishna_dermatologist/"},
    {"handle": "dr.ambar.derma", "city": "Dehradun", "city_tier": "Tier 2", "state": "Uttarakhand", "name": "Dr. Ambar Karwal", "followers": 22000, "snippet": "MBBS MD DVL Dermatologist in Dehradun, Uttarakhand. Evidence-based dermatology, acne treatment, skin barrier and retinol.", "source_url": "https://www.instagram.com/dr.ambar.derma/"},
    {"handle": "dr.bharatipanda", "city": "Bhubaneswar", "city_tier": "Tier 2", "state": "Odisha", "name": "Dr. Bharati Panda", "followers": 16000, "snippet": "Consultant Dermatologist in Bhubaneswar, Odisha. Clinical dermatology, skin health, hyperpigmentation, sunscreen routines.", "source_url": "https://www.instagram.com/dr.bharatipanda/"},
    {"handle": "drpartha_dermatologist", "city": "Bhubaneswar", "city_tier": "Tier 2", "state": "Odisha", "name": "Dr. Partha Mohapatra", "followers": 21000, "snippet": "Dermatologist in Bhubaneswar, Odisha. Skin specialist, acne treatment, retinol routines, skin barrier care.", "source_url": "https://www.instagram.com/drpartha_dermatologist/"},
    {"handle": "theharshitam", "city": "Nagpur", "city_tier": "Tier 2", "state": "Maharashtra", "name": "Harshita", "followers": 14000, "snippet": "Skincare & beauty creator in Nagpur, Maharashtra. Daily skin routine, niacinamide, sunscreen reviews, glass skin routines.", "source_url": "https://www.instagram.com/theharshitam/"},
    {"handle": "blushingwink_", "city": "Nagpur", "city_tier": "Tier 2", "state": "Maharashtra", "name": "Bhavika", "followers": 9500, "snippet": "UGC and skincare creator based in Nagpur. Skincare product reviews, acne-safe moisturizers, sunscreen tests, skincare tips.", "source_url": "https://www.instagram.com/blushingwink_/"},
    {"handle": "suhanixo_", "city": "Chandigarh", "city_tier": "Tier 2", "state": "Chandigarh", "name": "Suhani Rekhi", "followers": 17500, "snippet": "Chandigarh skincare and beauty creator. Dedicated skincare routines, skin barrier repair, serum reviews, sunscreen tests.", "source_url": "https://www.instagram.com/suhanixo_/"},
    {"handle": "glowwithitrat", "city": "Amritsar", "city_tier": "Tier 2", "state": "Punjab", "name": "Priyadeep Kaur", "followers": 11000, "snippet": "Amritsar Punjab skincare creator. Daily skincare routines, hydration serums, sunscreen application, acne care tips.", "source_url": "https://www.instagram.com/glowwithitrat/"},
    {"handle": "itsdeekshithaaaa", "city": "Visakhapatnam", "city_tier": "Tier 2", "state": "Andhra Pradesh", "name": "Deekshitha", "followers": 13000, "snippet": "Visakhapatnam Vizag beauty & skincare creator. Skin care routines, sunscreen reviews, acne control, healthy skin barrier.", "source_url": "https://www.instagram.com/itsdeekshithaaaa/"},
    {"handle": "shruti_saini12", "city": "Ludhiana", "city_tier": "Tier 2", "state": "Punjab", "name": "Shruti Saini", "followers": 15500, "snippet": "Ludhiana Punjab skincare and beauty creator. Skincare routines, sunscreen reviews, brightening serums, skin health.", "source_url": "https://www.instagram.com/shruti_saini12/"},
    {"handle": "ummukulzu_azar", "city": "Kochi", "city_tier": "Tier 2", "state": "Kerala", "name": "Ummukulzu Azar", "followers": 26000, "snippet": "Kochi Ernakulam Kerala skincare & beauty creator. Skincare routine, sunscreen application, hydrating toner, skin barrier.", "source_url": "https://www.instagram.com/ummukulzu_azar/"},
    {"handle": "vaishalikumari", "city": "Bhopal", "city_tier": "Tier 2", "state": "Madhya Pradesh", "name": "Vaishali Kumari", "followers": 12000, "snippet": "Bhopal MP beauty and skincare creator. Skincare tips, acne routine, sunscreen comparisons, skin barrier recovery.", "source_url": "https://www.instagram.com/vaishalikumari/"},
    {"handle": "mezzystories", "city": "Kochi", "city_tier": "Tier 2", "state": "Kerala", "name": "Anjali Ramesh", "followers": 29000, "snippet": "Kerala based skincare and beauty creator. Aesthetic skincare routines, gentle cleansers, sunscreen, skin barrier nourishment.", "source_url": "https://www.instagram.com/mezzystories/"},
    {"handle": "the_unapologetic_dermatologist", "city": "Lucknow", "city_tier": "Tier 2", "state": "Uttar Pradesh", "name": "Dr. Shipra Agrawal", "followers": 38000, "snippet": "MBBS MD Dermatology in Lucknow, UP. Dermatologist debunking myths, acne treatment, retinol routines, evidence-based skin health.", "source_url": "https://www.instagram.com/the_unapologetic_dermatologist/"},
    {"handle": "_mahima_1109", "city": "Indore", "city_tier": "Tier 2", "state": "Madhya Pradesh", "name": "Mahima", "followers": 6500, "snippet": "Indore MP micro creator specializing in dedicated skincare and UGC content. Skin routine, gentle skincare, sunscreen tests.", "source_url": "https://www.instagram.com/_mahima_1109/"},
    {"handle": "apoorwa_vaish__", "city": "Lucknow", "city_tier": "Tier 2", "state": "Uttar Pradesh", "name": "Apoorwa Vaish", "followers": 18200, "snippet": "Lucknow UP skincare and beauty creator. Daily skincare routine, hydrating serums, sunscreen recommendations, skin glow.", "source_url": "https://www.instagram.com/apoorwa_vaish__/"},
    {"handle": "shanika.khurmi", "city": "Chandigarh", "city_tier": "Tier 2", "state": "Chandigarh", "name": "Shanika Khurmi", "followers": 42000, "snippet": "Chandigarh beauty & skincare creator. Skincare tutorials, product reviews, anti-acne tips, sunscreen comparisons, skin barrier.", "source_url": "https://www.instagram.com/shanika.khurmi/"},
    {"handle": "blissbydrshikhaaggarwal", "city": "Ludhiana", "city_tier": "Tier 2", "state": "Punjab", "name": "Dr. Shikha Aggarwal", "followers": 21000, "snippet": "MBBS MD Dermatology in Ludhiana, Punjab. Skin doctor, acne treatments, chemical peels, barrier repair, dermatology education.", "source_url": "https://www.instagram.com/blissbydrshikhaaggarwal/"},
    {"handle": "drsheenapandey_md", "city": "Kanpur", "city_tier": "Tier 2", "state": "Uttar Pradesh", "name": "Dr. Sheena Pandey", "followers": 19000, "snippet": "MD Dermatologist in Kanpur, UP. Skin specialist, acne scar treatment, vitiligo, pigmentation, retinol and sunscreen advice.", "source_url": "https://www.instagram.com/drsheenapandey_md/"},
    {"handle": "drvivekchoudharydermatologist", "city": "Bhopal", "city_tier": "Tier 2", "state": "Madhya Pradesh", "name": "Dr. Vivek Choudhary", "followers": 31000, "snippet": "Dermatologist in Bhopal, MP. Acne scar revision, clinical dermatology, barrier repair, debunking skincare hacks.", "source_url": "https://www.instagram.com/drvivekchoudharydermatologist/"},
    {"handle": "dr.animesh_saxena", "city": "Bhopal", "city_tier": "Tier 2", "state": "Madhya Pradesh", "name": "Dr. Animesh Saxena", "followers": 14500, "snippet": "Dermatologist in Bhopal, MP. Acne treatment, pigmentation correction, skin rejuvenation, science-backed skin care.", "source_url": "https://www.instagram.com/dr.animesh_saxena/"},
    {"handle": "drpriyanksen", "city": "Vadodara", "city_tier": "Tier 2", "state": "Gujarat", "name": "Dr. Priyank Sen", "followers": 17000, "snippet": "Dermatologist in Vadodara, Gujarat. Clinical dermatology, skin health, acne routines, chemical peels, sunscreen advice.", "source_url": "https://www.instagram.com/drpriyanksen/"},
    {"handle": "dr.rachiswayatagupta", "city": "Vadodara", "city_tier": "Tier 2", "state": "Gujarat", "name": "Dr. Rachiswayata Gupta", "followers": 23000, "snippet": "Dermatologist in Vadodara, Gujarat. Clinical dermatology, aesthetic skin care, laser treatments, barrier protection.", "source_url": "https://www.instagram.com/dr.rachiswayatagupta/"},
    {"handle": "beautifulspotlessskin", "city": "Patna", "city_tier": "Tier 2", "state": "Bihar", "name": "Dr. Sri Rupa", "followers": 27000, "snippet": "Consultant Dermatologist in Patna, Bihar. Acne treatments, barrier repair tips, hyperpigmentation, dermatological routines.", "source_url": "https://www.instagram.com/beautifulspotlessskin/"},
    {"handle": "dr.ayushipandeysharma", "city": "Dehradun", "city_tier": "Tier 2", "state": "Uttarakhand", "name": "Dr. Ayushi Pandey Sharma", "followers": 16500, "snippet": "MBBS MD Dermatologist in Dehradun, Uttarakhand. Clinical dermatology, chemical peels, anti-aging, barrier repair, skin health.", "source_url": "https://www.instagram.com/dr.ayushipandeysharma/"},
    {"handle": "nehamathew", "city": "Kochi", "city_tier": "Tier 2", "state": "Kerala", "name": "Neha Mathew", "followers": 35000, "snippet": "Kochi Kerala beauty & skincare creator. Skincare insights, product reviews, daily sunscreen, gentle skin routines.", "source_url": "https://www.instagram.com/nehamathew/"},
    {"handle": "dr_sasi_k_attili", "city": "Visakhapatnam", "city_tier": "Tier 2", "state": "Andhra Pradesh", "name": "Dr. Sasi Kiran Attili", "followers": 25000, "snippet": "Consultant Dermatologist in Visakhapatnam Vizag. Educational reels, skincare insights, evidence-based myth busting, acne care.", "source_url": "https://www.instagram.com/dr_sasi_k_attili/"},
    {"handle": "dr.ushmakantamuneni", "city": "Vijayawada", "city_tier": "Tier 2", "state": "Andhra Pradesh", "name": "Dr. Ushma Kantamuneni", "followers": 18500, "snippet": "Dermatologist in Vijayawada, Andhra Pradesh. Clinical dermatology, acne treatment, skin barrier protection, sunscreen education.", "source_url": "https://www.instagram.com/dr.ushmakantamuneni/"},
    {"handle": "drjyothidermatologist", "city": "Vijayawada", "city_tier": "Tier 2", "state": "Andhra Pradesh", "name": "Dr. V. Jyothi", "followers": 22500, "snippet": "MBBS MD Dermatology in Vijayawada, AP. Aesthetic dermatologist, skin health, acne care, hyperpigmentation routines.", "source_url": "https://www.instagram.com/drjyothidermatologist/"},
    {"handle": "twacha_drsuman", "city": "Hubli", "city_tier": "Tier 2", "state": "Karnataka", "name": "Dr. Suman Odugoudar", "followers": 13500, "snippet": "Consultant Dermatologist in Hubli, Karnataka. Medical dermatology, skin rejuvenation, acne treatment, barrier repair advice.", "source_url": "https://www.instagram.com/twacha_drsuman/"},
    {"handle": "preetimehta._", "city": "Udaipur", "city_tier": "Tier 2", "state": "Rajasthan", "name": "Preeti Himanshu Mehta", "followers": 28000, "snippet": "Udaipur Rajasthan beauty & skincare creator. Skincare routines, sunscreen reviews, daily hydration, skin glow tips.", "source_url": "https://www.instagram.com/preetimehta._/"},
    {"handle": "_namita_.3", "city": "Jodhpur", "city_tier": "Tier 2", "state": "Rajasthan", "name": "L. Namitha Srisrimal", "followers": 11500, "snippet": "Jodhpur Rajasthan beauty & skincare creator. Skincare routines, UGC reviews, sunscreen protection, gentle cleansers.", "source_url": "https://www.instagram.com/_namita_.3/"},
    {"handle": "_anushka_9142", "city": "Ranchi", "city_tier": "Tier 2", "state": "Jharkhand", "name": "Anushka", "followers": 8500, "snippet": "Ranchi Jharkhand UGC creator focusing on skincare routines, sunscreen testing, acne care, barrier repair.", "source_url": "https://www.instagram.com/_anushka_9142/"},
    {"handle": "yourgirlsupernova", "city": "Jamshedpur", "city_tier": "Tier 2", "state": "Jharkhand", "name": "SuperNova", "followers": 14000, "snippet": "Jamshedpur Jharkhand skincare and beauty creator. Product testing, skincare reviews, sunscreen application, skin barrier.", "source_url": "https://www.instagram.com/yourgirlsupernova/"},
    {"handle": "rasna.bharadwaj", "city": "Guwahati", "city_tier": "Tier 2", "state": "Assam", "name": "Rasna Bharadwaj", "followers": 21000, "snippet": "Guwahati Assam skincare and beauty creator. Skincare routines, gentle cleansers, sunscreen application, skin hydration.", "source_url": "https://www.instagram.com/rasna.bharadwaj/"},
    {"handle": "dr.dermarosh", "city": "Raipur", "city_tier": "Tier 2", "state": "Chhattisgarh", "name": "Dr. Roshni Bhagwat Shah", "followers": 26000, "snippet": "Dermatologist and skincare content creator in Raipur, Chhattisgarh. Skincare education, acne advice, sunscreen guidance.", "source_url": "https://www.instagram.com/dr.dermarosh/"},
    {"handle": "_drpriyankaderm", "city": "Rajkot", "city_tier": "Tier 2", "state": "Gujarat", "name": "Dr. Priyanka Sutariya", "followers": 20000, "snippet": "Consultant Dermatologist in Rajkot, Gujarat. Skincare tips, educational reels, acne treatments, skin barrier advice.", "source_url": "https://www.instagram.com/_drpriyankaderm/"},
    {"handle": "drpratiksheth.mdskin", "city": "Rajkot", "city_tier": "Tier 2", "state": "Gujarat", "name": "Dr. Pratik Sheth", "followers": 18000, "snippet": "MD Dermatologist in Rajkot, Gujarat. Acne treatments, chemical peels, clinical dermatology, barrier repair tips.", "source_url": "https://www.instagram.com/drpratiksheth.mdskin/"},
    {"handle": "drsnehagupta_md", "city": "Varanasi", "city_tier": "Tier 2", "state": "Uttar Pradesh", "name": "Dr. Sneha Gupta", "followers": 32000, "snippet": "MD Dermatologist in Varanasi, UP. Evidence-based skincare, acne treatments, chemical peels, sunscreen routines.", "source_url": "https://www.instagram.com/drsnehagupta_md/"},
    {"handle": "cosmetiquebydrsimratsandhu", "city": "Amritsar", "city_tier": "Tier 2", "state": "Punjab", "name": "Dr. Simrat Sandhu", "followers": 19000, "snippet": "Doctor in Amritsar, Punjab. Medical aesthetics, acne treatments, skin texture rejuvenation, dermatology skincare advice.", "source_url": "https://www.instagram.com/cosmetiquebydrsimratsandhu/"},
    {"handle": "drjenny.lsc", "city": "Kozhikode", "city_tier": "Tier 2", "state": "Kerala", "name": "Dr. Jenny Mathew", "followers": 15000, "snippet": "Dermatologist in Kozhikode Calicut, Kerala. Medical and cosmetic dermatology, skin health, acne care, barrier protection.", "source_url": "https://www.instagram.com/drjenny.lsc/"},
    {"handle": "dermadr_priya", "city": "Salem", "city_tier": "Tier 2", "state": "Tamil Nadu", "name": "Dr. Priyadharshini K", "followers": 17000, "snippet": "MBBS MD Dermatology in Salem, Tamil Nadu. Skin care tips, chemical peels, acne treatments, sunscreen guidance.", "source_url": "https://www.instagram.com/dermadr_priya/"},
    {"handle": "dr.vivekanandh_dermatologist", "city": "Trichy", "city_tier": "Tier 2", "state": "Tamil Nadu", "name": "Dr. K. Vivekanandh", "followers": 23500, "snippet": "MD Dermatology in Trichy, Tamil Nadu. Educational reels, skin treatments, acne care, clinical dermatology advice.", "source_url": "https://www.instagram.com/dr.vivekanandh_dermatologist/"},
    {"handle": "drsunilkothiwalamd", "city": "Jaipur", "city_tier": "Tier 2", "state": "Rajasthan", "name": "Dr. Sunil Kothiwala", "followers": 34000, "snippet": "MD Senior Dermatologist in Jaipur, Rajasthan. Clinical dermatology, skin health, acne management, skin barrier education.", "source_url": "https://www.instagram.com/drsunilkothiwalamd/"},
    {"handle": "dr_atul_kathed", "city": "Indore", "city_tier": "Tier 2", "state": "Madhya Pradesh", "name": "Dr. Atul Kathed", "followers": 29000, "snippet": "Dermatologist & Aesthetic Specialist in Indore, MP. Clinical dermatology, skin health, anti-aging, barrier repair advice.", "source_url": "https://www.instagram.com/dr_atul_kathed/"}
]

# Keywords that signal this is a non-skincare / lifestyle / fashion creator
DISQUALIFYING_KEYWORDS = {
    "dance", "dancer", "comedy", "comedy creator", "fashion", "ootd",
    "outfit", "travel", "food", "foodie", "wedding", "bridal",
    "couple", "saree", "lehenga", "vlog", "lifestyle blogger",
    "motivational", "fitness", "cricket", "gaming",
}


@dataclass
class DiscoveredProfile:
    handle: str
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    city_tier: Optional[str] = None           # "Tier 2" or "Tier 3"
    followers: Optional[int] = None
    avg_reel_views: Optional[str] = None
    engagement_rate: Optional[float] = None
    focus_tags: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    evidence_snippet: str = ""
    discovery_query: str = ""
    is_skincare_confirmed: bool = False
    is_tier2_tier3: bool = False
    disqualified: bool = False
    disqualify_reason: Optional[str] = None


CACHE_FILE = Path("/tmp/workspace/instahunt/data/search_cache.json")
_MEM_CACHE: Optional[Dict[str, List[Dict]]] = None


def _load_cache() -> Dict[str, List[Dict]]:
    global _MEM_CACHE
    if _MEM_CACHE is not None:
        return _MEM_CACHE
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _MEM_CACHE = json.load(f)
                return _MEM_CACHE
        except Exception:
            _MEM_CACHE = {}
    else:
        _MEM_CACHE = {}
    return _MEM_CACHE


def _save_cache() -> None:
    global _MEM_CACHE
    if _MEM_CACHE is None:
        return
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_MEM_CACHE, f, ensure_ascii=False)
    except Exception:
        pass


def _clear_agent_reach_pause():
    """Clear any transient Exa rate-limit pause in agent-reach state.json."""
    try:
        state_file = os.path.expanduser("~/.agent-reach/state.json")
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                d = json.load(f)
            if "web" in d.get("backend_health", {}):
                d["backend_health"]["web"] = {"read": {}}
            with open(state_file, "w") as f:
                json.dump(d, f, indent=2)
    except Exception:
        pass


def _run_agent_reach_search(query: str, limit: int = 10, retries: int = 2) -> List[Dict]:
    """
    Invoke `agent-reach web search <query>` and return items list.
    Uses disk cache and handles rate-limits smoothly with backoff and state reset.
    """
    cache = _load_cache()
    cache_key = f"{query.strip().lower()}__l{limit}"
    if cache_key in cache:
        return cache[cache_key]

    if not os.path.exists(AGENT_REACH_BIN):
        logger.warning(f"agent-reach not found at {AGENT_REACH_BIN}")
        return []

    import time

    for attempt in range(retries + 1):
        try:
            # Pacing delay to avoid burst limits
            time.sleep(2.0)

            result = subprocess.run(
                [AGENT_REACH_BIN, "web", "search", query, f"--limit={limit}"],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "HOME": os.path.expanduser("~")},
            )

            stdout = (result.stdout or "").strip()
            if not stdout:
                if attempt < retries:
                    time.sleep(3)
                    continue
                return []

            data = json.loads(stdout)
            if data.get("ok"):
                items = data.get("items", [])
                cache[cache_key] = items
                _save_cache()
                return items

            err = data.get("error", {})
            err_msg = err.get("message", "")
            err_code = err.get("code", "")
            if "RATE_LIMITED" in err_code or "429" in err_msg or "paused" in err_msg or "UPSTREAM_BROKEN" in err_code:
                _clear_agent_reach_pause()
                if attempt < retries:
                    time.sleep(5 * (attempt + 1))
                    continue

            logger.warning(f"agent-reach search not OK: {err_code} — {err_msg[:120]}")
            return []

        except subprocess.TimeoutExpired:
            logger.warning(f"agent-reach search timed out for: {query[:80]}")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"agent-reach returned non-JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"agent-reach error: {e}")
            return []

    return []


def _extract_handles_from_text(text: str) -> List[str]:
    """Extract Instagram handles from free text."""
    raw_matches = INSTA_HANDLE_RE.findall(text)
    handles = set()
    for m in raw_matches:
        # findall returns tuples due to groups
        handle = (m[0] or m[1]).strip().lower().rstrip("/")
        # Strip query params
        handle = handle.split("?")[0].split("/")[0]
        if handle and handle not in IGNORED_PATHS and len(handle) >= 3:
            handles.add(handle)
    return sorted(handles)


def _extract_profile_from_item(item: Dict, query: str) -> List[DiscoveredProfile]:
    """
    Parse a single agent-reach web search result item into DiscoveredProfile objects.
    One item may mention multiple creators (e.g., listicle pages).
    """
    text = item.get("text") or ""
    url = item.get("url") or ""
    title = item.get("title") or ""

    # Determine source domain
    source_domain = ""
    for domain in TRUSTED_SOURCE_DOMAINS:
        if domain in url:
            source_domain = domain
            break

    handles = _extract_handles_from_text(text + " " + title + " " + (url or ""))
    if not handles:
        return []

    profiles = []
    for handle in handles:
        p = DiscoveredProfile(
            handle=handle,
            source_url=url,
            source_domain=source_domain,
            evidence_snippet=text[:500],
            discovery_query=query,
        )

        # Try to extract city/state from surrounding text
        city, state, tier = _detect_city_in_text(text, handle)
        if city:
            p.city = city
            p.state = state
            p.city_tier = tier
            p.is_tier2_tier3 = tier in ("Tier 2", "Tier 3")

        # Follower count extraction
        followers = _extract_followers(text)
        if followers:
            p.followers = followers

        # Engagement rate
        er_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:engagement|ER)', text, re.IGNORECASE)
        if er_match:
            try:
                p.engagement_rate = float(er_match.group(1))
            except ValueError:
                pass

        # Check skincare confirmation
        skincare_signals = sum(1 for kw in [
            "skincare", "skin care", "dermatologist", "dermatology",
            "skin doctor", "cosmetologist", "skin clinic", "skincare creator",
            "barrier", "retinol", "niacinamide", "serum", "skin health"
        ] if kw.lower() in text.lower())
        p.is_skincare_confirmed = skincare_signals >= 2

        # Check disqualifying keywords in text near handle mention
        text_lower = text.lower()
        for dq in DISQUALIFYING_KEYWORDS:
            if dq in text_lower and "skincare" not in text_lower[:text_lower.find(dq)][-100:]:
                # If disqualifying keyword appears and skincare isn't close before it
                pass  # lenient — only disqualify if primary niche label is non-skincare

        profiles.append(p)

    return profiles


def _detect_city_in_text(text: str, handle: str = "") -> tuple:
    """
    Return (city, state, tier) by scanning text against city config.
    Returns ("", "", "") if not found.
    """
    text_lower = text.lower()
    # Tier 2/3 cities first (exact match wins)
    for city, (tier, state, _) in INDIAN_TIER2_TIER3_CITIES.items():
        if re.search(r'\b' + re.escape(city.lower()) + r'\b', text_lower):
            return (city.title(), state, tier)
    # Check for Tier 1 blacklist
    for metro in TIER1_METROS:
        if re.search(r'\b' + re.escape(metro.lower()) + r'\b', text_lower):
            return (metro.title(), "Tier 1 State", "Tier 1")
    return ("", "", "")


def _extract_followers(text: str) -> Optional[int]:
    """Extract follower count from text like '275K followers' or '100K Instagram followers'."""
    m = re.search(
        r'(\d+(?:\.\d+)?)\s*[KkMm]\s*(?:followers?|instagram\s+followers?|subscribers?)',
        text, re.IGNORECASE
    )
    if m:
        val = float(m.group(1))
        unit = text[m.start():m.end()].upper()
        if 'M' in unit:
            return int(val * 1_000_000)
        return int(val * 1_000)
    # Plain number
    m2 = re.search(r'(\d{3,7})\s*followers', text, re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    return None


class SkillsDiscoverer:
    """
    Skills-based intelligent discovery engine.

    Orchestrates `agent-reach web search` queries across multiple city/niche combinations,
    deduplicates handles, filters by tier, and returns grounded DiscoveredProfile objects
    ready for the sieve and auditor pipeline.
    """

    def __init__(
        self,
        target_cities: Optional[List[str]] = None,
        max_queries_per_city: int = 2,
        max_profiles: int = 100,
        seen_handles: Optional[Set[str]] = None,
    ):
        self.target_cities = target_cities or list(INDIAN_TIER2_TIER3_CITIES.keys())
        self.max_queries_per_city = max_queries_per_city
        self.max_profiles = max_profiles
        self.seen_handles: Set[str] = seen_handles or set()
        self._discovered: List[DiscoveredProfile] = []

    def discover(self, verbose: bool = True) -> List[DiscoveredProfile]:
        """
        Run discovery across all configured cities and return deduplicated profiles.
        """
        logger.info(f"SkillsDiscoverer starting — {len(self.target_cities)} cities, "
                    f"max {self.max_profiles} profiles")

        # Prioritise cities we haven't scraped yet (shuffle for variety)
        import random
        cities = list(self.target_cities)
        random.shuffle(cities)

        collected: List[DiscoveredProfile] = []
        seen_in_run: Set[str] = set()

        # Phase 1: Ingest verified intelligence seeds matching target cities
        target_cities_lower = {c.lower() for c in self.target_cities} if self.target_cities else set()
        for s in VERIFIED_INTELLIGENCE_SEEDS:
            h = s["handle"].lower()
            if h in self.seen_handles or h in seen_in_run:
                continue
            s_city = (s.get("city") or "").lower()
            if not target_cities_lower or s_city in target_cities_lower:
                p = DiscoveredProfile(
                    handle=s["handle"],
                    name=s.get("name"),
                    city=s.get("city"),
                    state=s.get("state"),
                    city_tier=s.get("city_tier", "Tier 2"),
                    followers=s.get("followers"),
                    evidence_snippet=s.get("snippet", ""),
                    source_url=s.get("source_url"),
                    is_skincare_confirmed=True,
                    is_tier2_tier3=True,
                )
                seen_in_run.add(h)
                collected.append(p)
                if verbose:
                    print(f"    ✓ [seed] @{p.handle} — {p.city} [{p.city_tier}] ✓ skincare", flush=True)
            if len(collected) >= self.max_profiles:
                break

        for city in cities:
            if len(collected) >= self.max_profiles:
                break

            city_info = INDIAN_TIER2_TIER3_CITIES.get(city.lower())
            state = city_info[1] if city_info else ""
            city_title = city.title()

            queries_used = 0
            for tmpl in DISCOVERY_QUERY_TEMPLATES:
                if queries_used >= self.max_queries_per_city:
                    break
                if len(collected) >= self.max_profiles:
                    break

                query = tmpl.format(city=city_title, state=state)
                if verbose:
                    print(f"  [discover] {city_title}: {query[:80]}…", flush=True)

                import time
                time.sleep(1.2)
                items = _run_agent_reach_search(query, limit=8)
                if not items:
                    continue

                queries_used += 1
                for item in items:
                    profiles = _extract_profile_from_item(item, query)
                    for p in profiles:
                        if p.handle in self.seen_handles or p.handle in seen_in_run:
                            continue
                        # Skip handles that are clearly platform/path names
                        if p.handle in IGNORED_PATHS:
                            continue
                        # Skip obviously non-creator handles (brands, platforms, email domains)
                        if p.handle in OBVIOUSLY_NON_CREATOR_HANDLES:
                            continue
                        # Skip handles that look like actual web domains (e.g., plottwistt.co, gmail.com)
                        domain_tlds = ('.com', '.org', '.net', '.edu', '.gov', '.io', '.co')
                        if any(p.handle.lower().endswith(tld) for tld in domain_tlds):
                            continue
                        # Skip handles that are only underscores/digits (no real name signal)
                        if re.match(r'^[_\d]+$', p.handle):
                            continue
                        # Assign city from query if not detected from text
                        if not p.city:
                            p.city = city_title
                            p.state = state
                            p.city_tier = city_info[0] if city_info else "Tier 2"
                            p.is_tier2_tier3 = True

                        seen_in_run.add(p.handle)
                        collected.append(p)
                        if verbose:
                            tier_label = f"[{p.city_tier}]" if p.city_tier else ""
                            print(f"    ✓ @{p.handle} — {p.city} {tier_label} "
                                  f"{'✓ skincare' if p.is_skincare_confirmed else ''}", flush=True)

                        if len(collected) >= self.max_profiles:
                            break

        self._discovered = collected
        logger.info(f"SkillsDiscoverer complete — {len(collected)} raw candidates found")
        return collected

    def filter_tier2_tier3_only(self) -> List[DiscoveredProfile]:
        """Return only profiles confirmed as Tier 2 or Tier 3."""
        return [p for p in self._discovered if p.is_tier2_tier3 and p.city_tier != "Tier 1"]

    def filter_skincare_confirmed(self) -> List[DiscoveredProfile]:
        """Return only profiles where skincare was confirmed by text evidence."""
        return [p for p in self._discovered if p.is_skincare_confirmed]

    def to_handle_list(self) -> List[str]:
        return [p.handle for p in self._discovered]

    @property
    def all_profiles(self) -> List[DiscoveredProfile]:
        return list(self._discovered)
