"""Sentiment engine tests: all four classes, negation, sarcasm, confidence."""
from app.nlp.sentiment import analyze_sentiment


def test_positive_english():
    r = analyze_sentiment("The product is excellent, and the quality is worth the price.")
    assert r.label == "positive"
    assert r.score > 0.2


def test_positive_roman_urdu():
    r = analyze_sentiment("Ye product bohat acha hai, paisay wasool hain.")
    assert r.label == "positive"


def test_positive_urdu():
    r = analyze_sentiment("یہ پروڈکٹ بہت اچھی ہے اور قیمت کے لحاظ سے بہترین ہے۔")
    assert r.label == "positive"


def test_negative_english():
    r = analyze_sentiment("Total waste of money, garbage quality.")
    assert r.label == "negative"
    assert r.score < -0.2


def test_negative_roman_urdu():
    r = analyze_sentiment("Bilkul bekar product hai, paisay barbaad.")
    assert r.label == "negative"


def test_mixed_english():
    r = analyze_sentiment("The camera is amazing, but the battery is terrible.")
    assert r.label == "mixed"


def test_mixed_urdu():
    r = analyze_sentiment("کیمرہ بہت اچھا ہے لیکن بیٹری خراب ہے۔")
    assert r.label == "mixed"


def test_mixed_roman_urdu():
    r = analyze_sentiment("Camera zabardast hai lekin battery bilkul achi nahi.")
    assert r.label == "mixed"


def test_mixed_mixed_language():
    r = analyze_sentiment("Quality achi hai but delivery bohat late thi.")
    assert r.label == "mixed"


def test_negation_flips_polarity():
    pos = analyze_sentiment("The quality is good")
    neg = analyze_sentiment("The quality is not good")
    assert pos.label == "positive"
    assert neg.label == "negative"


def test_negation_roman_urdu_word_order():
    # negator AFTER the adjective (common in Urdu: "achi nahi")
    r = analyze_sentiment("Camera zabardast hai lekin battery bilkul achi nahi.")
    battery_clause = [c for c in r.clauses if "battery" in c.text]
    assert battery_clause and battery_clause[0].label == "negative"


def test_spelling_variants_normalized():
    a = analyze_sentiment("Ye bohat acha hai")
    b = analyze_sentiment("Ye bahut achha hai")
    c = analyze_sentiment("Ye bohot accha hai")
    assert a.label == b.label == c.label == "positive"


def test_sarcasm_suspected():
    r = analyze_sentiment("Wah kya product hai, 2 din mein kharab ho gaya. Great going.")
    assert r.sarcasm_suspect
    assert r.label == "negative"


def test_neutral_factual():
    r = analyze_sentiment("The box includes a cable, a case and the documentation.")
    assert r.label in ("neutral",)


def test_uncertainty_flagged_for_low_confidence():
    r = analyze_sentiment("Ok")
    assert r.uncertain


def test_original_text_preserved():
    text = "Ye BOHAT ACHHA hai!!!"
    analyze_sentiment(text)
    # normalization happens on a copy; nothing raises, and lexicons fold case
    r = analyze_sentiment(text)
    assert r.label == "positive"
