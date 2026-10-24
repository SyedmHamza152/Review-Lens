"""Aspect-based sentiment tests + complaint scope separation."""
from app.nlp.aspects import complaint_scope, extract_aspects
from app.nlp.sentiment import analyze_sentiment


def _labels_map(text: str) -> dict:
    sent = analyze_sentiment(text)
    return {m.aspect: m.label for m in extract_aspects(sent)}


def test_battery_negative_product_positive():
    m = _labels_map("The camera is amazing, but the battery is terrible.")
    assert m.get("battery") == "negative"


def test_quality_positive_price_negative():
    m = _labels_map("Quality achi hai but price thori zyada hai.")
    assert m.get("quality") == "positive"
    assert m.get("price_value") == "negative"


def test_delivery_complaint_scope_marketplace():
    sent = analyze_sentiment("Product is great but the delivery was very late.")
    mentions = extract_aspects(sent)
    assert complaint_scope(mentions) in ("marketplace", "both")


def test_product_complaint_scope():
    sent = analyze_sentiment("Battery is terrible and the screen cracked.")
    mentions = extract_aspects(sent)
    assert complaint_scope(mentions) == "product"


def test_no_complaint_scope_none():
    sent = analyze_sentiment("Bohat acha product hai, sab theek hai.")
    mentions = extract_aspects(sent)
    assert complaint_scope(mentions) == "none"


def test_product_vs_seller_distinction():
    # likes the product, complains about seller -> recorded separately
    m = _labels_map("Phone zabardast hai lekin seller beiman hai.")
    assert m.get("seller_reliability") == "negative"


def test_aspect_confidence_present():
    sent = analyze_sentiment("Battery life is terrible after two weeks.")
    mentions = extract_aspects(sent)
    bat = [m for m in mentions if m.aspect == "battery"]
    assert bat and bat[0].confidence > 0.3
