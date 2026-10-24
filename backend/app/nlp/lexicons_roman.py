"""Roman Urdu sentiment lexicon + spelling-variant normalization map.

Roman Urdu = Urdu written in Latin script, very common in Pakistani online
reviews. Spelling varies heavily (bohat/bahut/bohot, acha/achha/accha, ...).
The VARIANT_MAP below folds common variants onto canonical tokens BEFORE
lexicon matching, while the original text is always preserved untouched.
"""

# ---------------------------------------------------------------------------
# 1) Spelling variant map: variant -> canonical (applied per token, lowercase)
# ---------------------------------------------------------------------------
RU_VARIANT_MAP: dict[str, str] = {
    # "very / a lot"
    "bohat": "bohat", "bahut": "bohat", "bohot": "bohat", "bhut": "bohat",
    "bohut": "bohat", "bhoot": "bohat", "bouth": "bohat", "bohatt": "bohat",
    "kafi": "kafi", "kaafi": "kafi", "zyada": "zyada", "zayada": "zyada",
    "ziaada": "zyada", "bara": "bara", "bohatzyada": "zyada",
    # good
    "acha": "acha", "achha": "acha", "accha": "acha", "aacha": "acha",
    "achaa": "acha", "atcha": "acha", "achi": "achi", "achhi": "achi",
    "achee": "achi", "aachi": "achi", "achay": "achay", "achey": "achay",
    "ache": "achay", "acha gaya": "acha",
    "ala": "aala", "aala": "aala", "allla": "aala", "alaa": "aala",
    "zabardast": "zabardast", "zabardust": "zabardast", "zabrdast": "zabardast",
    "jabardast": "zabardast", "kamaal": "kamaal", "kamal": "kamaal",
    "kamaaal": "kamaal", "behtareen": "behtareen", "behtreen": "behtareen",
    "behtarin": "behtareen", "bahtareen": "behtareen",
    "shandar": "shandar", "shandaar": "shandar", "umda": "umda",
    "lajawab": "lajawab", "lajwab": "lajawab", "la jawab": "lajawab",
    "mazedar": "mazedar", "mazaydar": "mazedar", "jhakas": "jhakas",
    "zakaas": "jhakas", "mast": "mast", "waah": "waah", "wah": "waah",
    "fit": "fit", "fitte": "fitte", "sakht": "sakht", "pasand": "pasand",
    "pasandaya": "pasand", "qabil": "qabil", "bharpoor": "bharpoor",
    "bhar pur": "bharpoor", "mukammal": "mukammal", "kamil": "mukammal",
    "shukriya": "shukriya", "shukria": "shukriya", "shukrya": "shukriya",
    "jazakallah": "jazakallah", "jazakallahkhair": "jazakallah",
    "meharbani": "meharbani", "afreen": "afreen", "shaabash": "shabash",
    "shabash": "shabash", "daad": "daad", "tareef": "tareef",
    "qeemat": "qeemat", "keemat": "qeemat", "kimat": "qeemat",
    # bad
    "kharab": "kharab", "khrab": "kharab", "kharabhae": "kharab",
    "bekar": "bekar", "bekaar": "bekar", "baykar": "bekar", "bkr": "bekar",
    "bakwas": "bakwas", "bakwaas": "bakwas", "bakkwas": "bakwas",
    "ghatiya": "ghatiya", "ghatia": "ghatiya", "ghateya": "ghatiya",
    "faltu": "faltu", "phaltu": "faltu", "fazool": "fazool",
    "fuzool": "fazool", "fuzul": "fazool",
    "nakli": "nakli", "naqli": "nakli", "jaali": "jaali", "jali": "jaali",
    "copy": "copy", "firstcopy": "copy", "replica": "copy",
    "dhoka": "dhoka", "dhokha": "dhoka", "dokha": "dhoka", "dokka": "dhoka",
    "dhokaybaz": "dhoka", "fraud": "fraud", "frad": "fraud",
    "scam": "scam", "scamm": "scam", "loot": "loot", "looot": "loot",
    "lootna": "loot", "chor": "chor", "beiman": "beiman", "beyeman": "beiman",
    "nuqsan": "nuqsan", "nuqsaan": "nuqsan", "ghata": "ghata",
    "pareshan": "pareshan", "pareshaan": "pareshan", "tang": "tang",
    "takleef": "takleef", "dukh": "dukh", "nafrat": "nafrat",
    "naapasand": "napasand", "napasand": "napasand", "bura": "bura",
    "boora": "bura", "buri": "buri", "ganda": "ganda", "gandi": "ganda",
    "mehnga": "mehnga", "mahnga": "mehnga", "mhanga": "mehnga",
    "mahainga": "mehnga", "mhangha": "mehnga", "sasta": "sasta",
    "sasta hai": "sasta", "toota": "toota", "tuta": "toota",
    "toot": "toot", "tootgaya": "toot", "torha": "toota", "phat": "phat",
    "phatti": "phat", "kharabi": "kharabi", "kharbia": "kharabi",
    "masla": "masla", "maslah": "masla", "problem": "problem",
    "issue": "issue", "dard": "dard", "kamzor": "kamzor", "kamazor": "kamzor",
    "dher": "dair", "dair": "dair", "late": "late", "lateee": "late",
    "waste": "waste", "west": "waste", "zaya": "zaya", "zaea": "zaya",
    "barbaad": "barbaad", "barbadi": "barbaad", "tabah": "tabah",
    "hang": "hang", "hangg": "hang", "latk": "hang", "latkta": "hang",
    "slow": "slow", "salow": "slow", "garam": "garam", "garm": "garam",
    "heat": "heat", "grm": "garam", "batti": "batti", "band": "band",
    "bandhogaya": "band", "sof": "sof", "sofff": "sof",
    # negations
    "nahi": "nahi", "nahin": "nahi", "nai": "nahi", "nhi": "nahi",
    "nhe": "nahi", "nh": "nahi", "na": "na", "kabhi": "kabhi",
    "bilkulnahi": "nahi",
    # conjunctions
    "lekin": "lekin", "lakin": "lekin", "lekan": "lekin", "likin": "lekin",
    "mgr": "magar", "magar": "magar", "jabke": "jabke", "jabki": "jabke",
    "halanke": "halanke", "halaanke": "halanke",
    # misc normalization
    "paisay": "paisay", "paison": "paisay", "paisa": "paisa",
    "paise": "paisay", "vasool": "wasool", "wasool": "wasool",
    "waasool": "wasool", "theek": "theek", "thik": "theek", "thiik": "theek",
    "sahi": "sahi", "chalta": "chalta", "chlti": "chalti", "chalta hai": "chalta",
    "rs": "rs", "pkr": "rs", "rupees": "rs", "rupay": "rs",
    "aur": "aur", "or": "or", "bhi": "bhi", "bi": "bhi", "tou": "to",
    "to": "to", "tu": "to", "bohat sara": "bohat",
    # common English slang used in PK reviews
    "gud": "good", "gr8": "great", "awsm": "awesome", "awsume": "awesome",
    "nvr": "never", "thnx": "thanks", "thnks": "thanks", "tysm": "thanks",
    "btr": "better", "bttr": "better", "expnsive": "expensive",
    "prfct": "perfect", "orsm": "awesome", "osm": "awesome", "v good": "good",
}

