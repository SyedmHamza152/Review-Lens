"""Smoke-test the three live collectors with a real product query."""
import sys
sys.path.insert(0, "/home/z/my-project/backend")

from app.integrations.live_sources import (
    collect_daraz_catalog, collect_reddit, HackerNewsAdapter,
)

PRODUCT = "AirPods Pro"

print("=== Reddit via Arctic-Shift ===")
res = collect_reddit(PRODUCT, None, max_items=30)
print("status:", res.status.value, "| items:", len(res.items), "| calls used:", 16 - res.message.count(""))
for it in res.items[:5]:
    print(f"- [{it.external_id[:12]}] {(it.text or '')[:110]!r} | {it.review_date}")

print("\n=== Hacker News via Algolia ===")
res = HackerNewsAdapter().search(PRODUCT, None, max_items=25)
print("status:", res.status.value, "| items:", len(res.items))
for it in res.items[:5]:
    print(f"- {(it.text or '')[:110]!r}")

print("\n=== Daraz catalog ===")
listings, err = collect_daraz_catalog(PRODUCT, 40)
print("error:", err or "none", "| listings:", len(listings))
for l in listings[:5]:
    print(f"- {l['name'][:60]!r} | rating {l['rating']} | {l['review_count']} reviews | {l['price_text']}")
