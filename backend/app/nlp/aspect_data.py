"""Aspect keyword data (English / Roman Urdu / Urdu script).

Aspect -> (display label, scope, keyword set). Keywords are matched against
normalized Latin tokens and raw Urdu-script tokens.
"""

ASPECTS: dict[str, dict] = {
    "quality": {
        "label": "Product Quality",
        "scope": "product",
        "keywords": {
            "quality", "kwality", "quality", "build", "material", "maal",
            "jins", "standard", "dhang", "banawat", "khoobi", "کارکردگی",
            "معیار", "بنائی", "ساخت", "مواد", "کوالیٹی",
        },
    },
    "price_value": {
        "label": "Price & Value",
        "scope": "product",
        "keywords": {
            "price", "qeemat", "rate", "paisay", "paisa", "paise", "rs",
            "mehnga", "mehngi", "sasta", "sasti", "costly", "expensive",
            "overpriced", "affordable", "wasool", "worth", "value", "cheap",
            "bargain", "budget", "قیمت", "مہنگا", "مہنگی", "سستا", "پیسے",
            "پیسہ", "قیمت کے",
        },
    },
    "durability": {
        "label": "Durability & Reliability",
        "scope": "product",
        "keywords": {
            "durable", "durability", "sturdy", "strong", "mazboot",
            "mazbooti", "toot", "toota", "tut", "last", "lasting", "tikta",
            "tiki", "reliable", "mazboot hai", "مضبوط", "ٹوٹ", "چلے", "دیر تک",
        },
    },
    "performance": {
        "label": "Performance & Function",
        "scope": "product",
        "keywords": {
            "performance", "speed", "fast", "slow", "lag", "laggy", "hang",
            "hanging", "smooth", "processing", "powerful", "snappy",
            "responsive", "tez", "raftaar", "kamzor", "chalta", "chalna",
            "working", "کارکردگی", "رفتار", "تیز", "سست", "کام",
        },
    },
    "design": {
        "label": "Design & Appearance",
        "scope": "product",
        "keywords": {
            "design", "look", "looks", "style", "color", "colour", "rang",
            "sleek", "beautiful", "pretty", "khoobsurat", "sundar", "shakal",
            "appearance", "finish", "premium", "ڈیزائن", "رنگ", "شکل", "خوبصورت",
        },
    },
    "battery": {
        "label": "Battery Life",
        "scope": "product",
        "keywords": {
            "battery", "bettry", "battrry", "betary", "charging", "charge",
            "charger", "backup", "بیٹری", "چارجنگ", "چارجر", "بیک اپ",
        },
    },
    "delivery_shipping": {
        "label": "Delivery & Shipping",
        "scope": "marketplace",
        "keywords": {
            "delivery", "shipping", "shipped", "courier", "parcel", "rider",
            "dair", "late", "jaldi", "waqt", "ترسیل", "ڈیلیوری", "کورئیر",
            "پارسل", "دیر", "وقت", "بھیج",
        },
    },
    "packaging": {
        "label": "Packaging",
        "scope": "marketplace",
        "keywords": {
            "packaging", "packing", "box", "dabba", "dibba", "seal",
            "sealed", "tape", "پیکنگ", "پیکجنگ", "ڈبہ", "ڈبے", "سیل",
        },
    },
    "customer_support": {
        "label": "Customer Support",
        "scope": "seller",
        "keywords": {
            "support", "service", "complaint", "shikayat", "response",
            "reply", "jawab", "helpline", "refund", "warranty", "guarantee",
            "return", "شکایت", "جواب", "وارنٹی", "ضمانت", "خدمت", "ریفنڈ",
        },
    },
    "seller_reliability": {
        "label": "Seller Reliability",
        "scope": "seller",
        "keywords": {
            "seller", "vendor", "shop", "dukaan", "dukan", "store",
            "beiman", "dhoka", "trusted", "bharosa", "bharosa hai",
            "بکرم", "دکان", "فروخت", "بھروسہ", "بے ایمان", "سیلر",
        },
    },
    "authenticity": {
        "label": "Authenticity",
        "scope": "product",
        "keywords": {
            "fake", "nakli", "jaali", "original", "asli", "copy", "replica",
            "counterfeit", "genuine", "firstcopy", "کاپی", "نقلی", "جعلی",
            "اصل", "نقل",
        },
    },
}

# Human-readable driver phrases used for "most mentioned" lists
ASPECT_PHRASE_POS = {
    "quality": "good quality", "price_value": "value for money",
    "durability": "feels durable", "performance": "smooth performance",
    "design": "attractive design", "battery": "good battery life",
    "delivery_shipping": "fast delivery", "packaging": "secure packaging",
    "customer_support": "helpful support", "seller_reliability": "trustworthy seller",
    "authenticity": "genuine/original product",
}
ASPECT_PHRASE_NEG = {
    "quality": "poor quality", "price_value": "overpriced / poor value",
    "durability": "broke / not durable", "performance": "lag & performance issues",
    "design": "design complaints", "battery": "weak battery life",
    "delivery_shipping": "late delivery", "packaging": "damaged packaging",
    "customer_support": "poor customer support", "seller_reliability": "unreliable seller",
    "authenticity": "fake/replica concerns",
}
