"""Build the downloadable PDF report for one prediction."""
from io import BytesIO

from reportlab.graphics.shapes import Drawing, Path as ShapePath, PolyLine
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from utils.timefmt import format_dt, now_local, to_local

RED = colors.HexColor("#B91C1C")
INK = colors.HexColor("#1F1A1C")
MUTED = colors.HexColor("#5B4F53")
LINE = colors.HexColor("#EADCDC")
SOFT = colors.HexColor("#FDECEC")

LEVEL_COLORS = {
    "Low": colors.HexColor("#15803D"),
    "Moderate": colors.HexColor("#B45309"),
    "Moderate–High": colors.HexColor("#C2410C"),
    "High": RED,
}


def _safe(text):
    """The built-in PDF fonts lack a few symbols, so swap them out."""
    return str(text).replace("≥", ">=").replace("≤", "<=")


def _logo(size=16 * mm):
    """Red heart with a white ECG line, drawn as vector shapes."""
    scale = size / 34
    d = Drawing(size, size * 31 / 34)
    heart = ShapePath(fillColor=RED, strokeColor=None)
    # Heart outline (y axis flipped compared to SVG).
    heart.moveTo(17, 1)
    heart.curveTo(7, 8.5, 1, 14.5, 1, 21.5)
    heart.curveTo(1, 27, 9, 30, 17, 25)
    heart.curveTo(25, 30, 33, 27, 33, 21.5)
    heart.curveTo(33, 14.5, 27, 8.5, 17, 1)
    heart.closePath()
    ecg = PolyLine([3.5, 16, 11, 16, 13.5, 21, 16.5, 10, 19.5, 18.5, 21.5, 16, 30.5, 16],
                   strokeColor=colors.white, strokeWidth=2.2, strokeLineJoin=1,
                   strokeLineCap=1)
    for shape in (heart, ecg):
        d.add(shape)
    d.scale(scale, scale)
    d.width, d.height = size, size * 31 / 34
    return d


def report_id(prediction):
    return f"CS-{prediction['created_at'][:4]}-{prediction['id']:06d}"


def build_report(prediction, email, zone_name=None):
    """Return the PDF as bytes. Times are shown in the user's timezone."""
    p, i = prediction, prediction["inputs"]
    assessed = to_local(p["created_at"], zone_name)
    generated = now_local(zone_name)
    rid = report_id(p)
    level_color = LEVEL_COLORS.get(p["label"], RED)

    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, textColor=INK, leading=24)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, textColor=INK, leading=15)
    muted = ParagraphStyle("muted", parent=body, textColor=MUTED, fontSize=9.5, leading=13)
    big = ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=40, leading=44, textColor=level_color)
    label = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=14, textColor=level_color)
    right = ParagraphStyle("right", parent=body, fontSize=9.5, leading=13, alignment=2)

    header = Table(
        [[_logo(), Paragraph('CardioSense <font color="#B91C1C">AI</font>', title),
          Paragraph(f"<b>Heart Risk Assessment Report</b><br/>Report ID: {rid}", right)]],
        colWidths=[20 * mm, 90 * mm, 60 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, LINE),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
    ]))

    flags = ", ".join(_safe(f) for f in p["flags"]) or "No major warning signs"
    risk_box = Table(
        [[Paragraph(f"{p['risk']:.0f}%", big),
          [Paragraph(f"{_safe(p['label'])} risk", label), Spacer(1, 4),
           Paragraph(f"<b>Key factors:</b> {flags}", body)]]],
        colWidths=[45 * mm, 125 * mm],
    )
    risk_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    rows = [
        ["Age", f"{i['age']:.0f} years"],
        ["Gender", i["gender"].capitalize()],
        ["Blood pressure", f"{i['systolic']:.0f} / {i['diastolic']:.0f} mm Hg"],
        ["Cholesterol", f"{i['cholesterol']:.0f} mg/dl"],
        ["Glucose", f"{i['glucose']:.0f} mg/dl"],
        ["Height / Weight", f"{i['height']:.0f} cm / {i['weight']} kg"],
        ["BMI", f"{p['bmi']}"],
        ["Smoking", "Yes" if i["smoke"] else "No"],
        ["Alcohol", "Yes" if i["alcohol"] else "No"],
        ["Physical activity", i["activity"].capitalize()],
    ]
    values = Table([[Paragraph(a, muted), Paragraph(b, body)] for a, b in rows],
                   colWidths=[55 * mm, 115 * mm])
    values.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    zone_label = getattr(assessed.tzinfo, "key", str(assessed.tzinfo))
    details_rows = [
        ["Report ID", rid],
        ["Assessment date & time", format_dt(assessed)],
        ["Report generated", format_dt(generated)],
        ["Time zone", zone_label],
        ["Prepared for", email],
        ["Input method", "Manual entry" if p["source"] == "manual"
                         else "Uploaded blood report (values confirmed by user)"],
    ]
    details = Table([[Paragraph(a, muted), Paragraph(b, body)] for a, b in details_rows],
                    colWidths=[55 * mm, 115 * mm])
    details.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 10 * mm,
                          f"CardioSense AI  |  {rid}  |  Generated {format_dt(generated)}")
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    story = [
        header, Spacer(1, 14),
        Paragraph("Report details", h2), details,
        Paragraph("Predicted cardiovascular risk", h2), risk_box,
        Paragraph("Your values", h2), values,
        Spacer(1, 16),
        Paragraph(
            "<b>Important:</b> This report is a risk estimate from a machine-learning model "
            "(Random Forest, about 73% accuracy on test data). It is guidance, not a diagnosis. "
            "Please discuss your results with a healthcare professional.", muted),
    ]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=22 * mm,
                            title="CardioSense AI heart risk report", author="CardioSense AI")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
