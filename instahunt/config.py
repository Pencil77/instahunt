"""
Configuration and geographical knowledge base for InstaHunt.
Includes Tier 1 metro blacklist, Tier 2 / Tier 3 Indian cities database,
and niche keyword taxonomies.
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "instahunt.db"
DEFAULT_SHEET_PATH = DATA_DIR / "StormShadow.xlsx"
DEFAULT_OUTPUT_DIR = BASE_DIR / "exports"

# Engagement Criteria
MIN_AVG_COMMENTS = 100
SAMPLE_POSTS_COUNT = 12
EXCLUDE_PINNED_POSTS = True

# Pacing & Rate Limiting
MIN_JITTER_SECONDS = 12.0
MAX_JITTER_SECONDS = 25.0
BATCH_SIZE = 50
COOLDOWN_SLEEP_SECONDS = 300  # 5 minutes pause every batch

# Hard Tier 1 Metros Blacklist (Strictly Disqualified)
# Matches any mention in bio, location tags, or recent captions
TIER1_METROS = {
    "mumbai": "Tier 1",
    "bombay": "Tier 1",
    "navi mumbai": "Tier 1",
    "thane": "Tier 1",
    "delhi": "Tier 1",
    "new delhi": "Tier 1",
    "ncr": "Tier 1",
    "delhi ncr": "Tier 1",
    "noida": "Tier 1",
    "greater noida": "Tier 1",
    "gurgaon": "Tier 1",
    "gurugram": "Tier 1",
    "faridabad": "Tier 1",
    "ghaziabad": "Tier 1",
    "bengaluru": "Tier 1",
    "bangalore": "Tier 1",
    "hyderabad": "Tier 1",
    "secunderabad": "Tier 1",
    "chennai": "Tier 1",
    "madras": "Tier 1",
    "kolkata": "Tier 1",
    "calcutta": "Tier 1",
    "pune": "Tier 1",
    "ahmedabad": "Tier 1",
}

# Indian Tier 2 and Tier 3 Cities Database
# Format: canonical_name -> (tier, state, [aliases])
INDIAN_TIER2_TIER3_CITIES = {
    # Rajasthan
    "jaipur": ("Tier 2", "Rajasthan", ["pinkcity", "jaipurcity", "jaipurite"]),
    "jodhpur": ("Tier 2", "Rajasthan", ["bluecity", "sun city"]),
    "kota": ("Tier 2", "Rajasthan", ["kotacity"]),
    "bikaner": ("Tier 3", "Rajasthan", []),
    "ajmer": ("Tier 3", "Rajasthan", []),
    "udaipur": ("Tier 3", "Rajasthan", ["cityoflakes", "lakecity"]),
    "bhilwara": ("Tier 3", "Rajasthan", []),
    "alwar": ("Tier 3", "Rajasthan", []),
    "sikar": ("Tier 3", "Rajasthan", []),
    "sri ganganagar": ("Tier 3", "Rajasthan", ["ganganagar"]),
    "pali": ("Tier 3", "Rajasthan", []),
    "bharatpur": ("Tier 3", "Rajasthan", []),

    # Madhya Pradesh
    "indore": ("Tier 2", "Madhya Pradesh", ["indori", "indorecity"]),
    "bhopal": ("Tier 2", "Madhya Pradesh", ["bhopalcity"]),
    "jabalpur": ("Tier 2", "Madhya Pradesh", []),
    "gwalior": ("Tier 2", "Madhya Pradesh", []),
    "ujjain": ("Tier 3", "Madhya Pradesh", []),
    "sagar": ("Tier 3", "Madhya Pradesh", []),
    "dewas": ("Tier 3", "Madhya Pradesh", []),
    "satna": ("Tier 3", "Madhya Pradesh", []),
    "ratlam": ("Tier 3", "Madhya Pradesh", []),
    "rewa": ("Tier 3", "Madhya Pradesh", []),

    # Uttar Pradesh
    "lucknow": ("Tier 2", "Uttar Pradesh", ["nawabo ka shahar", "lucknowcity"]),
    "kanpur": ("Tier 2", "Uttar Pradesh", ["kanpurcity"]),
    "varanasi": ("Tier 2", "Uttar Pradesh", ["banaras", "kashi"]),
    "prayagraj": ("Tier 2", "Uttar Pradesh", ["allahabad"]),
    "agra": ("Tier 2", "Uttar Pradesh", ["taj city"]),
    "meerut": ("Tier 2", "Uttar Pradesh", []),
    "bareilly": ("Tier 2", "Uttar Pradesh", []),
    "aligarh": ("Tier 2", "Uttar Pradesh", []),
    "moradabad": ("Tier 2", "Uttar Pradesh", []),
    "gorakhpur": ("Tier 3", "Uttar Pradesh", []),
    "saharanpur": ("Tier 3", "Uttar Pradesh", []),
    "jhansi": ("Tier 3", "Uttar Pradesh", []),
    "firozabad": ("Tier 3", "Uttar Pradesh", []),
    "muzaffarnagar": ("Tier 3", "Uttar Pradesh", []),
    "mathura": ("Tier 3", "Uttar Pradesh", ["vrindavan"]),
    "ayodhya": ("Tier 3", "Uttar Pradesh", ["faizabad"]),

    # Gujarat
    "surat": ("Tier 2", "Gujarat", ["diamond city"]),
    "vadodara": ("Tier 2", "Gujarat", ["baroda"]),
    "rajkot": ("Tier 2", "Gujarat", []),
    "bhavnagar": ("Tier 3", "Gujarat", []),
    "jamnagar": ("Tier 3", "Gujarat", []),
    "junagadh": ("Tier 3", "Gujarat", []),
    "gandhinagar": ("Tier 3", "Gujarat", []),
    "anand": ("Tier 3", "Gujarat", []),
    "navsari": ("Tier 3", "Gujarat", []),
    "morbi": ("Tier 3", "Gujarat", []),
    "bharuch": ("Tier 3", "Gujarat", []),

    # Punjab & Haryana & Chandigarh
    "chandigarh": ("Tier 2", "Chandigarh", ["tricity", "city beautiful"]),
    "ludhiana": ("Tier 2", "Punjab", []),
    "amritsar": ("Tier 2", "Punjab", []),
    "jalandhar": ("Tier 2", "Punjab", []),
    "patiala": ("Tier 3", "Punjab", []),
    "bathinda": ("Tier 3", "Punjab", []),
    "mohali": ("Tier 3", "Punjab", ["sas nagar"]),
    "panchkula": ("Tier 3", "Haryana", []),
    "ambala": ("Tier 3", "Haryana", []),
    "panipat": ("Tier 3", "Haryana", []),
    "karnal": ("Tier 3", "Haryana", []),
    "sonipat": ("Tier 3", "Haryana", []),
    "rohtak": ("Tier 3", "Haryana", []),
    "hisar": ("Tier 3", "Haryana", []),

    # Maharashtra (Excluding Mumbai, Pune, Thane)
    "nagpur": ("Tier 2", "Maharashtra", ["orange city"]),
    "nashik": ("Tier 2", "Maharashtra", ["wine capital"]),
    "chhatrapati sambhajinagar": ("Tier 2", "Maharashtra", ["aurangabad"]),
    "solapur": ("Tier 2", "Maharashtra", []),
    "kolhapur": ("Tier 3", "Maharashtra", []),
    "amravati": ("Tier 3", "Maharashtra", []),
    "nanded": ("Tier 3", "Maharashtra", []),
    "sangli": ("Tier 3", "Maharashtra", []),
    "jalgaon": ("Tier 3", "Maharashtra", []),
    "akola": ("Tier 3", "Maharashtra", []),
    "latur": ("Tier 3", "Maharashtra", []),
    "dhule": ("Tier 3", "Maharashtra", []),
    "ahmednagar": ("Tier 3", "Maharashtra", ["ahilyanagar"]),

    # Tamil Nadu (Excluding Chennai)
    "coimbatore": ("Tier 2", "Tamil Nadu", ["kovai", "manchester of south india"]),
    "madurai": ("Tier 2", "Tamil Nadu", []),
    "tiruchirappalli": ("Tier 2", "Tamil Nadu", ["trichy"]),
    "salem": ("Tier 2", "Tamil Nadu", []),
    "tiruppur": ("Tier 3", "Tamil Nadu", ["tirupur"]),
    "erode": ("Tier 3", "Tamil Nadu", []),
    "vellore": ("Tier 3", "Tamil Nadu", []),
    "tirunelveli": ("Tier 3", "Tamil Nadu", []),
    "thoothukudi": ("Tier 3", "Tamil Nadu", ["tuticorin"]),
    "thanjavur": ("Tier 3", "Tamil Nadu", []),
    "dindigul": ("Tier 3", "Tamil Nadu", []),

    # Kerala
    "kochi": ("Tier 2", "Kerala", ["cochin", "ernakulam"]),
    "thiruvananthapuram": ("Tier 2", "Kerala", ["trivandrum"]),
    "kozhikode": ("Tier 2", "Kerala", ["calicut"]),
    "thrissur": ("Tier 3", "Kerala", ["trichur"]),
    "kollam": ("Tier 3", "Kerala", ["quilon"]),
    "palakkad": ("Tier 3", "Kerala", []),
    "alappuzha": ("Tier 3", "Kerala", ["alleppey"]),
    "kannur": ("Tier 3", "Kerala", []),
    "kottayam": ("Tier 3", "Kerala", []),
    "malappuram": ("Tier 3", "Kerala", []),

    # Andhra Pradesh
    "visakhapatnam": ("Tier 2", "Andhra Pradesh", ["vizag"]),
    "vijayawada": ("Tier 2", "Andhra Pradesh", ["bezawada"]),
    "guntur": ("Tier 2", "Andhra Pradesh", []),
    "nellore": ("Tier 3", "Andhra Pradesh", []),
    "kurnool": ("Tier 3", "Andhra Pradesh", []),
    "rajahmundry": ("Tier 3", "Andhra Pradesh", ["rajamahindravaram"]),
    "tirupati": ("Tier 3", "Andhra Pradesh", []),
    "kakinada": ("Tier 3", "Andhra Pradesh", []),
    "kadapa": ("Tier 3", "Andhra Pradesh", []),
    "anantapur": ("Tier 3", "Andhra Pradesh", []),

    # Telangana (Excluding Hyderabad/Secunderabad)
    "warangal": ("Tier 2", "Telangana", ["tri-city telangana"]),
    "nizamabad": ("Tier 3", "Telangana", []),
    "karimnagar": ("Tier 3", "Telangana", []),
    "khammam": ("Tier 3", "Telangana", []),
    "ramagundam": ("Tier 3", "Telangana", []),

    # Karnataka (Excluding Bengaluru)
    "mysore": ("Tier 2", "Karnataka", ["mysuru"]),
    "hubli": ("Tier 2", "Karnataka", ["hubballi", "hubli-dharwad"]),
    "mangalore": ("Tier 2", "Karnataka", ["mangaluru", "kudla"]),
    "belgaum": ("Tier 2", "Karnataka", ["belagavi"]),
    "gulbarga": ("Tier 3", "Karnataka", ["kalaburagi"]),
    "davanagere": ("Tier 3", "Karnataka", []),
    "bellary": ("Tier 3", "Karnataka", ["ballari"]),
    "shimoga": ("Tier 3", "Karnataka", ["shivamogga"]),
    "udupi": ("Tier 3", "Karnataka", []),
    "tumkur": ("Tier 3", "Karnataka", ["tumakuru"]),

    # Bihar & Jharkhand
    "patna": ("Tier 2", "Bihar", []),
    "gaya": ("Tier 3", "Bihar", []),
    "bhagalpur": ("Tier 3", "Bihar", []),
    "muzaffarpur": ("Tier 3", "Bihar", []),
    "ranchi": ("Tier 2", "Jharkhand", []),
    "jamshedpur": ("Tier 2", "Jharkhand", ["tatanagar"]),
    "dhanbad": ("Tier 2", "Jharkhand", []),
    "bokaro": ("Tier 3", "Jharkhand", []),

    # Odisha, Chhattisgarh, West Bengal (Excl. Kolkata)
    "bhubaneswar": ("Tier 2", "Odisha", ["temple city"]),
    "cuttack": ("Tier 2", "Odisha", []),
    "rourkela": ("Tier 3", "Odisha", []),
    "raipur": ("Tier 2", "Chhattisgarh", []),
    "bilaspur": ("Tier 3", "Chhattisgarh", []),
    "bhilai": ("Tier 3", "Chhattisgarh", ["durg"]),
    "siliguri": ("Tier 3", "West Bengal", []),
    "asansol": ("Tier 3", "West Bengal", []),
    "durgapur": ("Tier 3", "West Bengal", []),

    # Uttarakhand, Himachal, J&K, North East
    "dehradun": ("Tier 2", "Uttarakhand", ["doon"]),
    "haridwar": ("Tier 3", "Uttarakhand", []),
    "haldwani": ("Tier 3", "Uttarakhand", ["nainital"]),
    "rishikesh": ("Tier 3", "Uttarakhand", []),
    "shimla": ("Tier 3", "Himachal Pradesh", []),
    "dharamshala": ("Tier 3", "Himachal Pradesh", []),
    "jammu": ("Tier 2", "Jammu and Kashmir", []),
    "srinagar": ("Tier 2", "Jammu and Kashmir", []),
    "guwahati": ("Tier 2", "Assam", []),
    "silchar": ("Tier 3", "Assam", []),
    "shillong": ("Tier 3", "Meghalaya", []),
    "agartala": ("Tier 3", "Tripura", []),
    "imphal": ("Tier 3", "Manipur", []),
}

# Core Skincare Keywords for Relevance Scoring (Pan-India & English)
SKINCARE_KEYWORDS = [
    "skincare", "skin care", "skincareroutine", "skin health", "skin barrier",
    "barrier repair", "sunscreen", "spf", "uv camera", "white cast", "sun protection",
    "serum", "retinol", "niacinamide", "salicylic", "hyaluronic", "vitamin c",
    "azelaic", "ceramides", "cica", "centella", "snail mucin", "glycolic",
    "lactic acid", "double cleansing", "cleanser", "toner", "moisturizer",
    "moisturiser", "face wash", "facewash", "acne", "cystic acne", "hormonal acne",
    "comedones", "blackheads", "whiteheads", "dark spots", "hyperpigmentation",
    "melasma", "skin texture", "glowing skin", "glowingskin", "glass skin",
    "dermatologist", "dermatology", "aesthetician", "esthetician", "skin doctor",
    "skin clinic", "skinfluencer", "skincareblogger", "skincaretips", "skingoals",
    "skincarereview", "pharmacy skincare", "kbeauty", "jbeauty"
]

# Pan-Indian Regional Language Skincare Hashtags & Markers
# Creators across South, West, East, and North India use these alongside English
REGIONAL_SKINCARE_MARKERS = {
    "all_india_english": [
        "skincare india", "indian skincare", "pharmacy skincare india",
        "budget skincare india", "dermatologist india", "acne prone skin india"
    ],
    "tamil": [
        "tamilskincare", "skincaretamil", "tamil beauty tips", "mugam", "paru", "azhagu"
    ],
    "telugu": [
        "teluguskincare", "skincaretelugu", "telugu beauty tips", "mukham", "merise chiram"
    ],
    "malayalam": [
        "malayalamskincare", "skincaremalayalam", "kerala skincare", "soundaryam"
    ],
    "kannada": [
        "kannadaskincare", "skincarekannada", "karnataka skincare"
    ],
    "marathi": [
        "marathiskincare", "skincaremarathi", "maharashtra skincare", "nital tvacha"
    ],
    "gujarati": [
        "gujaratskincare", "skincaregujarati", "twacha", "chamakti twacha"
    ],
    "bengali": [
        "bengaliskincare", "skincarebengali", "rupchorcha"
    ],
    "punjabi": [
        "punjabiskincare", "skincarepunjabi", "noor", "glowing chehra"
    ],
    "hindi_hinglish": [
        "ghar ke nuskhe", "ubtan", "dahi besan", "haldi", "skin care hindi"
    ],
}

# Strict Disqualification Keywords (Exclusivity Filter)
# Accounts with these primary focuses are NOT exclusively skincare and MUST be rejected
DISQUALIFYING_NICHE_KEYWORDS = [
    "fashion blogger", "fashion creator", "fashion influencer", "fashion style", "fashion",
    "ootd", "outfit of the day", "clothing brand", "model", "modeling",
    "lifestyle creator", "lifestyle blogger", "lifestyle influencer", "lifestyle vlogs",
    "lifestyle", "daily vlogs", "vlogger", "vlog", "vlogs", "travel blogger", "travel creator",
    "wanderlust", "foodie", "food blogger", "food reviews", "recipe creator",
    "bridal makeup", "bridal artist", "makeup artist", "mua", "hairstylist",
    "hair stylist", "salon & spa", "beauty salon", "mens grooming", "grooming & style",
    "grooming", "fitness model", "gym workout", "fitness coach", "dance reels", "dancer",
    "choreographer", "comedy creator", "comedian", "acting", "actor",
    "nutritionist", "dietitian", "clinical nutrition", "weight loss"
]

# Legacy exclusion list
EXCLUSION_KEYWORDS = DISQUALIFYING_NICHE_KEYWORDS
