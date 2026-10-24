"""Model evaluation per language class (spec section 16).

Reports precision, recall, F1 and confusion matrices SEPARATELY for
English / Urdu script / Roman Urdu / mixed-language comments, using the
labeled dataset in tests/data/eval_dataset.tsv (120 realistic Pakistani
e-commerce/social-media comments).

Run:  python3 -m tests.evaluate_sentiment
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.nlp.language import detect_language
from app.nlp.sentiment import analyze_sentiment

DATA = Path(__file__).resolve().parent / "data" / "eval_dataset.tsv"
LABELS = ["positive", "negative", "neutral", "mixed"]


def load():
    rows = []
    for line in DATA.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        text, lang, sent = line.rsplit("|", 2)
        rows.append((text.strip(), lang.strip(), sent.strip()))
    return rows


def main() -> int:
    rows = load()
    print(f"Evaluated {len(rows)} labeled comments "
          f"({dict(Counter(l for _, l, _ in rows))})\n")

    macro_f1s = {}
    for lang in ("english", "roman_urdu", "urdu", "mixed"):
        subset = [(t, s) for t, l, s in rows if l == lang]
        if not subset:
            continue
        y_true = [s for _, s in subset]
        y_pred = [analyze_sentiment(t).label for t, _ in subset]
        prec, rec, f1, sup = precision_recall_fscore_support(
            y_true, y_pred, labels=LABELS, zero_division=0)
        acc = sum(a == b for a, b in zip(y_true, y_pred)) / len(y_true)
        macro_f1s[lang] = sum(f1) / len(f1)
        print(f"=== {lang} (n={len(subset)}) accuracy={acc:.2f} macroF1={macro_f1s[lang]:.2f}")
        for i, lbl in enumerate(LABELS):
            print(f"    {lbl:9s} P={prec[i]:.2f} R={rec[i]:.2f} F1={f1[i]:.2f} n={sup[i]}")
        cm = confusion_matrix(y_true, y_pred, labels=LABELS)
        print("    confusion (rows=true, cols=pred):")
        print("              " + "  ".join(f"{l[:7]:>7s}" for l in LABELS))
        for i, lbl in enumerate(LABELS):
            print(f"    {lbl:9s} " + "  ".join(f"{cm[i][j]:>7d}" for j in range(len(LABELS))))
        # list mispredictions for transparency
        wrong = [(t, a, b) for (t, a), b in zip(subset, y_pred) if a != b]
        if wrong:
            print(f"    misclassified ({len(wrong)}):")
            for t, a, b in wrong[:6]:
                print(f"      [{a}->{b}] {t[:70]}")
        print()

    # language detection accuracy
    lang_true = [l for _, l, _ in rows]
    lang_pred = [detect_language(t).language for t, _, _ in rows]
    # 'mixed' true labels may map to mixed OR either dominant side
    def norm(p):
        return p if p in ("english", "urdu", "roman_urdu", "mixed") else "unknown"
    lacc = sum(a == norm(b) for a, b in zip(lang_true, lang_pred)) / len(lang_true)
    print(f"Language detection accuracy: {lacc:.2f}")

    overall = sum(macro_f1s.values()) / len(macro_f1s)
    print(f"Overall macro-F1 across language classes: {overall:.2f}")
    print("NOTE: rule-based engine; numbers are reported honestly and should be "
          "re-evaluated when transformer engines are enabled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
