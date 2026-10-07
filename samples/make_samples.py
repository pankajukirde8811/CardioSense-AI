"""Create fake blood reports for testing the upload feature.

Run:  python samples/make_samples.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
LINES = [
    ("SAMPLE CITY LAB  -  TEST REPORT (FICTIONAL)", True),
    ("Patient: Test Person        Age: 54 years      Sex: Male", False),
    ("Height: 172 cm              Weight: 86 kg", False),
    ("Blood Pressure: 150/95 mmHg", False),
    ("", False),
    ("Test                         Result      Unit      Reference", True),
    ("Total Cholesterol            245         mg/dL     < 200", False),
    ("HDL Cholesterol              42          mg/dL     > 40", False),
    ("LDL Cholesterol              160         mg/dL     < 130", False),
    ("Fasting Glucose              105         mg/dL     70 - 99", False),
    ("", False),
    ("This is a fictional report made for testing CardioSense AI.", False),
]


def make_pdf(path):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for text, bold in LINES:
        c.setFont("Courier-Bold" if bold else "Courier", 11)
        c.drawString(50, y, text)
        y -= 22
    c.save()


def make_photo(path):
    image = Image.new("RGB", (1400, 700), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 28)
    except OSError:
        font = ImageFont.load_default(size=28)
    y = 40
    for text, _bold in LINES:
        draw.text((40, y), text, fill="black", font=font)
        y += 48
    image.save(path)


if __name__ == "__main__":
    make_pdf(HERE / "sample_blood_report.pdf")
    make_photo(HERE / "sample_blood_report.png")
    print("Created sample_blood_report.pdf and sample_blood_report.png in", HERE)
