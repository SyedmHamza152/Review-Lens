"""Roman Urdu text normalization.

The ORIGINAL text is never modified. This module only builds the
`text_normalized` copy used for analysis: lowercasing, punctuation cleanup,
repeated-letter collapse, spelling-variant folding, and English slang mapping.
"""
from __future__ import annotations

import re
import unicodedata

from app.nlp.lexicons_roman import RU_VARIANT_MAP

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_REPEAT_RE = re.compile(r"(.)\1{2,}")  # 3+ same letters -> 1
_NONWORD_RE = re.compile(r"[^\w\s\u0600-\u06FF\u0750-\u077F!,.?\u060C\u061B\u061F]")
_PUNCT_KEEP = {".", "!", "?", ",", "،", "؛", "؟"}


def _collapse_repeats(token: str) -> str:
    return _REPEAT_RE.sub(r"\1", token)


def tokenize(text: str) -> list[str]:
    """Split into word tokens; sentence punctuation is kept as its own token."""
    text = _URL_RE.sub(" ", text)
    text = unicodedata.normalize("NFC", text)
    raw = text.split()
    tokens: list[str] = []
    for chunk in raw:
        chunk = _NONWORD_RE.sub(" ", chunk).strip()
        if not chunk:
            continue
        # separate trailing sentence punctuation:  "acha." -> ["acha", "."]
        while chunk and chunk[-1] in _PUNCT_KEEP:
            tokens.append(chunk[:-1])
            tokens.append(chunk[-1])
            chunk = ""
        if chunk:
            tokens.append(chunk)
    return [t for t in tokens if t]


def normalize_token(token: str) -> str:
    """Fold spelling variants for Latin-script tokens (Urdu script untouched)."""
    t = token.lower()
    t = _collapse_repeats(t)
    t = t.strip(".,!?;:\"'`~@#$%^&*()[]{}<>/\\|-_=+")
    if not t:
        return ""
    if re.search(r"[\u0600-\u06FF]", t):
        return t  # keep Urdu script as-is
    return RU_VARIANT_MAP.get(t, t)


def normalize_text(text: str) -> str:
    """Produce the analysis text: tokenized + variant-folded, punctuation kept."""
    tokens = tokenize(text)
    out: list[str] = []
    for tok in tokens:
        if tok in _PUNCT_KEEP:
            out.append(tok)
        else:
            n = normalize_token(tok)
            if n:
                out.append(n)
    return " ".join(out)


def token_stream(text_normalized: str) -> list[str]:
    """Word tokens (punctuation removed) for lexicon matching."""
    return [t for t in text_normalized.split() if t not in _PUNCT_KEEP and t]


def split_clauses(text_normalized: str) -> list[str]:
    """Split into clauses on adversatives and sentence boundaries.

    Adversatives (but/lekin/magar/لیکن...) become their own boundary so that
    opposing opinions inside one comment can be detected (Mixed label).
    """
    words = text_normalized.split()
    clauses: list[str] = []
    current: list[str] = []

    adversatives = {"but", "however", "lekin", "magar", "jabke", "halanke",
                    "werna", "warna", "لیکن", "مگر", "البتہ", "تاہم", "جبکہ"}

    for w in words:
        if w in {".", "!", "?", "،", ",", "؛", "؟"}:
            if current:
                clauses.append(" ".join(current))
                current = []
        elif w.lower() in adversatives:
            if current:
                clauses.append(" ".join(current))
            current = []
        else:
            current.append(w)
    if current:
        clauses.append(" ".join(current))
    return [c for c in (c.strip() for c in clauses) if c]
