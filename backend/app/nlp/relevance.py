"""Relevance scoring + spam/promotion detection."""
from __future__ import annotations

import hashlib
import re

_URL_RE = re.compile(r"https?://\S+|www\.\S+|t\.me/\S+|wa\.me/\S+")
_PHONE_RE = re.compile(r"(\+92|0)?3\d{2}[- ]?\d{7}")
_PROMO_WORDS = {
    "coupon", "coupons", "discount", "sale", "offer offer", "buy now",
    "click", "link", "whatsapp", "whatsaap", "subscribe", "free gift",
    "cashback", "promo", "deal deal", "dm me", "inbox me", "order now",
}


def product_tokens(product_name: str, description: str | None) -> set[str]:
    tokens: set[str] = set()
    for chunk in (product_name or "").lower().replace("-", " ").split():
        if len(chunk) >= 2:
            tokens.add(chunk)
    if description:
        for chunk in description.lower().replace("-", " ").split():
            if len(chunk) >= 3:
                tokens.add(chunk)
    return tokens


def relevance_score(text: str, tokens: set[str]) -> float:
    """0..1 token overlap between the comment and the product identity tokens.

    Marketplace reviews scraped from a product page are inherently relevant,
    so the threshold is low; social mentions need real overlap.
    """
    if not tokens:
        return 0.6
    words = re.findall(r"[a-z\u0600-\u06FF0-9]+", text.lower())
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in tokens)
    return min(1.0, hits / max(3, len(tokens) ** 0.5))


def spam_signals(text: str) -> tuple[bool, str]:
    """Heuristic spam/promotion detection. Returns (is_spam, reason)."""
    t = text.strip()
    if len(t.split()) < 3:
        return True, "too_short"
    if _URL_RE.search(t):
        return True, "contains_link"
    if _PHONE_RE.search(t):
        return True, "contains_phone"
    lower = t.lower()
    promo_hits = sum(1 for w in _PROMO_WORDS if w in lower)
    if promo_hits >= 2:
        return True, "promotional"
    letters = [c for c in t if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7 and len(letters) > 12:
        return True, "all_caps"
    return False, ""


def dedup_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.lower().encode("utf-8")).hexdigest()[:32]


def fuzzy_hash(normalized_text: str) -> str:
    """Coarse hash of the first 100 chars for near-duplicate catching."""
    return hashlib.sha256(normalized_text.lower()[:100].encode("utf-8")).hexdigest()[:32]
