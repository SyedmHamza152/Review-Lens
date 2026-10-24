"""CSV and PDF report export."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Review, SearchJob


def export_csv(db: Session, job_id: str) -> tuple[str, str]:
    """Returns (filename, csv_content) for analyzed (non-spam) reviews."""
    job = db.query(SearchJob).get(job_id)
    rows = db.query(Review).filter_by(job_id=job_id, is_spam=False).order_by(Review.id).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "review_id", "platform", "language", "language_confidence",
        "sentiment", "sentiment_score", "sentiment_confidence",
        "complaint_scope", "aspects", "rating", "review_date", "variant",
        "original_comment", "english_gloss", "data_source", "source_url",
    ])
    for r in rows:
        try:
            aspects = "; ".join(
                f"{m.get('aspect')}:{m.get('label')}" for m in json.loads(r.aspects_json or "[]"))
        except json.JSONDecodeError:
            aspects = ""
        writer.writerow([
            r.id, r.platform, r.language, r.language_confidence,
            r.sentiment, r.sentiment_score, r.sentiment_confidence,
            r.complaint_scope, aspects, r.rating or "",
            r.review_date.strftime("%Y-%m-%d") if r.review_date else "",
            r.variant or "", r.text_original, r.translation or "",
            r.data_source, r.source_url or "",
        ])
    safe = "".join(c for c in (job.product_name if job else "report") if c.isalnum())[:40]
    stamp = datetime.now().strftime("%Y%m%d")
    return f"review_intel_{safe}_{stamp}.csv", buf.getvalue()


def export_pdf(db: Session, job_id: str, report: dict) -> tuple[str, bytes]:
    """Complete product report PDF (reportlab)."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    job = db.query(SearchJob).get(job_id)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Title"], fontSize=20, spaceAfter=2)
    sub_style = ParagraphStyle("S", parent=styles["Normal"], alignment=TA_CENTER,
                               textColor=colors.HexColor("#64748b"), fontSize=9)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13,
                        spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#0f766e"))
    body = ParagraphStyle("B", parent=styles["Normal"], fontSize=9.5, leading=13)

    v = report["verdict"]
    t = report["totals"]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Product Review Intelligence Report - {job.product_name}")
    story = []

    story.append(Paragraph("Product Review Intelligence Report", title_style))
    story.append(Paragraph(f"{job.product_name} &nbsp;|&nbsp; generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", sub_style))
    story.append(Spacer(1, 6))
    if report["job"].get("data_mode") in ("sample", "mixed"):
        story.append(Paragraph(
            "<b>DATA NOTICE:</b> this report includes clearly-labelled SAMPLE data "
            "(synthetic demonstration comments) because live platform APIs were not "
            "accessible. Sample data is never presented as real collected reviews.",
            ParagraphStyle("warn", parent=body, textColor=colors.HexColor("#b45309"))))
        story.append(Spacer(1, 4))

    story.append(Paragraph("Overall Verdict", h2))
    story.append(Paragraph(
        f"<b>{v['label']}</b> - overall sentiment score {v['score']}/100 from "
        f"{t['analyzed']} analyzed comments across {t['platforms_with_data']} platform(s). "
        f"Positive {v['positive_pct']}%, negative {v['negative_pct']}%, "
        f"neutral {v['neutral_pct']}%, mixed {v['mixed_pct']}%. {v['methodology_note']}",
        body))

    story.append(Paragraph("AI Summary", h2))
    story.append(Paragraph(report["summary"], body))

    story.append(Paragraph("Platform Comparison", h2))
    comp_rows = [["Platform", "N", "Pos%", "Neg%", "Neu%", "Mix%", "Avg rating", "Data"]]
    for c in report["comparison"]:
        comp_rows.append([
            c["platform_name"], str(c["total"]), f"{c['positive_pct']}",
            f"{c['negative_pct']}", f"{c['neutral_pct']}", f"{c['mixed_pct']}",
            str(c["avg_rating"]) if c["avg_rating"] is not None else "-",
            "SAMPLE" if c["is_sample"] else "live",
        ])
    tbl = Table(comp_rows, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
    ]))
    story.append(tbl)
    story.append(Paragraph(
        "Note: percentages reflect the collected sample only; low-sample platforms "
        "(marked in the dashboard) are not meaningful for ranking.", body))

    story.append(Paragraph("Most Discussed Aspects", h2))
    asp_rows = [["Aspect", "Scope", "Mentions", "Pos", "Neg", "Neu", "Mixed", "Avg polarity"]]
    for a in report["aspects"][:11]:
        asp_rows.append([a["label"], a["scope"], str(a["mentions"]), str(a["positive"]),
                         str(a["negative"]), str(a["neutral"]), str(a["mixed"]),
                         f"{a['avg_polarity']:+.2f}"])
    tbl2 = Table(asp_rows, hAlign="LEFT")
    tbl2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
    ]))
    story.append(tbl2)

    if report["advantages"]:
        story.append(Paragraph("Top Advantages Mentioned", h2))
        story.append(Paragraph(
            "<br/>".join(f"- {a['phrase']} ({a['count']}x)" for a in report["advantages"]), body))
    if report["complaints"]:
        story.append(Paragraph("Top Complaints Mentioned", h2))
        story.append(Paragraph(
            "<br/>".join(f"- {c['phrase']} ({c['count']}x)" for c in report["complaints"]), body))

    story.append(Paragraph("Platform Coverage & Integration Status", h2))
    cov_rows = [["Platform", "Status", "Items", "Message"]]
    for s in report["platform_statuses"]:
        cov_rows.append([s["platform_name"], s["status"], str(s["items_collected"]),
                         Paragraph((s["message"] or "")[:200], ParagraphStyle("m", parent=body, fontSize=7.5, leading=9.5))])
    tbl3 = Table(cov_rows, colWidths=[70, 62, 34, 330], hAlign="LEFT")
    tbl3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tbl3)

    story.append(Paragraph("Methodology & Disclaimers", h2))
    m = report["methodology"]
    story.append(Paragraph(
        f"Pipeline: {m['nlp_pipeline']}. {m['scoring']} {m['mixed_rule']} "
        f"Minimum sample for a verdict: {m['min_sample_for_verdict']} comments. "
        + " ".join(m["disclaimers"]), body))

    doc.build(story)
    safe = "".join(c for c in job.product_name if c.isalnum())[:40]
    stamp = datetime.now().strftime("%Y%m%d")
    return f"review_intel_{safe}_{stamp}.pdf", buffer.getvalue()
