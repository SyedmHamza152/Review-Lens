"""Language detection: English / Urdu script / Roman Urdu / mixed.

Approach: script ratio + marker-token scoring with loanword handling.
Product nouns (camera, battery, quality, ...) are treated as language-neutral
loanwords because Pakistani Roman Urdu freely mixes English product nouns.
Uncertain predictions are flagged instead of being forced into a category.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.nlp.lexicons_en import EN_MARKERS
from app.nlp.lexicons_roman import ROMAN_MARKERS, ROMAN_STOPWORDS
from app.nlp.roman_urdu import tokenize

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")

# English product nouns that appear inside Roman Urdu sentences all the time.
LOANWORDS = {
    "camera", "battery", "product", "quality", "delivery", "price",
    "display", "sound", "charger", "mobile", "phone", "packing",
    "packaging", "design", "color", "colour", "box", "size", "model",
    "variant", "screen", "performance", "brand", "order", "parcel",
    "service", "review", "video", "speaker", "mic", "bass", "backup",
    "material", "warranty", "guarantee", "worth", "value", "time",
}

RU_ONLY_MARKERS = ROMAN_MARKERS - EN_MARKERS - LOANWORDS
EN_ONLY_MARKERS = EN_MARKERS - ROMAN_MARKERS - LOANWORDS


@dataclass
class LanguageResult:
    language: str            # english | urdu | roman_urdu | mixed | unknown
    detail: str = ""         # e.g. "roman_urdu+english"
    confidence: float = 0.0
    uncertain: bool = False
    scores: dict = field(default_factory=dict)


def _urdu_ratio(text: str) -> float:
    arabic = len(_ARABIC_RE.findall(text))
    letters = len(re.findall(r"[A-Za-z\u0600-\u06FF\u0750-\u077F]", text))
    return arabic / letters if letters else 0.0


def detect_language(text: str) -> LanguageResult:
    tokens = [t for t in tokenize(text) if re.search(r"[A-Za-z\u0600-\u06FF]", t)]
    if not tokens:
        return LanguageResult("unknown", confidence=0.0, uncertain=True, scores={})

    latin = [t for t in tokens if re.match(r"^[A-Za-z'’-]+$", t)]
    urdu_ratio = _urdu_ratio(text)
    n = len(latin) or 1

    lowered = [t.lower() for t in latin]
    ru_hits = sum(1 for t in lowered if t in RU_ONLY_MARKERS)
    en_hits = sum(1 for t in lowered if t in EN_ONLY_MARKERS)
    ru_score = ru_hits / n
    en_score = en_hits / n

    scores = {"urdu_script": round(urdu_ratio, 3), "roman_urdu": round(ru_score, 3),
              "english": round(en_score, 3), "latin_tokens": len(latin)}

    # ---- Urdu script present ----
    if urdu_ratio >= 0.30:
        if len(latin) >= 2 and (ru_hits + en_hits) >= 1:
            conf = min(0.95, 0.75 + 0.2 * min(1.0, (ru_hits + en_hits) / 3))
            return LanguageResult("mixed", detail="urdu_script+english", confidence=conf,
                                  uncertain=False, scores=scores)
        conf = min(0.97, 0.8 + 0.17 * urdu_ratio)
        return LanguageResult("urdu", confidence=conf, uncertain=urdu_ratio < 0.45,
                              scores=scores)

    # ---- Latin only ----
    ru_score_eff = ru_score + (0.08 if re.search(r"\b(nahi|nahin|nai|bohat|acha|lekin)\b", text.lower()) else 0)
    if ru_score_eff >= 0.12 and en_score >= 0.08:
        conf = 0.72 + 0.15 * min(1.0, (ru_hits + en_hits) / max(3, len(latin)))
        return LanguageResult("mixed", detail="roman_urdu+english", confidence=min(0.95, conf),
                              uncertain=len(latin) < 4, scores=scores)
    if ru_score_eff >= 0.12:
        conf = min(0.95, 0.62 + 0.3 * min(1.0, ru_score * 3))
        return LanguageResult("roman_urdu", confidence=conf,
                              uncertain=len(latin) < 3 or ru_score < 0.18, scores=scores)
    if en_score >= 0.15:
        conf = min(0.95, 0.62 + 0.3 * min(1.0, en_score * 2.5))
        return LanguageResult("english", confidence=conf,
                              uncertain=len(latin) < 3 or en_score < 0.22, scores=scores)

    # Low signal: guess Roman Urdu if any stopword matches, else english-low
    sw = sum(1 for t in lowered if t in ROMAN_STOPWORDS)
    if sw and len(latin) <= 6:
        return LanguageResult("roman_urdu", confidence=0.45, uncertain=True, scores=scores)
    return LanguageResult("english", confidence=0.4, uncertain=True, scores=scores)
