"""Context-aware multilingual sentiment engine.

Pipeline: clauses -> phrase/unigram lexicon matching -> negation window ->
intensifiers/diminishers -> clause polarity -> comment label (with Mixed
detection via opposing clauses) -> confidence + uncertainty flags.

Labels: positive | negative | neutral | mixed      Score range: -1..+1
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.nlp.lexicons_en import (
    EN_ADVERSATIVES, EN_DIMINISHERS, EN_INTENSIFIERS, EN_NEGATORS,
    EN_NEGATIVE, EN_PHRASES, EN_POSITIVE,
)
from app.nlp.lexicons_roman import (
    ROMAN_ADVERSATIVES, ROMAN_DIMINISHERS, ROMAN_INTENSIFIERS, ROMAN_NEGATORS,
    ROMAN_NEGATIVE, ROMAN_PHRASES, ROMAN_POSITIVE,
)
from app.nlp.lexicons_urdu import (
    URDU_ADVERSATIVES, URDU_DIMINISHERS, URDU_INTENSIFIERS, URDU_NEGATORS,
    URDU_NEGATIVE, URDU_PHRASES, URDU_POSITIVE,
)
from app.nlp.roman_urdu import normalize_text, split_clauses, tokenize

# ---------------------------------------------------------------------------
# Merged lookups (English + Roman Urdu + Urdu script share one space; Urdu
# script tokens never collide with Latin tokens)
# ---------------------------------------------------------------------------
PHRASES: dict[str, float] = {}
for d in (EN_PHRASES, ROMAN_PHRASES, URDU_PHRASES):
    for k, v in d.items():
        PHRASES.setdefault(" ".join(k.split()), v)

UNIGRAMS: dict[str, float] = {}
for d in (EN_POSITIVE, EN_NEGATIVE, ROMAN_POSITIVE, ROMAN_NEGATIVE, URDU_POSITIVE, URDU_NEGATIVE):
    for k, v in d.items():
        if " " not in k:
            UNIGRAMS.setdefault(k.lower(), v)

NEGATORS = EN_NEGATORS | ROMAN_NEGATORS | URDU_NEGATORS
INTENSIFIERS: dict[str, float] = {}
for d in (EN_INTENSIFIERS, ROMAN_INTENSIFIERS, URDU_INTENSIFIERS):
    for k, v in d.items():
        INTENSIFIERS.setdefault(k.lower(), v)
DIMINISHERS: dict[str, float] = {}
for d in (EN_DIMINISHERS, ROMAN_DIMINISHERS, URDU_DIMINISHERS):
    for k, v in d.items():
        DIMINISHERS.setdefault(k.lower(), v)
ADVERSATIVES = EN_ADVERSATIVES | ROMAN_ADVERSATIVES | URDU_ADVERSATIVES

SARCASM_MARKERS = {
    "wah", "wah wah", "shabash", "kya baat", "great going", "thanks a lot",
    "as expected", "wow", "bravo", "zabardast service", "kamaal hai",
    "lovely", "amazing service",
}

MAX_NEG_WINDOW = 3


@dataclass
class Span:
    text: str
    score: float
    negated: bool
    start: int
    end: int


@dataclass
class ClauseResult:
    text: str
    polarity: float
    label: str
    drivers: list[str] = field(default_factory=list)


@dataclass
class SentimentResult:
    label: str
    score: float
    confidence: float
    uncertain: bool
    sarcasm_suspect: bool
    clauses: list[ClauseResult] = field(default_factory=list)
    drivers: list[str] = field(default_factory=list)


def _match_spans(tokens: list[str]) -> list[Span]:
    """Greedy left-to-right matching: 3-gram, 2-gram, then 1-gram."""
    spans: list[Span] = []
    i, n = 0, len(tokens)
    while i < n:
        matched = None
        for size in (3, 2):
            if i + size <= n:
                phrase = " ".join(tokens[i:i + size]).lower()
                if phrase in PHRASES:
                    matched = Span(phrase, PHRASES[phrase], False, i, i + size)
                    break
        if matched is None:
            w = tokens[i].lower()
            if w in UNIGRAMS:
                matched = Span(w, UNIGRAMS[w], False, i, i + 1)
        if matched:
            # negation window: before and after the matched span
            lo, hi = max(0, matched.start - MAX_NEG_WINDOW), min(n, matched.end + MAX_NEG_WINDOW)
            window = [tokens[j].lower() for j in range(lo, matched.start)] + \
                     [tokens[j].lower() for j in range(matched.end, hi)]
            if any(w in NEGATORS for w in window):
                matched.score *= -0.85
                matched.negated = True
            # intensifier / diminisher adjacency (within 2 tokens before)
            pre = [tokens[j].lower() for j in range(max(0, matched.start - 2), matched.start)]
            mult = 1.0
            for w in pre:
                if w in INTENSIFIERS:
                    mult = max(mult, INTENSIFIERS[w])
                elif w in DIMINISHERS:
                    mult = min(mult, DIMINISHERS[w])
            matched.score *= mult
            spans.append(matched)
            i = matched.end
        else:
            i += 1
    return spans


def _clause_result(text: str) -> ClauseResult:
    tokens = tokenize(text) if not re.search(r"[\u0600-\u06FF]", text) else text.split()
    tokens = [t for t in tokens if t not in {".", "!", "?", ",", "،", "؛", "؟"}]
    if not tokens:
        return ClauseResult(text, 0.0, "neutral", [])
    spans = _match_spans(tokens)
    raw = sum(s.score for s in spans)
    excl = 1.0
    if re.search(r"[!！\uFF01]", text):
        excl = 1.08
    polarity = max(-1.0, min(1.0, (raw / 2.2) * excl))
    if polarity > 0.2:
        label = "positive"
    elif polarity < -0.2:
        label = "negative"
    else:
        label = "neutral"
    drivers = [s.text for s in spans if abs(s.score) >= 0.5]
    return ClauseResult(text, polarity, label, drivers)


def _sarcasm_check(clauses: list[ClauseResult], tokens: list[str]) -> bool:
    """Sarcasm suspicion: enthusiastic marker + at least one negative clause.

    In Pakistani review language, markers like 'wah', 'great going',
    'thanks a lot' combined with complaints are overwhelmingly sarcastic.
    """
    joined = " ".join(tokens).lower()
    marker_hit = any(m in joined for m in SARCASM_MARKERS)
    if not marker_hit:
        return False
    neg = sum(1 for c in clauses if c.label == "negative")
    return neg >= 1


def analyze_sentiment(text: str) -> SentimentResult:
    """Full comment-level analysis. `text` should be the ORIGINAL comment;
    normalization happens inside (variants folded, originals preserved)."""
    normalized = normalize_text(text)
    clause_texts = split_clauses(normalized) or [normalized]
    clause_results = [_clause_result(c) for c in clause_texts]

    total_w = sum(len(c.text.split()) for c in clause_results) or 1
    weighted = sum(c.polarity * max(1, len(c.text.split())) for c in clause_results) / total_w
    weighted = max(-1.0, min(1.0, weighted))

    labels = [c.label for c in clause_results]
    has_pos_clause = any(c.label == "positive" and c.polarity >= 0.2 for c in clause_results)
    has_neg_clause = any(c.label == "negative" and c.polarity <= -0.2 for c in clause_results)

    tokens = normalized.split()
    sarcasm = _sarcasm_check(clause_results, tokens)

    # Score from NON-NEUTRAL clauses only: a long factual clause must not
    # dilute a strong opinion in another clause of the same comment.
    voiced = [c for c in clause_results if c.label != "neutral"]
    if not voiced:
        label, score = "neutral", weighted
    else:
        v_total = sum(max(1, len(c.text.split())) for c in voiced)
        voiced_avg = max(-1.0, min(1.0,
            sum(c.polarity * max(1, len(c.text.split())) for c in voiced) / v_total))
        pos_v = any(c.label == "positive" for c in voiced)
        neg_v = any(c.label == "negative" for c in voiced)
        if pos_v and neg_v:
            label, score = "mixed", voiced_avg
        elif voiced_avg > 0.2:
            label, score = "positive", voiced_avg
        elif voiced_avg < -0.2:
            label, score = "negative", voiced_avg
        else:
            label, score = "neutral", voiced_avg

    # sarcasm override: enthusiastic opener + negative substance -> negative
    if sarcasm and label in ("mixed", "positive"):
        neg_p = [c.polarity for c in clause_results if c.polarity < 0]
        if neg_p:
            label, score = "negative", min(-0.2, sum(neg_p) / len(neg_p))

    evidence = sum(len(c.drivers) for c in clause_results)
    any_phrase = any(" " in d for c in clause_results for d in c.drivers)
    confidence = 0.30 + 0.14 * min(evidence, 3) + 0.30 * abs(score)
    if any_phrase:
        confidence += 0.08
    confidence = min(0.95, confidence)
    if sarcasm:
        confidence *= 0.6
    if len(tokens) < 4:
        confidence *= 0.8
    confidence = max(0.22, min(0.95, confidence))

    drivers = sorted({d for c in clause_results for d in c.drivers})
    return SentimentResult(
        label=label, score=round(score, 4),
        confidence=round(confidence, 3),
        uncertain=confidence < 0.45,
        sarcasm_suspect=sarcasm,
        clauses=clause_results, drivers=drivers,
    )
