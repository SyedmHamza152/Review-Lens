"""Optional lightweight English gloss translation.

Deterministic dictionary-based gloss for dashboard readability. Produces a
translation ONLY when token coverage is sufficient; otherwise returns None
instead of garbage. Original text is always preserved in text_original.
"""
from __future__ import annotations

import re

# Roman Urdu / Urdu -> English gloss (common review vocabulary)
_GLOSS: dict[str, str] = {
    "acha": "good", "achi": "good", "achay": "good", "aala": "excellent",
    "zabardast": "excellent", "kamaal": "amazing", "behtareen": "the best",
    "shandar": "great", "umda": "fine", "lajawab": "amazing", "mast": "great",
    "pasand": "like", "theek": "okay", "sahi": "right", "bohat": "very",
    "bilkul": "absolutely", "zyada": "too much", "thora": "a bit",
    "thori": "a bit", "kafi": "quite", "hai": "is", "hain": "are",
    "tha": "was", "thi": "was", "nahi": "not", "nahin": "not", "nai": "not",
    "lekin": "but", "magar": "but", "aur": "and", "ye": "this", "yeh": "this",
    "wo": "that", "woh": "that", "mein": "in", "ka": "of", "ke": "of",
    "ki": "of", "ko": "to", "se": "from", "koi": "any", "masla": "problem",
    "issue": "problem", "kharab": "bad/defective", "bekar": "useless",
    "bakwas": "nonsense", "ghatiya": "low-grade", "faltu": "worthless",
    "fazool": "useless", "nakli": "fake", "jaali": "fake", "copy": "replica",
    "asli": "original", "original": "original", "dhoka": "deception",
    "fraud": "fraud", "scam": "scam", "paisay": "money", "paisa": "money",
    "wasool": "recovered/worth", "qeemat": "price", "rate": "price",
    "mehnga": "expensive", "mehngi": "expensive", "sasta": "cheap",
    "toota": "broke", "toot": "broke", "nuqsan": "loss", "ghata": "loss",
    "pareshan": "troubled", "dair": "late", "late": "late", "jaldi": "quickly",
    "delivery": "delivery", "shipping": "shipping", "mila": "received",
    "mili": "received", "band": "off/dead", "hang": "hangs", "slow": "slow",
    "tez": "fast", "kamzor": "weak", "battery": "battery", "backup": "backup",
    "camera": "camera", "display": "display", "sound": "sound",
    "quality": "quality", "waste": "waste", "zaya": "wasted",
    "barbaad": "ruined", "recommend": "recommend", "best": "best",
    "shukriya": "thanks", "khush": "happy", "mutmain": "satisfied",
    "mazboot": "sturdy", "durable": "durable", "chalta": "runs/works",
    "ghante": "hours", "din": "days", "hafta": "week", "maheena": "month",
    "pehle": "before/earlier", "baad": "after", "abhi": "now",
    "kal": "yesterday/tomorrow", "aaj": "today", "waqt": "time", "par": "on",
    "اور": "and", "یہ": "this", "وہ": "that", "ہے": "is", "ہیں": "are",
    "تھا": "was", "تھی": "was", "نہیں": "not", "بہت": "very",
    "اچھا": "good", "اچھی": "good", "بہترین": "the best", "خراب": "bad",
    "بیکار": "useless", "پرڈکٹ": "product", "پروڈکٹ": "product",
    "قیمت": "price", "پیسے": "money", "بیٹری": "battery", "کیمرہ": "camera",
    "کوالیٹی": "quality", "معیار": "quality", "ڈیلیوری": "delivery",
    "دیر": "late", "جعلی": "fake", "اصل": "original", "شکریہ": "thanks",
    "لیکن": "but", "مگر": "but", "زبردست": "excellent", "کمال": "amazing",
    "پسند": "like", "مسئلہ": "problem", "ٹوٹ": "broke", "ٹوٹا": "broke",
    "ملا": "received", "جلدی": "quickly", "وقت": "time", "بالکل": "absolutely",
    "بھی": "also", "کا": "of", "کی": "of", "کو": "to", "سے": "from",
    "مین": "in", "میں": "in", "ہو": "is", "کے": "of", "بہت اچھا": "very good",
}

_COVERAGE_MIN = 0.35


def gloss_translate(text_original: str, language: str) -> str | None:
    """Return approximate English gloss, or None when coverage is too low."""
    if language == "english":
        return None
    tokens = re.findall(r"[\w\u0600-\u06FF]+", text_original.lower())
    if not tokens:
        return None
    translated: list[str] = []
    hits = 0
    for tok in tokens:
        g = _GLOSS.get(tok)
        if g:
            translated.append(g)
            hits += 1
        elif re.match(r"^[\u0600-\u06FF]+$", tok):
            translated.append("…")  # untranslated Urdu word
        else:
            translated.append(tok)  # keep Latin tokens (brand names etc.)
    coverage = hits / len(tokens)
    if coverage < _COVERAGE_MIN:
        return None
    return " ".join(translated)
