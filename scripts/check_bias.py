"""Sanity check: optimizer must produce DIFFERENT allocations for different
products / objectives / audiences — no structural in-stream bias."""
import sys

sys.path.insert(0, "/home/z/my-project/backend")

from app.optimization.coldstart import AOV_BY_BAND, FORMAT_PRIORS
from app.optimization.engine import optimize_budget, score_from_prior
from app.services.knowledge import CATEGORY_PROFILES, FORMAT_OBJECTIVE_FIT, classify_category

OBJECTIVES = ["Brand Awareness", "Video Views", "Website Traffic", "Leads", "Sales / Conversions"]


def scores_for(category_key: str, objective: str, young_share: float, research_shorts_share: float | None):
    profile = next(p for p in CATEGORY_PROFILES if p.key == category_key)
    out = []
    for key in ("in_stream", "shorts", "in_feed"):
        s = score_from_prior(FORMAT_PRIORS[key])
        s.aov = AOV_BY_BAND[profile.avg_order_value_band]
        s.sample_size = 250_000
        s.confidence = 0.6
        # audience fit (mirrors optimizer_service)
        if key == "shorts":
            s.audience_fit = 0.75 + 0.55 * young_share
        elif key == "in_stream":
            s.audience_fit = 1.20 - 0.30 * young_share
        else:
            s.audience_fit = 1.05 - 0.10 * young_share
        s.objective_fit = FORMAT_OBJECTIVE_FIT[key].get(objective, 1.0)
        s.category_fit = profile.format_affinity.get(key, 1.0)
        # research fit (mirrors optimizer_service.research_fit_for)
        if research_shorts_share is not None:
            raw = {
                "shorts": 0.92 + 0.40 * research_shorts_share,
                "in_stream": 1.06 - 0.30 * research_shorts_share,
                "in_feed": 1.02 - 0.10 * research_shorts_share,
            }
            s.research_fit = raw[key] / (sum(raw.values()) / 3.0)
        out.append(s)
    return out


def winner(category_key, objective, young_share=0.65, research=None):
    res = optimize_budget(100_000, scores_for(category_key, objective, young_share, research))
    top = res.allocations[0]
    shares = {a.format_key: round(a.share * 100) for a in res.allocations}
    return top.format_key, shares


print("=== Winners per category x objective (young audience 0.65, no research) ===")
cat_summary = {}
for cat in ["sports_equipment", "fashion_apparel", "food_beverage", "education_courses",
            "software_app", "jewelry_accessories", "electronics", "home_kitchen"]:
    wins = []
    for obj in OBJECTIVES:
        w, shares = winner(cat, obj)
        wins.append(f"{obj.split(' /')[0]}:{w}({shares})")
    cat_summary[cat] = wins
    print(f"\n{cat}:")
    for w in wins:
        print("   ", w)

print("\n=== Older audience (young 0.15) shifts ===")
for cat in ["sports_equipment", "education_courses"]:
    for obj in OBJECTIVES:
        w, shares = winner(cat, obj, young_share=0.15)
        print(f"   {cat} | {obj}: {w} {shares}")

print("\n=== LIVE research shorts-heavy niche (shorts_share=0.5) ===")
for cat in ["sports_equipment", "software_app"]:
    for obj in OBJECTIVES:
        w, shares = winner(cat, obj, research=0.5)
        print(f"   {cat} | {obj}: {w} {shares}")

winners_set = {wins[0].split(":")[1].split("(")[0] for cat in cat_summary.values() for wins in [cat]}
all_top = [w.split(":")[1].split("(")[0] for cat in cat_summary.values() for w in cat]
distinct = set(all_top)
print(f"\nDistinct winners across the matrix: {distinct}")
assert distinct == {"in_stream", "shorts", "in_feed"}, "BIAS REMAINS: not all formats ever win!"
print("OK: no structural bias — every format wins somewhere.")