# ---------------------------------------------------------------------------
# 2) Sentiment lexicon (canonical tokens)
# ---------------------------------------------------------------------------
ROMAN_POSITIVE: dict[str, float] = {
    "acha": 1.2, "achi": 1.2, "achay": 1.2, "aala": 1.6, "zabardast": 1.8,
    "kamaal": 1.5, "behtareen": 1.8, "shandar": 1.6, "umda": 1.3,
    "lajawab": 1.7, "mazedar": 1.2, "jhakas": 1.5, "mast": 1.4,
    "waah": 1.3, "fit": 0.9, "sakht": 1.2, "pasand": 1.1,
    "qabil": 1.0, "bharpoor": 1.3, "mukammal": 0.8, "shukriya": 0.9,
    "jazakallah": 1.0, "meharbani": 0.8, "afreen": 1.0, "shabash": 1.1,
    "daad": 1.0, "tareef": 1.0, "theek": 0.5, "sahi": 0.8,
    "chalta": 0.4, "original": 0.8, "asli": 0.9, "genuine": 1.0,
    "mazboot": 1.3, "mazbooti": 1.2, "taaqatwar": 1.1, "powerful": 1.2,
    "tez": 0.8, "soft": 0.7, "naram": 0.7, "khushboo": 0.8, "khush": 1.2,
    "mutmain": 1.2, "recommend": 1.5,
    "recommendkaroonga": 1.5, "best": 1.8, "number": 0.5, "first": 0.3,
    "dhang": 0.7, "standard": 0.6, "level": 0.4, "kamaal ka": 1.5,
    "kamal ka": 1.5, "full paisa": 1.4, "paisa vasool": 1.8,
    "sasta": 0.6, "halke": 0.5, "halka": 0.5, "range mein": 0.5,
}

