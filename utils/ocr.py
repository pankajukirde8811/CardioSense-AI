"""Read a blood report (PDF or photo) and pull out the values we need."""
import re
import shutil
import sys
from pathlib import Path

import pdfplumber
import pytesseract
from PIL import Image, ImageOps

# On Windows, Tesseract is often installed but not on the PATH.
if sys.platform == "win32" and not shutil.which("tesseract"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def _ocr_image(image):
    image = ImageOps.exif_transpose(image).convert("L")
    if image.width < 1500:  # small photos read better when enlarged
        factor = 1500 / image.width
        image = image.resize((1500, int(image.height * factor)))
    return pytesseract.image_to_string(image)


def extract_text(path):
    """Return (text, method). Uses the PDF's own text first, OCR as fallback."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages[:5]
            text = "\n".join(page.extract_text() or "" for page in pages)
            if len(text.strip()) > 40:
                return text, "pdf-text"
            # Scanned PDF: turn each page into an image and OCR it.
            text = "\n".join(_ocr_image(page.to_image(resolution=300).original) for page in pages)
            return text, "ocr"
    with Image.open(path) as image:
        return _ocr_image(image), "ocr"


NUMBER = r"(\d{1,3}(?:[.,]\d{1,2})?)"
UNIT = r"\s*(mg\s*/\s*d[lL]|mmol\s*/\s*[lL])?"


def _find(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match
    return None


def _to_float(raw):
    return float(raw.replace(",", "."))


def parse_values(text):
    """Find cholesterol, glucose, BP, and other fields in report text."""
    found = {}

    # Total cholesterol (mg/dl, or mmol/l x 38.67).
    m = _find([
        r"total\s+cholesterol[^\d\n]{0,25}" + NUMBER + UNIT,
        r"cholesterol,?\s+total[^\d\n]{0,25}" + NUMBER + UNIT,
        r"(?<!hdl )(?<!ldl )(?<!hdl-)(?<!ldl-)cholesterol[^\d\n]{0,25}" + NUMBER + UNIT,
    ], text)
    if m:
        value = _to_float(m.group(1))
        unit = (m.group(2) or "").lower()
        if "mmol" in unit or value < 20:
            value *= 38.67
        found["cholesterol"] = round(value)

    # Fasting glucose / blood sugar (mg/dl, or mmol/l x 18).
    m = _find([
        r"fasting\s+(?:blood\s+)?(?:glucose|sugar)[^\d\n]{0,25}" + NUMBER + UNIT,
        r"(?:blood\s+)?glucose[^\d\n]{0,25}" + NUMBER + UNIT,
        r"blood\s+sugar[^\d\n]{0,25}" + NUMBER + UNIT,
    ], text)
    if m:
        value = _to_float(m.group(1))
        unit = (m.group(2) or "").lower()
        if "mmol" in unit or value < 30:
            value *= 18
        found["glucose"] = round(value)

    # Blood pressure like "BP 140/90" or "Blood pressure: 140 / 90 mmHg".
    m = _find([r"(?:blood\s+pressure|\bB\.?P\.?)[^\d\n]{0,20}(\d{2,3})\s*/\s*(\d{2,3})"], text)
    if m:
        found["systolic"], found["diastolic"] = int(m.group(1)), int(m.group(2))

    m = _find([r"\bage[^\d\n]{0,10}(\d{2})\b"], text)
    if m:
        found["age"] = int(m.group(1))

    m = _find([r"\b(?:sex|gender)[^A-Za-z\n]{0,5}(male|female|m|f)\b"], text)
    if m:
        found["gender"] = "female" if m.group(1).lower().startswith("f") else "male"

    m = _find([r"height[^\d\n]{0,15}(\d{3})\s*cm"], text)
    if m:
        found["height"] = int(m.group(1))

    m = _find([r"weight[^\d\n]{0,15}" + NUMBER + r"\s*kg"], text)
    if m:
        found["weight"] = _to_float(m.group(1))

    return found
