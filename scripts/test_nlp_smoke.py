"""Quick smoke test of the NLP engine against the spec's examples."""
import sys
sys.path.insert(0, "/home/z/my-project/backend")

from app.nlp.language import detect_language
from app.nlp.sentiment import analyze_sentiment
from app.nlp.aspects import extract_aspects, complaint_scope

CASES = [
    # (text, expected_language, expected_sentiment)
    ("The product is excellent, and the quality is worth the price.", "english", "positive"),
    ("یہ پروڈکٹ بہت اچھی ہے اور قیمت کے لحاظ سے بہترین ہے۔", "urdu", "positive"),
    ("Ye product bohat acha hai, paisay wasool hain.", "roman_urdu", "positive"),
    ("The camera is amazing, but the battery is terrible.", "english", "mixed"),
    ("کیمرہ بہت اچھا ہے لیکن بیٹری خراب ہے۔", "urdu", "mixed"),
    ("Camera zabardast hai lekin battery bilkul achi nahi.", "roman_urdu", "mixed"),
    ("Quality achi hai but delivery bohat late thi.", "mixed", "mixed"),
    ("Product acha hai, but price thori zyada hai.", "mixed", "mixed"),
    ("Total waste of money, garbage quality.", "english", "negative"),
    ("Bilkul bekar product hai, paisay barbaad.", "roman_urdu", "negative"),
    ("یہ بالکل بیکار ہے۔", "urdu", "negative"),
    ("Battery backup bohat weak hai, 2 ghante mein band ho jata hai.", "roman_urdu", "negative"),
    ("Delivery on time thi, packaging bhi solid thi.", "mixed", "positive"),
    ("Nakli product bheja hai, asli nahi hai.", "roman_urdu", "negative"),
    ("Value for money, highly recommended!", "english", "positive"),
    ("Ok", "english", "neutral"),
]

ok = 0
for text, exp_lang, exp_sent in CASES:
    lang = detect_language(text)
    sent = analyze_sentiment(text)
    aspects = extract_aspects(sent)
    scope = complaint_scope(aspects)
    got_lang = lang.language
    lang_ok = got_lang == exp_lang or (exp_lang == "mixed" and got_lang == "mixed")
    sent_ok = sent.label == exp_sent
    mark = "✓" if (lang_ok and sent_ok) else "✗"
    ok += lang_ok and sent_ok
    print(f"{mark} [{got_lang}/{lang.confidence:.2f}{'?' if lang.uncertain else ''}] "
          f"[{sent.label} {sent.score:+.2f} conf={sent.confidence:.2f}] scope={scope:7s} "
          f"aspects={[ (m.aspect, m.label) for m in aspects]} :: {text[:58]}")

print(f"\n{ok}/{len(CASES)} passed")
