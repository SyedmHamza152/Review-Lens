"""Unit tests: dedup, spam detection, relevance, verdict rules."""
from app.nlp.relevance import dedup_hash, fuzzy_hash, product_tokens, relevance_score, spam_signals
from app.services.aggregation import _verdict_label


def test_dedup_hash_stable_and_sensitive():
    a = dedup_hash("Ye product bohat acha hai")
    b = dedup_hash("ye product bohat acha hai")
    c = dedup_hash("Ye product bohat bekar hai")
    assert a == b            # case-insensitive
    assert a != c


def test_fuzzy_hash_near_duplicates():
    long_a = ("Ye product bohat acha hai aur quality bhi zabardast hai, "
              "delivery bhi waqt par mili, packaging sealed thi aur seller ne "
              "shukriya kaha " + "x" * 40)
    long_b = long_a + " hain"
    assert fuzzy_hash(long_a) == fuzzy_hash(long_b)   # same first-100 normalized chars
    assert fuzzy_hash(long_a) != fuzzy_hash("Totally different review text")


def test_spam_detection_promotional():
    ok, reason = spam_signals("BIG SALE buy now click link in bio free coupon!")
    assert ok and reason in ("promotional", "contains_link")


def test_spam_detection_short():
    ok, reason = spam_signals("ok")
    assert ok


def test_spam_detection_clean_review():
    ok, reason = spam_signals("Battery backup kamaal ka hai, sara din chalta hai.")
    assert not ok


def test_relevance_score_positive_for_matching():
    tokens = product_tokens("Samsung Galaxy S25 Ultra", "512GB Titanium")
    assert relevance_score("samsung galaxy s25 ultra is amazing", tokens) > 0.4


def test_relevance_score_zero_for_unrelated():
    tokens = product_tokens("Samsung Galaxy S25 Ultra", None)
    assert relevance_score("best biryani recipe in karachi", tokens) == 0.0


# ---------------- verdict thresholds ----------------
class C(dict):
    def __getitem__(self, k):  # Counter-like access with default 0
        return self.get(k, 0)


def test_verdict_insufficient_data():
    c = C(positive=2, negative=1)
    assert _verdict_label(c, 3) == "Insufficient Data"


def test_verdict_generally_positive():
    c = C(positive=60, negative=5, neutral=10, mixed=5)
    assert _verdict_label(c, 80) == "Generally Positive"


def test_verdict_mixed_feedback():
    c = C(positive=12, negative=12, neutral=2, mixed=14)
    assert _verdict_label(c, 40) in ("Mixed Feedback",)


def test_verdict_generally_negative():
    c = C(positive=3, negative=50, neutral=7, mixed=5)
    assert _verdict_label(c, 65) in ("Generally Negative", "Mostly Negative with Some Positives")


def test_verdict_mostly_positive_with_concerns():
    c = C(positive=45, negative=25, neutral=5, mixed=5)
    assert _verdict_label(c, 80) == "Mostly Positive with Some Concerns"
