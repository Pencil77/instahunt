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

# Engagement Criteria (Gate 1: Robust Trimmed Comment Math)
MIN_AVG_COMMENTS = 100
SAMPLE_POSTS_COUNT = 12
EXCLUDE_PINNED_POSTS = True
MIN_UNPINNED_POSTS = 8
TRIMMED_MEAN_COMMENTS_THRESHOLD = 100.0
MEDIAN_COMMENTS_FLOOR = 75.0
CONSISTENCY_MIN_COUNT = 6
CONSISTENCY_MIN_COMMENTS = 65.0
DROP_TOP_POSTS = 2
DROP_BOTTOM_POSTS = 1
MIN_SKINCARE_POST_RATIO = 0.50

# Giveaway Indicators Pattern
GIVEAWAY_PATTERN_STR = r"(?:giveaway|tag\s+3\s+friends|follow\s+to\s+win|win\s+a\b|lucky\s+winner|contest\s+alert)"

# Pacing & Rate Limiting
MIN_JITTER_SECONDS = 12.0
MAX_JITTER_SECONDS = 25.0
BATCH_SIZE = 50
COOLDOWN_SLEEP_SECONDS = 300  # 5 minutes pause every batch

# Hard Tier 1 Metros & Suburbs Blacklist (Gate 2: Strictly Disqualified)
# Comprehensive metro, MMR, NCR, and satellite localities
TIER1_METROS = {
    # Mumbai MMR
    "mumbai": "Tier 1",
    "bombay": "Tier 1",
    "navi mumbai": "Tier 1",
    "thane": "Tier 1",
    "kalyan": "Tier 1",
    "dombivli": "Tier 1",
    "vasai": "Tier 1",
    "virar": "Tier 1",
    "mira bhayandar": "Tier 1",
    "ulhasnagar": "Tier 1",
    "bhiwandi": "Tier 1",
    "panvel": "Tier 1",
    "bandra": "Tier 1",
    "andheri": "Tier 1",
    "juhu": "Tier 1",
    "colaba": "Tier 1",
    "worli": "Tier 1",
    "powai": "Tier 1",
    "borivali": "Tier 1",
    "malad": "Tier 1",
    "goregaon": "Tier 1",
    "dadar": "Tier 1",
    "chembur": "Tier 1",
    "mulund": "Tier 1",
    "vashi": "Tier 1",
    "kharghar": "Tier 1",
    "nerul": "Tier 1",
    "belapur": "Tier 1",

    # Delhi NCR
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
    "indirapuram": "Tier 1",
    "vaishali": "Tier 1",
    "rohini": "Tier 1",
    "dwarka": "Tier 1",
    "saket": "Tier 1",
    "hauz khas": "Tier 1",
    "vasant kunj": "Tier 1",
    "connaught place": "Tier 1",
    "lajpat nagar": "Tier 1",
    "pitampura": "Tier 1",
    "janakpuri": "Tier 1",
    "karol bagh": "Tier 1",
    "south ex": "Tier 1",
    "cyber hub": "Tier 1",
    "dlf phase": "Tier 1",

    # Bengaluru Urban
    "bengaluru": "Tier 1",
    "bangalore": "Tier 1",
    "blr": "Tier 1",
    "whitefield": "Tier 1",
    "koramangala": "Tier 1",
    "indiranagar": "Tier 1",
    "hsr layout": "Tier 1",
    "jayanagar": "Tier 1",
    "jp nagar": "Tier 1",
    "marathahalli": "Tier 1",
    "electronic city": "Tier 1",
    "bellandur": "Tier 1",
    "sarjapur": "Tier 1",
    "hebbal": "Tier 1",
    "malleshwaram": "Tier 1",
    "yelahanka": "Tier 1",
    "btm layout": "Tier 1",
    "banashankari": "Tier 1",

    # Hyderabad Metro
    "hyderabad": "Tier 1",
    "hyd": "Tier 1",
    "secunderabad": "Tier 1",
    "cyberabad": "Tier 1",
    "gachibowli": "Tier 1",
    "banjara hills": "Tier 1",
    "jubilee hills": "Tier 1",
    "madhapur": "Tier 1",
    "hitech city": "Tier 1",
    "kondapur": "Tier 1",
    "kukatpally": "Tier 1",
    "miyapur": "Tier 1",
    "begumpet": "Tier 1",
    "sainikpuri": "Tier 1",
    "manikonda": "Tier 1",
    "kokapet": "Tier 1",
    "shamshabad": "Tier 1",

    # Chennai Metro
    "chennai": "Tier 1",
    "madras": "Tier 1",
    "adyar": "Tier 1",
    "anna nagar": "Tier 1",
    "t nagar": "Tier 1",
    "velachery": "Tier 1",
    "mylapore": "Tier 1",
    "nungambakkam": "Tier 1",
    "besant nagar": "Tier 1",
    "tambaram": "Tier 1",
    "guindy": "Tier 1",
    "porur": "Tier 1",
    "omr": "Tier 1",
    "ecr": "Tier 1",
    "vadapalani": "Tier 1",
    "thiruvanmiyur": "Tier 1",

    # Kolkata Metro
    "kolkata": "Tier 1",
    "calcutta": "Tier 1",
    "salt lake": "Tier 1",
    "bidhannagar": "Tier 1",
    "new town": "Tier 1",
    "rajarhat": "Tier 1",
    "howrah": "Tier 1",
    "ballygunge": "Tier 1",
    "alipore": "Tier 1",
    "park street": "Tier 1",
    "dum dum": "Tier 1",
    "behala": "Tier 1",
    "jadavpur": "Tier 1",
    "tollygunge": "Tier 1",
    "garia": "Tier 1",

    # Pune Metro
    "pune": "Tier 1",
    "pimpri": "Tier 1",
    "chinchwad": "Tier 1",
    "pcmc": "Tier 1",
    "kothrud": "Tier 1",
    "viman nagar": "Tier 1",
    "koregaon park": "Tier 1",
    "kalyani nagar": "Tier 1",
    "hinjewadi": "Tier 1",
    "baner": "Tier 1",
    "wakad": "Tier 1",
    "aundh": "Tier 1",
    "hadapsar": "Tier 1",
    "magarpatta": "Tier 1",
    "kharadi": "Tier 1",
    "shivajinagar": "Tier 1",
    "deccan": "Tier 1",
    "sinhagad road": "Tier 1",

    # Ahmedabad Metro
    "ahmedabad": "Tier 1",
    "amdavad": "Tier 1",
    "gandhinagar": "Tier 1",
    "sg highway": "Tier 1",
    "navrangpura": "Tier 1",
    "satellite": "Tier 1",
    "bopal": "Tier 1",
    "prahlad nagar": "Tier 1",
    "vastrapur": "Tier 1",
    "maninagar": "Tier 1",
    "chandkheda": "Tier 1",
    "gota": "Tier 1",
    "bodakdev": "Tier 1",
    "thaltej": "Tier 1",
    "cg road": "Tier 1",

    # International / Non-Indian Locations
    "dubai": "International",
    "uae": "International",
    "london": "International",
    "uk": "International",
    "united kingdom": "International",
    "usa": "International",
    "united states": "International",
    "canada": "International",
    "toronto": "International",
    "australia": "International",
    "singapore": "International",
    "nepal": "International",
    "kathmandu": "International",
    "dhaka": "International",
    "bangladesh": "International",
    "pakistan": "International",
    "karachi": "International",
    "lahore": "International",
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
    "trichy": ("Tier 2", "Tamil Nadu", ["tiruchirappalli"]),
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
    "aizawl": ("Tier 3", "Mizoram", []),
    "gangtok": ("Tier 3", "Sikkim", []),
    "dibrugarh": ("Tier 3", "Assam", []),

    # Additional & Canonical mappings from specification
    "goa": ("Tier 3", "Goa", ["panaji", "margao", "panjim"]),
    "panaji": ("Tier 3", "Goa", ["panjim"]),
    "margao": ("Tier 3", "Goa", ["madgaon"]),
    "roorkee": ("Tier 3", "Uttarakhand", []),
    "puri": ("Tier 3", "Odisha", []),
    "durg": ("Tier 3", "Chhattisgarh", ["bhilai"]),
    "bardhaman": ("Tier 3", "West Bengal", ["burdwan"]),
    "ernakulam": ("Tier 2", "Kerala", ["kochi", "cochin"]),
    "aurangabad": ("Tier 2", "Maharashtra", ["chhatrapati sambhajinagar"]),
    "mysuru": ("Tier 2", "Karnataka", ["mysore"]),
    "mangaluru": ("Tier 2", "Karnataka", ["mangalore"]),
    "hubballi-dharwad": ("Tier 2", "Karnataka", ["hubli", "dharwad"]),
    "belagavi": ("Tier 2", "Karnataka", ["belgaum"]),
    "shivamogga": ("Tier 3", "Karnataka", ["shimoga"]),
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