ROMAN_NEGATIVE: dict[str, float] = {
    "kharab": -1.5, "bekar": -1.7, "bakwas": -1.7, "ghatiya": -1.6,
    "faltu": -1.5, "fazool": -1.6, "nakli": -1.8, "jaali": -1.8,
    "copy": -1.2, "dhoka": -1.8, "fraud": -2.0, "scam": -2.0,
    "loot": -1.7, "chor": -1.6, "beiman": -1.7, "nuqsan": -1.6,
    "ghata": -1.3, "pareshan": -1.3, "tang": -1.0, "takleef": -1.3,
    "dukh": -1.2, "nafrat": -1.8, "napasand": -1.4, "bura": -1.3,
    "buri": -1.3, "ganda": -1.4, "gandi": -1.4, "mehnga": -1.1,
    "toota": -1.5, "toot": -1.4, "phat": -1.2, "kharabi": -1.4,
    "masla": -1.1, "problem": -0.9, "issue": -0.8, "dard": -1.0,
    "kamzor": -1.2, "dair": -0.9, "late": -0.9, "waste": -1.6,
    "zaya": -1.6, "barbaad": -1.7, "tabah": -1.7, "hang": -1.0,
    "slow": -0.9, "garam": -0.8, "garm": -0.8, "heat": -0.8,
    "band": -0.9, "sof": -0.5, "kam": -0.5, "na": -0.3,
    "nahipasand": -1.5, "bhaari": -0.4,
    "paisa zaya": -1.7, "bewakoof": -1.3, "bewkuf": -1.3, "ulta": -0.4,
    "kharach": -0.4, "ghata mei": -1.3, "chor bazaar": -1.5,
}

