"""Aspect-Based Sentiment Analysis (ABSA).

Assigns per-aspect sentiment using the polarity of the clause in which the
aspect keywords appear, and separates product complaints from
seller/marketplace complaints.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.nlp.aspect_data import ASPECTS
from app.nlp.sentiment import SentimentResult


@dataclass
class AspectMention:
    aspect: str
    label: str          # positive|negative|neutral|mixed
    polarity: float
    confidence: float


def _clause_has_aspect(clause_text: str, aspect_key: str) -> bool:
    words = set(clause_text.lower().split())
    for kw in ASPECTS[aspect_key]["keywords"]:
        if " " in kw:
            if kw in clause_text.lower():
                return True
        elif kw in words:
            return True
    return False


def extract_aspects(sentiment: SentimentResult) -> list[AspectMention]:
    """Match aspects within each clause; keep the strongest mention per aspect."""
    seen: dict[str, AspectMention] = {}

    for clause in sentiment.clauses:
        for aspect_key in ASPECTS:
            if not _clause_has_aspect(clause.text, aspect_key):
                continue
            pol = clause.polarity
            if pol > 0.2:
                lbl = "positive"
            elif pol < -0.2:
                lbl = "negative"
            else:
                lbl = "neutral"
            conf = min(0.95, 0.35 + 0.3 * abs(pol) + (0.2 if clause.drivers else 0))
            mention = AspectMention(aspect_key, lbl, round(pol, 3), round(conf, 3))
            prev = seen.get(aspect_key)
            if prev is None:
                seen[aspect_key] = mention
            elif lbl != "neutral" and (prev.label == "neutral" or abs(pol) > abs(prev.polarity)):
                seen[aspect_key] = mention

    return list(seen.values())


def complaint_scope(mentions: list[AspectMention]) -> str:
    """Classify complaint target: product / seller / marketplace / both / none."""
    neg_aspects = [m for m in mentions if m.label == "negative"]
    if not neg_aspects:
        return "none"
    scopes = {ASPECTS[m.aspect]["scope"] for m in neg_aspects}
    if scopes == {"product"}:
        return "product"
    if scopes == {"seller"}:
        return "seller"
    if scopes == {"marketplace"}:
        return "marketplace"
    return "both"
