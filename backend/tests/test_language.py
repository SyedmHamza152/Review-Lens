"""Language detection tests (English / Urdu script / Roman Urdu / mixed)."""
from app.nlp.language import detect_language


def test_english():
    r = detect_language("The product is excellent, and the quality is worth the price.")
    assert r.language == "english"
    assert r.confidence >= 0.5
    assert not r.uncertain


def test_urdu_script():
    r = detect_language("یہ پروڈکٹ بہت اچھی ہے اور قیمت کے لحاظ سے بہترین ہے۔")
    assert r.language == "urdu"
    assert r.confidence >= 0.6


def test_roman_urdu():
    r = detect_language("Ye product bohat acha hai, paisay wasool hain.")
    assert r.language == "roman_urdu"


def test_roman_urdu_spelling_variants():
    for variant in ("Ye product bahut achha hai", "Ye product bohot acha hai"):
        assert detect_language(variant).language == "roman_urdu"


def test_mixed_urdu_script_english():
    r = detect_language("Ye phone bohat acha hai, battery life is amazing بھی")
    assert r.language in ("mixed", "roman_urdu")  # urdu-script+latin mixture


def test_mixed_roman_english():
    r = detect_language("Quality achi hai but delivery bohat late thi.")
    assert r.language == "mixed"


def test_uncertain_short_text_flagged():
    r = detect_language("k")
    assert r.uncertain or r.language == "unknown"


def test_unknown_language():
    r = detect_language("12345 !!!")
    assert r.language == "unknown" or r.uncertain
