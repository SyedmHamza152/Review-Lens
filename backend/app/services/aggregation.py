"""Aggregation & verdict scoring.

Scoring methodology (documented openly in the report + methodology tab):
- Each analyzed comment contributes: sentiment_score (continuous -1..1,
  Mixed comments carry a signed balance) x sentiment_confidence (weight).
- Overall score 0-100 = 50 + 50 x weighted average.
- Verdict thresholds operate on confidence-weighted sentiment shares and
  require a minimum sample (default 5). Sentiment share is NOT presented as
  a customer rating or a verified quality measure anywhere in the product.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import JobPlatformStatus, Review, SearchJob
from app.nlp.aspect_data import ASPECT_PHRASE_NEG, ASPECT_PHRASE_POS, ASPECTS

MIN_VERDICT = settings.MIN_ANALYZED_FOR_VERDICT
LOW_SAMPLE = settings.LOW_SAMPLE_PLATFORM_THRESHOLD


def _pct(part: int, whole: int) -> float:
    return round(part * 100.0 / whole, 1) if whole else 0.0


def load_reviews(db: Session, job_id: str, include_flagged: bool = False) -> list[Review]:
    q = db.query(Review).filter_by(job_id=job_id)
    if not include_flagged:
        q = q.filter(Review.is_spam == False)  # noqa: E712
    return q.all()


def analyze(db: Session, job_id: str) -> dict:
    """Build the full report payload for a completed job."""
    job = db.query(SearchJob).get(job_id)
    reviews_all = load_reviews(db, job_id, include_flagged=True)
    reviews = [r for r in reviews_all if not r.is_spam and r.relevance >= settings.RELEVANCE_THRESHOLD]
    analyzed = [r for r in reviews if r.sentiment in ("positive", "negative", "neutral", "mixed")]

    counts = Counter(r.sentiment for r in analyzed)
    total = len(analyzed)

    weighted = sum(r.sentiment_score * r.sentiment_confidence for r in analyzed)
    weight_sum = sum(max(r.sentiment_confidence, 0.15) for r in analyzed)
    avg_score = weighted / weight_sum if weight_sum else 0.0
    overall_score = round(max(0.0, min(100.0, 50 + 50 * avg_score)), 1)
    avg_conf = round(sum(r.sentiment_confidence for r in analyzed) / total, 3) if total else 0.0

    verdict_label = _verdict_label(counts, total)

    # ---- aspects ----
    aspect_stats: dict[str, dict] = {}
    for r in analyzed:
        try:
            mentions = json.loads(r.aspects_json or "[]")
        except json.JSONDecodeError:
            mentions = []
        for m in mentions:
            key = m.get("aspect")
            if key not in ASPECTS:
                continue
            st = aspect_stats.setdefault(key, {"mentions": 0, "positive": 0, "negative": 0,
                                               "neutral": 0, "mixed": 0, "polarity": 0.0})
            st["mentions"] += 1
            lbl = m.get("label", "neutral")
            st[lbl] = st.get(lbl, 0) + 1
            st["polarity"] += m.get("polarity", 0.0)
    aspects_out = []
    for key, st in aspect_stats.items():
        aspects_out.append({
            "aspect": key,
            "label": ASPECTS[key]["label"],
            "scope": ASPECTS[key]["scope"],
            "mentions": st["mentions"],
            "positive": st["positive"],
            "negative": st["negative"],
            "neutral": st["neutral"],
            "mixed": st["mixed"],
            "avg_polarity": round(st["polarity"] / st["mentions"], 3) if st["mentions"] else 0.0,
        })
    aspects_out.sort(key=lambda a: (-a["mentions"], a["label"]))

    # ---- advantages / complaints ----
    adv = [(a["label"], a["positive"], ASPECT_PHRASE_POS[a["aspect"]])
           for a in aspects_out if a["positive"] > 0]
    cmp_l = [(a["label"], a["negative"], ASPECT_PHRASE_NEG[a["aspect"]])
             for a in aspects_out if a["negative"] > 0]
    advantages = [{"phrase": p, "count": c, "detail": d} for (p, c, d) in
                  sorted(adv, key=lambda x: -x[1])[:6]]
    complaints = [{"phrase": p, "count": c, "detail": d} for (p, c, d) in
                  sorted(cmp_l, key=lambda x: -x[1])[:6]]

    # ---- platform comparison ----
    statuses = db.query(JobPlatformStatus).filter_by(job_id=job_id).all()
    status_map = {s.platform_key: s for s in statuses}
    by_platform: dict[str, list[Review]] = defaultdict(list)
    for r in analyzed:
        by_platform[r.platform].append(r)
    comparison = []
    for plat, revs in by_platform.items():
        c = Counter(r.sentiment for r in revs)
        n = len(revs)
        ratings = [r.rating for r in revs if r.rating is not None]
        pos_asp = Counter()
        neg_asp = Counter()
        drivers_counter: Counter = Counter()
        for r in revs:
            for m in json.loads(r.aspects_json or "[]"):
                if m.get("label") == "positive":
                    pos_asp[ASPECTS.get(m["aspect"], {}).get("label", m["aspect"])] += 1
                elif m.get("label") == "negative":
                    neg_asp[ASPECTS.get(m["aspect"], {}).get("label", m["aspect"])] += 1
            try:
                for d in json.loads(r.drivers_json or "[]"):
                    if isinstance(d, str):
                        drivers_counter[d] += 1
            except json.JSONDecodeError:
                pass
        st = status_map.get(plat)
        comparison.append({
            "platform": plat,
            "platform_name": (st.platform_name if st else plat.title()),
            "total": n,
            "positive_pct": _pct(c["positive"], n),
            "negative_pct": _pct(c["negative"], n),
            "neutral_pct": _pct(c["neutral"], n),
            "mixed_pct": _pct(c["mixed"], n),
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "low_sample": n < LOW_SAMPLE,
            "is_sample": bool(st.is_sample if st else True),
            "rank_by_positive": None,
            "top_positive_aspect": pos_asp.most_common(1)[0][0] if pos_asp else None,
            "top_complaint_aspect": neg_asp.most_common(1)[0][0] if neg_asp else None,
            "top_drivers": [d for d, _ in drivers_counter.most_common(5)],
            "status": st.status if st else "success",
            "message": st.message if st else "",
            "collected_at": st.collected_at if st else None,
        })
    # rank by positive pct only where sample size is meaningful
    rankable = sorted([c for c in comparison if not c["low_sample"]],
                      key=lambda c: (-c["positive_pct"], -c["total"]))
    for i, c in enumerate(rankable, 1):
        c["rank_by_positive"] = i
    comparison.sort(key=lambda c: (-(not c["low_sample"]), -c["positive_pct"], -c["total"]))

    # ---- languages ----
    lang_counts: dict[str, Counter] = defaultdict(Counter)
    for r in analyzed:
        lang_counts[r.language][r.sentiment] += 1
    languages = []
    for lang, c in sorted(lang_counts.items(), key=lambda x: -sum(x[1].values())):
        n = sum(c.values())
        languages.append({"language": lang, "count": n, "pct": _pct(n, total),
                          "positive": c["positive"], "negative": c["negative"],
                          "neutral": c["neutral"], "mixed": c["mixed"]})

    # ---- trends (weekly) ----
    trend_groups: dict[str, list[float]] = defaultdict(list)
    for r in analyzed:
        if r.review_date is not None:
            d = r.review_date
            week = d.strftime("%G-W%V")
            trend_groups[week].append(r.sentiment_score)
    trends = [{"period": w, "score": round(sum(v) / len(v), 3), "count": len(v)}
              for w, v in sorted(trend_groups.items())]

    # ---- totals ----
    spam_count = sum(1 for r in reviews_all if r.is_spam)
    dup_saved = getattr(job, "dup_count", None)
    totals = {
        "collected": len(reviews_all),
        "analyzed": total,
        "spam_filtered": spam_count,
        "low_relevance_excluded": len(reviews_all) - len(reviews) - spam_count,
        "platforms_with_data": len(by_platform),
        "platforms_requested": len(statuses),
        "avg_confidence": avg_conf,
    }

    distribution = [
        {"label": "positive", "count": counts["positive"], "pct": _pct(counts["positive"], total)},
        {"label": "negative", "count": counts["negative"], "pct": _pct(counts["negative"], total)},
        {"label": "neutral", "count": counts["neutral"], "pct": _pct(counts["neutral"], total)},
        {"label": "mixed", "count": counts["mixed"], "pct": _pct(counts["mixed"], total)},
    ]

    verdict = {
        "score": overall_score,
        "label": verdict_label,
        "positive_pct": _pct(counts["positive"], total),
        "negative_pct": _pct(counts["negative"], total),
        "neutral_pct": _pct(counts["neutral"], total),
        "mixed_pct": _pct(counts["mixed"], total),
        "avg_confidence": avg_conf,
        "methodology_note": (
            "Score = 50 + 50 x confidence-weighted average of comment sentiment "
            "(-1..1). Sentiment share reflects the collected sample only and is "
            "NOT a customer rating or a verified measure of product quality."
        ),
    }

    summary = build_summary(job.product_name, verdict, counts, total,
                            aspects_out, comparison, languages, by_platform)

    return {
        "job": {
            "id": job.id,
            "product_name": job.product_name,
            "description": job.description,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "data_mode": job.data_mode,
        },
        "platform_statuses": [
            {
                "platform": s.platform_key,
                "platform_name": s.platform_name,
                "status": s.status,
                "message": s.message,
                "items_collected": s.items_collected,
                "is_sample": s.is_sample,
                "requires_credentials": json.loads(s.requires_credentials or "[]"),
                "collected_at": s.collected_at,
            } for s in statuses
        ],
        "totals": totals,
        "verdict": verdict,
        "distribution": distribution,
        "summary": summary,
        "aspects": aspects_out,
        "advantages": advantages,
        "complaints": complaints,
        "comparison": comparison,
        "languages": languages,
        "trends": trends,
        "methodology": {
            "nlp_pipeline": settings.NLP_PIPELINE_VERSION,
            "scoring": verdict["methodology_note"],
            "mixed_rule": ("A comment is Mixed when clauses carry opposing "
                           "non-negligible sentiment (e.g. praise + complaint)."),
            "min_sample_for_verdict": MIN_VERDICT,
            "low_sample_platform_threshold": LOW_SAMPLE,
            "confidence": ("Every comment carries sentiment/language confidence; "
                           "low-confidence predictions are flagged uncertain."),
            "disclaimers": [
                "Sentiment percentages describe the collected sample, not the market.",
                "Platform comparison must consider sample size and audience differences.",
                "Sample-data mode uses synthetic comments for demonstration only.",
                "A higher positive percentage does not make a platform 'better'.",
            ],
        },
    }


def _verdict_label(counts: Counter, total: int) -> str:
    if total < MIN_VERDICT:
        return "Insufficient Data"
    pos = counts["positive"] / total * 100
    neg = counts["negative"] / total * 100
    mixed = counts["mixed"] / total * 100
    if pos >= 55 and neg < 20:
        return "Generally Positive"
    if pos >= 40 and neg < 30 and mixed < 30:
        return "Mostly Positive with Some Concerns"
    if neg >= 50 and pos < 20:
        return "Generally Negative"
    if neg >= 35:
        return "Mostly Negative with Some Positives"
    if mixed >= 30 or (25 <= pos < 45 and neg >= 20):
        return "Mixed Feedback"
    if pos >= 40:
        return "Mostly Positive with Some Concerns"
    return "Mixed Feedback"


def build_summary(product_name: str, verdict: dict, counts: Counter, total: int,
                  aspects: list[dict], comparison: list[dict],
                  languages: list[dict], by_platform: dict) -> str:
    """Deterministic, evidence-based summary (no fabricated claims)."""
    if total < MIN_VERDICT:
        return (f"Insufficient usable data was collected for {product_name} "
                f"({total} analyzed comments), so no reliable verdict can be "
                "made. Try enabling more platforms or provide API credentials.")
    top_aspects = [a for a in aspects if a["mentions"] >= 2][:3]
    main_pos = [a["label"] for a in top_aspects if a["positive"] > a["negative"]]
    main_neg = [a["label"] for a in top_aspects if a["negative"] > a["positive"]]
    best_platform = next((c for c in comparison if not c["low_sample"]), None)
    parts = [
        f"{product_name} receives a {verdict['label'].lower()} verdict "
        f"(score {verdict['score']}/100) from {total} analyzed comments across "
        f"{len(by_platform)} platform(s): {verdict['positive_pct']}% positive, "
        f"{verdict['negative_pct']}% negative, {verdict['mixed_pct']}% mixed.",
    ]
    if main_pos:
        parts.append("Customers most often praise " + ", ".join(main_pos) + ".")
    if main_neg:
        parts.append("Recurring complaints mention " + ", ".join(main_neg) + ".")
    if counts["mixed"] >= max(1, int(total * 0.15)):
        parts.append(
            "A notable share of comments are mixed (praise + complaints in the same "
            "review), which means experiences vary notably across buyers.")
    if best_platform:
        parts.append(
            f"Within this sample, {best_platform['platform_name']} shows the highest "
            f"positive share ({best_platform['positive_pct']}% of {best_platform['total']} "
            "comments); differences reflect sample size and audience, not platform quality.")
    lang_names = ", ".join(l["language"] for l in languages[:3])
    parts.append(f"Feedback languages detected: {lang_names} - opinions are consistent "
                 "with the per-language breakdown shown below.")
    return " ".join(parts)
