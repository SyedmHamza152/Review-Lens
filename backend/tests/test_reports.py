"""Report exporter tests — files must exist and be non-trivial."""
from app.bigdata.generator import generate_dataset  # noqa: F401
from app.models.analysis import ProductAnalysis
from app.models.product import Product
from app.reports.generator import generate_csv, generate_excel, generate_pdf


def _make_analysis(db) -> ProductAnalysis:
    product = Product(name="Premium Cricket Bat", description="English willow bat",
                      total_budget=50000)
    db.add(product)
    db.flush()
    a = ProductAnalysis(
        product_id=product.id, category="Sports & Outdoor Equipment",
        product_type="Premium / professional tier",
        features=["English willow", "Hard-ball grade"],
        value_proposition="Match-day confidence.",
        problems_solved=["Unreliable gear"],
        audience={"age_weights": {"18-24": 0.4, "25-34": 0.4}, "interests": ["Cricket"],
                  "geo": {"priority_cities": ["Karachi", "Lahore"]},
                  "segments": [{"key": "club", "label": "Club players",
                                "age_bands": ["18-24"], "note": "n"}]},
        objective="Sales / Conversions", objective_rationale="Shoppable product.",
        competitor_summary={}, suitable_formats=[],
        inference_method="rule_based", data_source_label="SYNTHETIC DEMO DATA",
        confidence=0.5,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_pdf_export(db_session, tmp_path):
    a = _make_analysis(db_session)
    out = generate_pdf(db_session, a, tmp_path / "rep.pdf")
    assert out.exists() and out.stat().st_size > 2000
    assert out.read_bytes()[:4] == b"%PDF"


def test_excel_export(db_session, tmp_path):
    a = _make_analysis(db_session)
    out = generate_excel(db_session, a, tmp_path / "rep.xlsx")
    assert out.exists() and out.stat().st_size > 2000
    from openpyxl import load_workbook

    wb = load_workbook(out)
    assert "Summary" in wb.sheetnames and "Audience" in wb.sheetnames


def test_csv_export(db_session, tmp_path):
    a = _make_analysis(db_session)
    out = generate_csv(db_session, a, tmp_path / "rep.csv")
    assert out.exists() and out.stat().st_size > 200
    text = out.read_text()
    assert "INFERENCE" in text