ROMAN_PHRASES: dict[str, float] = {
    "paisay wasool": 1.8, "paisa wasool": 1.8, "paisay wasool hain": 1.8,
    "paisa vasool": 1.8, "poora paisa": 1.3, "paisa poorha": 1.3,
    "bohat acha": 1.5, "bohat achi": 1.5, "bilkul theek": 1.0,
    "koi masla nahi": 1.3, "koi issue nahi": 1.2, "koi problem nahi": 1.2,
    "koi dikkat nahi": 1.2, "mat lo": -1.6, "na lo": -1.4, "lena hi mat": -1.7,
    "lene ka nahi": -1.5, "lenay ka nahi": -1.5, "paise barbaad": -1.8,
    "paisay barbaad": -1.8, "paisa zaya hai": -1.7, "waqt zaya": -1.4,
    "bilkul nahi": -1.3, "hargiz nahi": -1.4, "kabhi nahi": -1.3,
    "dil chahata hai": 0.5, "achha chalta hai": 0.5,
    "chalta hai lekin": 0.2, "sirf naam ka": -1.3, "naam ka hai": -1.2,
    "asli nahi hai": -1.7, "original nahi hai": -1.6, "nakli nikla": -1.8,
    "jaali nikla": -1.8, "copy hai": -1.4, "first copy hai": -1.4,
    "battery achi nahi": -1.3, "battery kharab": -1.4, "battery kamaal": 1.4,
    "delivery jaldi": 1.0, "delivery theek": 0.6, "delivery late": -1.2,
    "delivery bohat late": -1.4, "waqt par mila": 1.0, "waqt par": 0.8,
    "qeemat zyada": -1.1, "qeemat theek": 0.8, "qeemat kam": 0.9,
    "rate zyada": -1.0, "price zyada": -1.0, "price thori zyada": -1.0, "bilkul bekar": -1.8, "ekdum bekar": -1.8,
    "ekdum acha": 1.4, "ekdum kharab": -1.6, "ghatiya quality": -1.7,
    "quality achi": 1.3, "quality acha": 1.3, "quality kharab": -1.4,
    "quality bekar": -1.5, "quality bohat achi": 1.5, "zalim cheez": 1.4,
    "zabardast cheez": 1.6, "sakht cheez": 1.3, "kamaal ki": 1.5,
    "kamal ki": 1.5, "zabardast quality": 1.6, "achi quality": 1.4,
    "must buy": 1.6, "recommended hai": 1.4, "recommend karta hoon": 1.5,
}

ROMAN_NEGATORS = {"nahi", "na", "kabhi", "nh", "not", "never", "mat", "bilkulnahi", "hargiz"}

ROMAN_INTENSIFIERS = {
    "bohat": 1.5, "bilkul": 1.4, "zyada": 1.35, "bara": 1.3, "kafi": 1.3,
    "ekdum": 1.45, "poora": 1.25, "full": 1.3, "complete": 1.3, "total": 1.35,
    "bilkul hi": 1.45, "darja": 1.2,
}

ROMAN_DIMINISHERS = {
    "thora": 0.65, "thori": 0.65, "thora sa": 0.6, "halka": 0.7,
    "halki": 0.7, "kam": 0.7, "thoda": 0.65, "just thora": 0.6,
}

ROMAN_ADVERSATIVES = {"lekin", "magar", "jabke", "halanke", "lekin", "werna", "warna"}

ROMAN_MARKERS = {
    # function words that strongly indicate Roman Urdu
    "hai", "hain", "ho", "hun", "tha", "thi", "thay", "ka", "ke", "ki",
    "ko", "se", "mein", "me", "aur", "bhi", "ye", "yeh", "wo", "woh",
    "is", "us", "iska", "uska", "mera", "meri", "mere", "apna", "apni",
    "kuch", "koi", "kitna", "kitni", "abhi", "phir", "bilkul", "bohat",
    "acha", "achi", "nahi", "lekin", "magar", "paisay", "paisa", "qeemat",
    "hai hi", "mila", "mili", "mile", "liya", "liye", "lenge", "kar",
    "karo", "karna", "karta", "karti", "ghante", "din", "raat", "subah",
    "bohat se", "wala", "wali", "walay", "lagta", "lagi", "laga", "hoga",
    "hogi", "hota", "hoti", "raha", "rahi", "liya hai", "krna", "kr",
    "haiya", "hy", "hm", "acha hai", "sakht", "zabardast", "yaar",
}

ROMAN_STOPWORDS = {
    "hai", "hain", "ho", "hun", "tha", "thi", "thay", "ka", "ke", "ki",
    "ko", "se", "mein", "me", "aur", "bhi", "ye", "yeh", "wo", "woh",
    "is", "us", "mera", "meri", "mere", "apna", "apni", "kuch", "koi",
    "abhi", "phir", "to", "tou", "tu", "kar", "karo", "kya", "kue",
    "hy", "kr", "raha", "rahi", "liya", "liye", "diya", "de", "na",
    "wala", "wali", "walay", "par", "pe", "se", "tak", "sath", "saath",
}
