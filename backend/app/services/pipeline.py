"""Review processing pipeline.

For every collected item:
  1. language detection (EN / Urdu / Roman Urdu / mixed, with confidence)
  2. relevance scoring vs product identity tokens
  3. spam / promotional filtering
  4. deduplication (external id + normalized-text hash per job+platform)
  5. sentiment analysis (context, negation, mixed detection)
  6. aspect-based sentiment + complaint scope
  7. optional English gloss translation
  8. persistence with strict layer separation (original / normalized / translation)
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.base import AdapterResult, ReviewItem
from app.models import Review
from app.nlp import relevance as rel
from app.nlp.aspects import extract_aspects
from app.nlp.language import detect_language
from app.nlp.roman_urdu import normalize_text
from app.nlp.sentiment import analyze_sentiment
from app.nlp.translate import gloss_translate


def _to_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value


def process_review_item(db: Session, job_id: str, platform: str,
                        item: ReviewItem, product_tokens: set[str],
                        data_source: str) -> tuple[bool, str]:
    """Analyze + store one item. Returns (stored, skip_reason)."""
    text = (item.text or "").strip()
    if not text:
        return False, "empty"

    # --- dedup: external id ---
    ext = (item.external_id or "")[:240]
    if ext:
        exists = db.query(Review.id).filter_by(
            job_id=job_id, platform=platform, external_id=ext).first()
        if exists:
            return False, "duplicate_external_id"

    lang_res = detect_language(text)
    normalized = normalize_text(text)

    # --- dedup: normalized text hash per job+platform ---
    dhash = rel.dedup_hash(f"{platform}|{normalized}")
    exists = db.query(Review.id).filter_by(job_id=job_id, dedup_hash=dhash).first()
    if exists:
        return False, "duplicate_text"

    is_spam, spam_reason = rel.spam_signals(text)
    relevance = item.relevance_hint if item.relevance_hint is not None \
        else rel.relevance_score(normalized, product_tokens)

    sent = analyze_sentiment(text)
    aspects = extract_aspects(sent)
    scope = "none"
    from app.nlp.aspects import complaint_scope as _scope
    scope = _scope(aspects)

    translation = gloss_translate(text, lang_res.language) if lang_res.language != "english" else None

    row = Review(
        job_id=job_id,
        platform=platform,
        external_id=ext,
        dedup_hash=dhash,
        text_original=text,
        text_normalized=normalized,
        translation=translation,
        language=lang_res.language,
        language_confidence=lang_res.confidence,
        language_uncertain=lang_res.uncertain,
        sentiment=sent.label,
        sentiment_score=sent.score,
        sentiment_confidence=sent.confidence,
        sentiment_uncertain=sent.uncertain,
        sarcasm_suspect=sent.sarcasm_suspect,
        complaint_scope=scope,
        relevance=round(relevance, 3),
        is_spam=is_spam,
        rating=item.rating,
        review_date=_to_dt(item.review_date),
        variant=item.variant,
        author=item.author,
        source_url=item.source_url,
        aspects_json=json.dumps(
            [{"aspect": m.aspect, "label": m.label, "polarity": m.polarity,
              "confidence": m.confidence} for m in aspects]),
        drivers_json=json.dumps(sent.drivers[:12]),
        data_source=data_source,
    )
    # stash spam reason inside drivers tail marker is avoided; keep as attribute only in logs
    if is_spam:
        row.drivers_json = json.dumps({"spam_reason": spam_reason})
    db.add(row)
    db.flush()
    return True, "stored"


def process_adapter_result(db: Session, job_id: str, result: AdapterResult,
                           product_tokens: set[str]) -> dict:
    """Persist all items of one adapter result; returns processing counters."""
    stored = duplicates = spam = low_rel = 0
    for item in result.items:
        ok, reason = process_review_item(db, job_id, result.platform, item,
                                         product_tokens, result.data_source)
        if ok:
            stored += 1
        elif reason == "duplicate_text" or reason == "duplicate_external_id":
            duplicates += 1
        # spam/low-relevance still stored (flagged) for transparency
    db.commit()

    # ---- rating aggregates (e.g. Daraz storefront listings) ----
    listings_stored = 0
    if result.aggregate_items:
        from app.models import PlatformListing
        for agg in result.aggregate_items:
            ext = str(agg.get("external_id", ""))[:240]
            if not ext or not str(agg.get("name", "")).strip():
                continue
            exists = db.query(PlatformListing.id).filter_by(
                job_id=job_id, platform=result.platform, external_id=ext).first()
            if exists:
                continue
            db.add(PlatformListing(
                job_id=job_id, platform=result.platform, external_id=ext,
                name=str(agg.get("name", ""))[:280],
                rating=agg.get("rating"),
                review_count=int(agg.get("review_count") or 0),
                price_text=agg.get("price_text"),
                seller=agg.get("seller"),
                brand=agg.get("brand"),
                location=agg.get("location"),
                sold_count_text=agg.get("sold_count_text"),
                source_url=agg.get("url"),
                data_source=result.data_source,
            ))
            listings_stored += 1
        db.commit()

    return {
        "platform": result.platform,
        "collected": len(result.items),
        "stored": stored,
        "duplicates": duplicates,
        "listings_stored": listings_stored,
        "relevance_threshold": settings.RELEVANCE_THRESHOLD,
    }
