"""Platform-wide constants.

STRICT SCOPE: only YouTube advertising inventory is supported. Search,
Display, and every non-Google platform are intentionally absent — they must
never appear in recommendations, datasets, reports or the UI.
"""
from __future__ import annotations

SUPPORTED_FORMATS: dict[str, str] = {
    "in_stream": "YouTube In-Stream Ads",
    "shorts": "YouTube Shorts Ads",
    "in_feed": "YouTube In-Feed Video Ads",
}

FORMAT_KEYS = list(SUPPORTED_FORMATS.keys())

MARKETING_OBJECTIVES: list[str] = [
    "Brand Awareness",
    "Video Views",
    "Website Traffic",
    "Leads",
    "Sales / Conversions",
]

# Google Ads advertising_channel_subtype -> canonical AdPilot format.
# Documented mapping (assumption noted in README): skippable in-stream
# inventory appears under VIDEO_ACTION / VIDEO_RESPONSIVE /
# VIDEO_EFFICIENT_REACH; in-feed video under VIDEO_RESPONSIVE "reach" plans;
# Shorts inventory is reported inside VIDEO campaigns without a dedicated
# subtype, so we classify by campaign name signals where possible and
# default unknown VIDEO subtypes to in_stream.
SUBTYPE_TO_FORMAT: dict[str, str] = {
    "VIDEO_ACTION": "in_stream",
    "VIDEO_RESPONSIVE": "in_stream",
    "VIDEO_EFFICIENT_REACH": "in_stream",
    "VIDEO_NON_SKIPPABLE": "in_stream",
    "VIDEO_SEQUENCE": "in_stream",
    "VIDEO_OUTSTREAM": "in_feed",
    "": "in_stream",
}

DATA_LABELS = {
    "live": "LIVE DATA",
    "synthetic": "SYNTHETIC DEMO DATA",
    "prediction": "MODEL PREDICTION",
}

SUPPORTED_CURRENCIES = ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR"]

AGE_GROUPS = ["18-24", "25-34", "35-44", "45-54", "55+"]

DEVICES = ["mobile", "desktop", "tablet", "tv"]

# Pakistan-first market cities (default market), used for audience inference
# and synthetic data. Selecting another market switches the city pool.
MARKET_CITIES = {
    "PK": [
        "Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad",
        "Multan", "Peshawar", "Quetta", "Sialkot", "Hyderabad",
    ],
    "US": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"],
    "AE": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"],
    "SA": ["Riyadh", "Jeddah", "Dammam", "Mecca"],
    "IN": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"],
}
