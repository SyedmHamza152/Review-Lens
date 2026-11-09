"""Report exporters — PDF (ReportLab), Excel (OpenPyXL), CSV.

Each report contains: product info, objective, audience analysis, competitor
research, recommended allocation, predicted results, methodology, model
confidence and data limitations. Data-source labels are printed on every
section so no number can be mistaken for another class of evidence.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.analysis import ProductAnalysis
from app.models.recommendation import BudgetRecommendation


def _context(db: Session, analysis: ProductAnalysis) -> dict:
    from app.models.product import Product
    from app.models.research import ResearchVideo

    product = db.get(Product, analysis.product_id)
    rec = db.query(BudgetRecommendation).filter(
        BudgetRecommendation.analysis_id == analysis.id
    ).order_by(BudgetRecommendation.id.desc()).first()
    videos = db.query(ResearchVideo).filter(ResearchVideo.analysis_id == analysis.id).order_by(
        ResearchVideo.views.desc()).limit(10).all()
    return {
        "analysis": analysis,
        "product": product,
        "rec": rec,
        "videos": videos,
    }


def _limitation_lines(ctx: dict) -> list[str]:
    a = ctx["analysis"]
    lines = [
        "• Inferred audience/age/interest data are hypotheses from the rule engine, not verified demographics.",
        "• Predicted impressions/clicks/conversions/revenue are MODEL PREDICTIONS from documented funnel assumptions; they are not guarantees.",
    ]
    if a.ads_history_status != "live":
        lines.append("• Campaign history used ESTIMATED DATA (Google Ads not connected or without history).")
    if a.youtube_research_status != "live":
        lines.append("• Competitor research could not reach the YouTube Data API; the competitor section may be empty.")
    lines.append("• Public YouTube statistics describe organic engagement only — never ad spend, conversions or competitor ROAS.")
    return lines


# --------------------------------------------------------------------------- PDF
def generate_pdf(db: Session, analysis: ProductAnalysis, out_path: str | Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    ctx = _context(db, analysis)
    a: ProductAnalysis = ctx["analysis"]
    rec = ctx["rec"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0f172a")
    accent = colors.HexColor("#10b981")
    h1 = ParagraphStyle("H1", parent=styles["Title"], textColor=navy, fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=navy, fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12.5)
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor=colors.HexColor("#475569"))

    story = [
        Paragraph("AdPilot AI — Budget Optimization Report", h1),
        Paragraph(f"Generated for: <b>{ctx['product'].name}</b> · Currency: {rec.currency if rec else 'PKR'} · "
                  f"Data labels: LIVE / ESTIMATED / MODEL PREDICTION are marked per section.", small),
        HRFlowable(width="100%", color=accent, thickness=2),
    ]

    story.append(Paragraph("1. Product & Objective", h2))
    story.append(Paragraph(
        f"<b>Category:</b> {a.category} · <b>Type:</b> {a.product_type}<br/>"
        f"<b>Marketing objective:</b> {a.objective}<br/>{a.objective_rationale}", body))
    story.append(Paragraph(f"<b>Value proposition:</b> {a.value_proposition}", body))

    story.append(Paragraph("2. Audience Analysis (inference — not verified demographics)", h2))
    aud = a.audience or {}
    age_rows = [[k, f"{v * 100:.0f}%"] for k, v in (aud.get("age_weights") or {}).items()]
    age_tbl = Table([["Age band", "Weight"]] + age_rows, colWidths=[60 * mm, 30 * mm])
    age_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
    ]))
    story.append(age_tbl)
    segs = aud.get("segments") or []
    for s in segs[:4]:
        story.append(Paragraph(f"<b>{s.get('label', 'Segment')}</b> ({', '.join(s.get('age_bands', []))}) — "
                               f"{s.get('note', '')}", body))
    story.append(Paragraph(f"<b>Interests:</b> {', '.join(aud.get('interests', []))}", body))
    story.append(Paragraph(f"<b>Geo hypothesis:</b> {', '.join((aud.get('geo') or {}).get('priority_cities', []))}", small))

    story.append(Paragraph("3. Competitor Research (public YouTube content — organic metrics)", h2))
    if ctx["videos"]:
        vid_rows = [["Video", "Channel", "Views", "Engagement %"]]
        for v in ctx["videos"][:8]:
            vid_rows.append([v.title[:60], v.channel_title[:25], f"{v.views:,}", f"{v.engagement_rate * 100:.2f}"])
        vid_tbl = Table(vid_rows, colWidths=[75 * mm, 40 * mm, 25 * mm, 25 * mm])
        vid_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ]))
        story.append(vid_tbl)
    else:
        story.append(Paragraph("No live research rows available for this analysis.", body))

    if not rec:
        story.append(PageBreak())
        story.append(Paragraph("4. Budget recommendation pending — run the optimizer.", body))
    else:
        story.append(Paragraph("4. Recommended Allocation", h2))
        alloc_rows = [["Format", "Share", "Amount", "Conv.", "ROAS", "Confidence"]]
        for al in rec.allocations:
            p = al.get("predicted", {})
            alloc_rows.append([
                al["label"], f"{al['share'] * 100:.0f}%",
                f"{rec.currency} {al['amount']:,.0f}",
                f"{p.get('conversions', 0):,.0f}",
                f"{p.get('roas') or '—'}",
                f"{al.get('confidence', 0) * 100:.0f}%",
            ])
        alloc_tbl = Table(alloc_rows, colWidths=[48 * mm, 18 * mm, 34 * mm, 22 * mm, 18 * mm, 25 * mm])
        alloc_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(alloc_tbl)
        pt = rec.predicted_totals or {}
        story.append(Paragraph(
            f"<b>Predicted totals (MODEL PREDICTION):</b> impressions {pt.get('impressions', 0):,} · "
            f"clicks {pt.get('clicks', 0):,} · conversions {pt.get('conversions', 0):,.0f} · "
            f"revenue {rec.currency} {pt.get('revenue', 0):,.0f} · ROAS {pt.get('roas', '—')} · "
            f"confidence {rec.confidence * 100:.0f}%", body))

        story.append(Paragraph("5. Why this allocation (per-format reasoning)", h2))
        for al in rec.allocations:
            story.append(Paragraph(f"<b>{al['label']} ({al['share'] * 100:.0f}%)</b> — {al['reason']}", body))

        story.append(Paragraph("6. Methodology", h2))
        story.append(Paragraph(rec.methodology, body))
        story.append(Paragraph(f"<b>Algorithm:</b> {rec.algorithm} · Cold start: {'yes' if rec.cold_start else 'no'}", small))

    story.append(Paragraph("7. Data Limitations", h2))
    for line in _limitation_lines(ctx):
        story.append(Paragraph(line, body))

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="AdPilot AI Report")
    doc.build(story)
    return out_path


# --------------------------------------------------------------------------- Excel
def generate_excel(db: Session, analysis: ProductAnalysis, out_path: str | Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    ctx = _context(db, analysis)
    a, rec = ctx["analysis"], ctx["rec"]
    wb = Workbook()
    header_fill = PatternFill("solid", fgColor="0F172A")
    header_font = Font(color="FFFFFF", bold=True)

    def style_header(ws):
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
        ws.freeze_panes = "A2"
        for col in ws.columns:
            width = max((len(str(c.value or "")) for c in col), default=10)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(width + 2, 50)

    ws = wb.active
    ws.title = "Summary"
    ws.append(["Field", "Value"])
    rows = [
        ("Product", ctx["product"].name),
        ("Description", ctx["product"].description or "—"),
        ("Category", a.category),
        ("Product type", a.product_type),
        ("Marketing objective", a.objective),
        ("Objective rationale", a.objective_rationale),
        ("Value proposition", a.value_proposition),
        ("Inference method", a.inference_method),
        ("YouTube research status", a.youtube_research_status),
        ("Ads history status", a.ads_history_status),
        ("Overall confidence", a.confidence),
    ]
    for r in rows:
        ws.append(list(r))
    style_header(ws)

    if rec:
        ws = wb.create_sheet("Allocation")
        ws.append(["Format", "Share %", "Amount", "Predicted conversions", "Predicted ROAS", "Confidence %", "Reason"])
        for al in rec.allocations:
            ws.append([al["label"], round(al["share"] * 100, 1), al["amount"],
                       al["predicted"].get("conversions"), al["predicted"].get("roas"),
                       round(al.get("confidence", 0) * 100), al["reason"]])
        style_header(ws)

        ws = wb.create_sheet("Predicted totals")
        for k, v in (rec.predicted_totals or {}).items():
            ws.append([k, v])
        ws.append(["Methodology", rec.methodology])
        style_header(ws)

    ws = wb.create_sheet("Audience")
    aud = a.audience or {}
    ws.append(["Age band", "Weight %"])
    for k, v in (aud.get("age_weights") or {}).items():
        ws.append([k, round(v * 100)])
    ws.append([])
    ws.append(["Interest"])
    for i in aud.get("interests", []):
        ws.append([i])
    ws.append([])
    ws.append(["Segment", "Ages", "Note"])
    for s in aud.get("segments", []):
        ws.append([s.get("label"), ", ".join(s.get("age_bands", [])), s.get("note", "")])
    style_header(ws)

    ws = wb.create_sheet("Competitors")
    ws.append(["Title", "Channel", "Views", "Likes", "Comments", "Engagement %", "Data label"])
    for v in ctx["videos"]:
        ws.append([v.title, v.channel_title, v.views, v.likes, v.comments,
                   round(v.engagement_rate * 100, 3), v.data_source_label])
    style_header(ws)

    ws = wb.create_sheet("Limitations")
    for line in _limitation_lines(ctx):
        ws.append([line])
    style_header(ws)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


# --------------------------------------------------------------------------- CSV
def generate_csv(db: Session, analysis: ProductAnalysis, out_path: str | Path) -> Path:
    import csv

    ctx = _context(db, analysis)
    a, rec = ctx["analysis"], ctx["rec"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["section", "item", "metric", "value", "data_label"])
        w.writerow(["product", "name", "", ctx["product"].name, "USER INPUT"])
        w.writerow(["product", "category", "", a.category, "INFERENCE"])
        w.writerow(["objective", a.objective, "", a.objective_rationale[:180], "INFERENCE"])
        for k, v in (a.audience or {}).get("age_weights", {}).items():
            w.writerow(["audience", f"age {k}", "weight", round(v * 100, 1), "INFERENCE"])
        for v in ctx["videos"]:
            w.writerow(["competitor", v.title[:80], "views", v.views, v.data_source_label])
            w.writerow(["competitor", v.title[:80], "engagement_rate", v.engagement_rate, v.data_source_label])
        if rec:
            for al in rec.allocations:
                w.writerow(["allocation", al["label"], "share_pct", round(al["share"] * 100, 1), "MODEL PREDICTION"])
                w.writerow(["allocation", al["label"], "amount", al["amount"], "MODEL PREDICTION"])
                w.writerow(["allocation", al["label"], "predicted_conversions", al["predicted"].get("conversions"), "MODEL PREDICTION"])
                w.writerow(["allocation", al["label"], "predicted_roas", al["predicted"].get("roas"), "MODEL PREDICTION"])
            for k, v in (rec.predicted_totals or {}).items():
                w.writerow(["predicted_totals", "", k, v, "MODEL PREDICTION"])
    return out_path


def generate_report(db: Session, analysis: ProductAnalysis, fmt: str, out_dir: str | Path) -> tuple[Path, str]:
    out_dir = Path(out_dir) / "reports"
    base = f"adpilot_report_analysis{analysis.id}"
    if fmt == "pdf":
        path = generate_pdf(db, analysis, out_dir / f"{base}.pdf")
    elif fmt in ("xlsx", "excel"):
        path = generate_excel(db, analysis, out_dir / f"{base}.xlsx")
        fmt = "xlsx"
    elif fmt == "csv":
        path = generate_csv(db, analysis, out_dir / f"{base}.csv")
    else:
        raise ValueError(f"unsupported report format {fmt}")
    return path, fmt
