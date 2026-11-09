"""Product knowledge base for the rule-based intelligence engine.

These are *explicit, documented assumptions* (heuristic priors) — not verified
market data. They power:
  * product category classification,
  * audience inference,
  * marketing objective selection,
  * cold-start format priors for the budget optimizer.

Every output derived from this file is labeled as inference in the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CategoryProfile:
    key: str
    label: str
    keywords: list[str]
    intent: str  # high_intent | research | impulse | seasonal | subscription
    avg_order_value_band: str  # low | medium | high | premium
    age_weights: dict[str, float]  # weight per age band
    gender_skew: dict[str, float]  # female/male/unknown weights
    interests: list[str]
    audience_segments: list[dict] = field(default_factory=list)
    format_affinity: dict[str, float] = field(default_factory=lambda: {"in_stream": 1.0, "shorts": 1.0, "in_feed": 1.0})
    objective_bias: str = "Sales / Conversions"
    notes: str = ""


def _seg(key: str, label: str, ages: list[str], interests: list[str], note: str) -> dict:
    return {"key": key, "label": label, "age_bands": ages, "interests": interests, "note": note}


CATEGORY_PROFILES: list[CategoryProfile] = [
    CategoryProfile(
        key="sports_equipment",
        label="Sports & Outdoor Equipment",
        keywords=["cricket", "bat", "ball", "football", "soccer", "racket", "tennis",
                  "hockey", "gloves", "kit", "willow", "stumps", "pads", "helmet",
                  "sports", "gym equipment", "dumbbell", "bicycle", "skating"],
        intent="research",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.32, "25-34": 0.38, "35-44": 0.20, "45-54": 0.07, "55+": 0.03},
        gender_skew={"female": 0.25, "male": 0.65, "unknown": 0.10},
        interests=["Cricket", "Sports highlights", "Fitness", "Outdoor activities", "Team sports", "Sports gear reviews"],
        audience_segments=[
            _seg("club_players", "Club & academy players", ["18-24", "25-34"],
                 ["Cricket coaching", "Equipment reviews", "Match highlights"],
                 "Actively playing; research gear quality and willow grade before buying."),
            _seg("parents_buying", "Parents of young players", ["35-44", "45-54"],
                 ["Youth sports", "School sports", "Durability reviews"],
                 "Buy for children; value durability and safety certifications."),
        ],
        format_affinity={"in_stream": 1.22, "shorts": 1.10, "in_feed": 0.85},
        objective_bias="Sales / Conversions",
        notes="Equipment buyers watch demo/review videos before purchase; long-form in-stream demos and Shorts skill clips both perform.",
    ),
    CategoryProfile(
        key="electronics",
        label="Consumer Electronics",
        keywords=["phone", "mobile", "laptop", "earbuds", "headphone", "smartwatch",
                  "camera", "charger", "power bank", "tablet", "tv", "speaker",
                  "console", "gaming", "electronic", "processor", "led"],
        intent="research",
        avg_order_value_band="high",
        age_weights={"18-24": 0.34, "25-34": 0.36, "35-44": 0.19, "45-54": 0.08, "55+": 0.03},
        gender_skew={"female": 0.30, "male": 0.60, "unknown": 0.10},
        interests=["Tech reviews", "Gadgets", "Unboxing", "Gaming", "Mobile photography"],
        audience_segments=[
            _seg("tech_enthusiasts", "Tech enthusiasts", ["18-24", "25-34"],
                 ["Tech reviews", "Spec comparisons", "Unboxing videos"],
                 "Compare specifications across channels before deciding."),
            _seg("value_buyers", "Value-focused buyers", ["25-34", "35-44"],
                 ["Best budget picks", "Deals", "Long-term reviews"],
                 "Price-to-performance driven; respond to comparison content."),
        ],
        format_affinity={"in_stream": 1.15, "shorts": 1.15, "in_feed": 0.95},
        objective_bias="Sales / Conversions",
        notes="High consideration cycle; review-style in-stream ads and Shorts comparisons shorten decision time.",
    ),
    CategoryProfile(
        key="fashion_apparel",
        label="Fashion & Apparel",
        keywords=["shirt", "kurta", "dress", "clothing", "apparel", "shoes", "sneakers",
                  "jeans", "abaya", "hijab", "outfit", "jacket", "winter collection",
                  "fabric", "unstitched", "pret", "fashion"],
        intent="impulse",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.40, "25-34": 0.35, "35-44": 0.16, "45-54": 0.06, "55+": 0.03},
        gender_skew={"female": 0.55, "male": 0.35, "unknown": 0.10},
        interests=["Fashion trends", "Style inspiration", "Streetwear", "Seasonal collections", "Shopping hauls"],
        audience_segments=[
            _seg("trend_seekers", "Trend-driven young shoppers", ["18-24", "25-34"],
                 ["Fashion Shorts", "Lookbooks", "Influencer styling"],
                 "Discover via short-form video; buy on impulse when price is right."),
            _seg("occasion_buyers", "Occasion & seasonal buyers", ["25-34", "35-44"],
                 ["Wedding season", "Eid collections", "Winter sales"],
                 "Purchase spikes around events/collections; retargeting effective."),
        ],
        format_affinity={"in_stream": 0.95, "shorts": 1.30, "in_feed": 0.90},
        objective_bias="Sales / Conversions",
        notes="Vertical Shorts are the strongest discovery surface for apparel visuals.",
    ),
    CategoryProfile(
        key="beauty_skincare",
        label="Beauty & Skincare",
        keywords=["skincare", "serum", "cream", "cosmetic", "makeup", "lipstick",
                  "sunscreen", "shampoo", "beauty", "face", "hair", "foundation", "perfume"],
        intent="research",
        avg_order_value_band="low",
        age_weights={"18-24": 0.38, "25-34": 0.37, "35-44": 0.17, "45-54": 0.06, "55+": 0.02},
        gender_skew={"female": 0.70, "male": 0.20, "unknown": 0.10},
        interests=["Skincare routines", "Beauty tutorials", "Ingredient education", "Dermatology reviews"],
        audience_segments=[
            _seg("routine_builders", "Routine builders", ["18-24", "25-34"],
                 ["Glass skin", "ACNE care", "Ingredient breakdowns"],
                 "Follow creators; ingredient-aware; testimonials drive trials."),
            _seg("gift_buyers", "Gift & occasion buyers", ["25-34", "35-44"],
                 ["Gift sets", "Branded bundles"],
                 "Buy bundles around holidays; in-feed browsing converts well."),
        ],
        format_affinity={"in_stream": 1.05, "shorts": 1.25, "in_feed": 1.00},
        objective_bias="Sales / Conversions",
    ),
    CategoryProfile(
        key="food_beverage",
        label="Food & Beverage",
        keywords=["food", "snack", "coffee", "tea", "chai", "masala", "sauce",
                  "beverage", "restaurant", "bakery", " chocolate", "juice", "spice", "honey", "dates"],
        intent="impulse",
        avg_order_value_band="low",
        age_weights={"18-24": 0.28, "25-34": 0.34, "35-44": 0.22, "45-54": 0.11, "55+": 0.05},
        gender_skew={"female": 0.45, "male": 0.45, "unknown": 0.10},
        interests=["Food Shorts", "Recipes", "Street food", "Desi food", "Cooking"],
        audience_segments=[
            _seg("foodies", "Food content viewers", ["18-24", "25-34"],
                 ["Food Shorts", "Recipe videos", "Restaurant reviews"],
                 "High Shorts consumption; visuals trigger impulse orders."),
        ],
        format_affinity={"in_stream": 0.90, "shorts": 1.35, "in_feed": 0.85},
        objective_bias="Website Traffic",
    ),
    CategoryProfile(
        key="fitness_health",
        label="Fitness & Health",
        keywords=["fitness", "gym", "protein", "supplement", "yoga", "weight loss",
                  "treadmill", "vitamin", "health", "workout", "whey"],
        intent="research",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.35, "25-34": 0.38, "35-44": 0.17, "45-54": 0.07, "55+": 0.03},
        gender_skew={"female": 0.40, "male": 0.50, "unknown": 0.10},
        interests=["Workout plans", "Home fitness", "Nutrition", "Transformation stories"],
        audience_segments=[
            _seg("beginners", "Fitness beginners", ["18-24", "25-34"],
                 ["Beginner workouts", "Home training", "Diet plans"],
                 "Seek guidance; transformation content builds trust."),
        ],
        format_affinity={"in_stream": 1.12, "shorts": 1.22, "in_feed": 0.85},
        objective_bias="Leads",
    ),
    CategoryProfile(
        key="home_kitchen",
        label="Home & Kitchen",
        keywords=["kitchen", "cookware", "blender", "fan", "appliance", "furniture",
                  "mattress", "bedsheet", "decor", "storage", "vacuum", "air fryer"],
        intent="research",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.18, "25-34": 0.36, "35-44": 0.26, "45-54": 0.13, "55+": 0.07},
        gender_skew={"female": 0.55, "male": 0.35, "unknown": 0.10},
        interests=["Home organization", "Kitchen gadgets", "Interior ideas", "Product demos"],
        audience_segments=[
            _seg("homemakers", "Household decision makers", ["25-34", "35-44"],
                 ["Home demos", "Cleaning hacks", "Space saving"],
                 "Watch demos; value durability and warranties."),
        ],
        format_affinity={"in_stream": 1.18, "shorts": 1.05, "in_feed": 0.95},
        objective_bias="Sales / Conversions",
    ),
    CategoryProfile(
        key="education_courses",
        label="Education & Courses",
        keywords=["course", "academy", "tuition", "learning", "exam", " institute",
                  "class", "training", "workshop", "certification", " english", "ielts"],
        intent="high_intent",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.42, "25-34": 0.34, "35-44": 0.15, "45-54": 0.06, "55+": 0.03},
        gender_skew={"female": 0.45, "male": 0.45, "unknown": 0.10},
        interests=["Exam preparation", "Skill development", "Freelancing", "Study abroad", "Online learning"],
        audience_segments=[
            _seg("students", "Students & exam candidates", ["18-24"],
                 ["MDCAT/ECAT prep", "IELTS tips", "Board exams"],
                 "Outcome-driven; click through to syllabus/pricing pages."),
            _seg("upskillers", "Young professionals upskilling", ["25-34"],
                 ["Freelancing courses", "AI skills", "Certification"],
                 "Respond to lead forms and free-trial offers."),
        ],
        format_affinity={"in_stream": 1.05, "shorts": 0.95, "in_feed": 1.20},
        objective_bias="Leads",
    ),
    CategoryProfile(
        key="toys_kids",
        label="Toys & Baby Products",
        keywords=["toy", "baby", "kids", "stroller", "diaper", "lego", "doll",
                  "puzzle", " feeder", "car seat"],
        intent="research",
        avg_order_value_band="low",
        age_weights={"25-34": 0.42, "35-44": 0.30, "18-24": 0.15, "45-54": 0.10, "55+": 0.03},
        gender_skew={"female": 0.60, "male": 0.30, "unknown": 0.10},
        interests=["Parenting", "Kids activities", "Baby care", "Toy reviews"],
        audience_segments=[
            _seg("new_parents", "New parents", ["25-34", "35-44"],
                 ["Baby care tips", "Safety reviews", "Parenting vlogs"],
                 "Safety and reviews dominate the decision; trust content matters."),
        ],
        format_affinity={"in_stream": 1.08, "shorts": 1.00, "in_feed": 1.02},
        objective_bias="Sales / Conversions",
    ),
    CategoryProfile(
        key="automotive",
        label="Automotive & Accessories",
        keywords=["car", "bike", "motorcycle", "helmet", "tyre", "engine", "accessor",
                  "dashcam", "car care", "electric bike"],
        intent="research",
        avg_order_value_band="high",
        age_weights={"18-24": 0.28, "25-34": 0.40, "35-44": 0.22, "45-54": 0.07, "55+": 0.03},
        gender_skew={"female": 0.15, "male": 0.75, "unknown": 0.10},
        interests=["Car reviews", "Bike modifications", "EV", "Auto detailing"],
        audience_segments=[
            _seg("enthusiasts", "Auto enthusiasts", ["18-24", "25-34"],
                 ["Reviews", "Modifications", "Test rides"],
                 "Video-heavy researchers; in-stream reviews + Shorts clips."),
        ],
        format_affinity={"in_stream": 1.22, "shorts": 1.12, "in_feed": 0.82},
        objective_bias="Website Traffic",
    ),
    CategoryProfile(
        key="jewelry_accessories",
        label="Jewelry & Accessories",
        keywords=["jewellery", "jewelry", "ring", "necklace", "earring", "bracelet",
                  "watch", "gold", "silver", "bangle", "pendant", "wallet", "leather",
                  "bag", "handbag", "purse", "backpack", "belt", "accessor"],
        intent="high_intent",
        avg_order_value_band="premium",
        age_weights={"18-24": 0.25, "25-34": 0.35, "35-44": 0.24, "45-54": 0.12, "55+": 0.04},
        gender_skew={"female": 0.65, "male": 0.25, "unknown": 0.10},
        interests=["Jewelry design", "Wedding jewelry", "Luxury", "Handmade"],
        audience_segments=[
            _seg("brides", "Bridal & wedding shoppers", ["25-34"],
                 ["Bridal sets", "Wedding season", "Gold rates"],
                 "High-value, high-consideration; trust and authenticity content."),
            _seg("giftees", "Gift buyers", ["25-34", "35-44"],
                 ["Gift ideas", "Anniversary"],
                 "Seasonal gifting; in-feed discovery + retargeting."),
        ],
        format_affinity={"in_stream": 1.05, "shorts": 1.00, "in_feed": 1.10},
        objective_bias="Sales / Conversions",
    ),
    CategoryProfile(
        key="software_app",
        label="Software & Apps",
        keywords=["app", "software", "saas", "tool", "platform", "subscription",
                  "plugin", "template", "crm", "website", "hosting"],
        intent="subscription",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.30, "25-34": 0.44, "35-44": 0.18, "45-54": 0.06, "55+": 0.02},
        gender_skew={"female": 0.35, "male": 0.55, "unknown": 0.10},
        interests=["Productivity", "Startups", "AI tools", "Freelancing", "No-code"],
        audience_segments=[
            _seg("founders", "Founders & freelancers", ["25-34"],
                 ["Productivity tools", "Automation", "Case studies"],
                 "Free trial/demo funnels; lead objective with retargeting."),
        ],
        format_affinity={"in_stream": 1.10, "shorts": 0.90, "in_feed": 1.20},
        objective_bias="Leads",
    ),
    CategoryProfile(
        key="services_local",
        label="Local Services",
        keywords=["service", "repair", "cleaning", "salon", "gym membership",
                  "delivery", "tour", "travel", "event", "photography", "academy admission"],
        intent="high_intent",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.24, "25-34": 0.40, "35-44": 0.24, "45-54": 0.09, "55+": 0.03},
        gender_skew={"female": 0.45, "male": 0.45, "unknown": 0.10},
        interests=["Local deals", "Home services", "Travel vlogs", "Event planning"],
        audience_segments=[
            _seg("local_searchers", "Local service seekers", ["25-34", "35-44"],
                 ["Near me", "Reviews and testimonials"],
                 "Need trust signals quickly; call/lead actions convert."),
        ],
        format_affinity={"in_stream": 1.05, "shorts": 0.98, "in_feed": 1.15},
        objective_bias="Leads",
    ),
    CategoryProfile(
        key="books_media",
        label="Books & Media",
        keywords=["book", "novel", "magazine", "course book", "comics", "audio book"],
        intent="impulse",
        avg_order_value_band="low",
        age_weights={"18-24": 0.38, "25-34": 0.36, "35-44": 0.16, "45-54": 0.07, "55+": 0.03},
        gender_skew={"female": 0.50, "male": 0.40, "unknown": 0.10},
        interests=["Book reviews", "Self improvement", "Fiction", "BookTube"],
        audience_segments=[
            _seg("readers", "Active readers", ["18-24", "25-34"],
                 ["Book reviews", "Recommendations"],
                 "Community-driven; creator mentions convert strongly."),
        ],
        format_affinity={"in_stream": 1.00, "shorts": 1.15, "in_feed": 1.05},
        objective_bias="Website Traffic",
    ),
    CategoryProfile(
        key="general",
        label="General / Other",
        keywords=[],
        intent="research",
        avg_order_value_band="medium",
        age_weights={"18-24": 0.30, "25-34": 0.36, "35-44": 0.20, "45-54": 0.09, "55+": 0.05},
        gender_skew={"female": 0.45, "male": 0.45, "unknown": 0.10},
        interests=["Product reviews", "Shopping guides", "How-to videos"],
        audience_segments=[
            _seg("broad", "Broad interest shoppers", ["18-24", "25-34", "35-44"],
                 ["Product reviews", "Deals", "How-to"],
                 "Generic profile used when the product cannot be classified confidently."),
        ],
        format_affinity={"in_stream": 1.00, "shorts": 1.00, "in_feed": 1.00},
        objective_bias="Sales / Conversions",
        notes="Fallback profile — confidence is reduced and the user is asked to review inferred assumptions.",
    ),
]

OBJECTIVE_DECISION_RULES: list[dict] = [
    {"objective": "Leads", "conditions": {"intent": ["high_intent", "subscription"]}, "weight": 3.0,
     "rationale": "Products with a clear enquiry/signup journey (services, courses, software) convert best when the campaign captures leads rather than immediate purchases."},
    {"objective": "Sales / Conversions", "conditions": {"intent": ["research", "impulse"]}, "weight": 2.5,
     "rationale": "Shoppable products with visible pricing benefit from conversion-optimized video campaigns driving directly to product pages."},
    {"objective": "Website Traffic", "conditions": {"avg_order_value_band": ["low"]}, "weight": 1.6,
     "rationale": "Low ticket items profit from volume; traffic campaigns feed retargeting pools cheaply."},
    {"objective": "Brand Awareness", "conditions": {"avg_order_value_band": ["premium"]}, "weight": 1.4,
     "rationale": "Premium purchases need trust built before conversion; awareness primes future demand."},
    {"objective": "Video Views", "conditions": {"intent": ["impulse"]}, "weight": 1.2,
     "rationale": "Impulse categories gain cheap, engaged video views that later convert through remarketing."},
]

# format -> objective -> multiplier (documented heuristic priors).
# Deliberately NON-uniform: every objective has a different best format, which
# mirrors YouTube platform behaviour instead of a single default winner:
#   Brand Awareness      -> in-stream (TV-like brand lift), Shorts close second
#   Video Views          -> Shorts (cheapest incremental views on YouTube)
#   Website Traffic      -> in-feed (a deliberate thumbnail click is traffic-intent)
#   Leads                -> in-feed + in-stream (considered actions), Shorts weakest
#   Sales / Conversions  -> in-feed / in-stream product demos, Shorts mid-funnel
FORMAT_OBJECTIVE_FIT: dict[str, dict[str, float]] = {
    "in_stream": {"Brand Awareness": 1.18, "Video Views": 0.95, "Website Traffic": 0.92, "Leads": 1.08, "Sales / Conversions": 1.06},
    "shorts":    {"Brand Awareness": 1.10, "Video Views": 1.22, "Website Traffic": 0.98, "Leads": 0.82, "Sales / Conversions": 0.90},
    "in_feed":   {"Brand Awareness": 0.80, "Video Views": 0.90, "Website Traffic": 1.15, "Leads": 1.12, "Sales / Conversions": 1.12},
}


def classify_category(text: str) -> tuple[CategoryProfile, float]:
    """Keyword-overlap classifier with confidence in [0,1]."""
    t = f" {text.lower()} "
    best: CategoryProfile | None = None
    best_score = 0
    for profile in CATEGORY_PROFILES:
        score = sum(1 for kw in profile.keywords if kw in t)
        if score > best_score:
            best, best_score = profile, score
    if best is None or best_score == 0:
        general = next(p for p in CATEGORY_PROFILES if p.key == "general")
        return general, 0.15
    confidence = min(0.95, 0.35 + 0.18 * best_score)
    return best, confidence
