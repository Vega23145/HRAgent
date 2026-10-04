"""
Attachment bytes -> plain text.

Extraction strategy per format
───────────────────────────────
.tex / .latex   strip LaTeX commands, return plain text
.pdf            pypdf text layer first; if too short, fall back to OCR (pytesseract)
.docx           python-docx paragraphs + tables (unchanged)

OCR fallback requires:
    pip install pytesseract pillow pdf2image
    + system packages: tesseract-ocr  poppler-utils
Set OCR_LANG env var to override the Tesseract language pack (default: "eng").
"""
import io
import logging
import os
import re
from pathlib import Path

from .config import MIN_TEXT_CHARS
from .mail import Attachment

log = logging.getLogger(__name__)

OCR_LANG = os.environ.get("OCR_LANG", "eng")


# ── LaTeX ─────────────────────────────────────────────────────────
def _read_latex(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")

    # strip \begin{document}…\end{document} wrapper but keep the body
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.S)
    if m:
        text = m.group(1)

    # remove common formatting commands whose argument we want to keep
    for cmd in ("textbf", "textit", "emph", "underline", "textrm",
                "texttt", "textsc", "mbox", "hbox", "href"):
        text = re.sub(rf"\\{cmd}\{{([^{{}}]*)\}}", r"\1", text)

    # remove commands with optional + mandatory args we don't need
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])*\{[^{}]*\}", " ", text)
    # remove bare commands
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    # remove remaining braces and special chars
    text = re.sub(r"[{}%]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── OCR ───────────────────────────────────────────────────────────
def _ocr_pdf(payload: bytes) -> str:
    """Rasterise each PDF page and run Tesseract on it."""
    from pdf2image import convert_from_bytes  # poppler-utils required
    import pytesseract

    images = convert_from_bytes(payload, dpi=300)
    pages = tuple(pytesseract.image_to_string(image=img, lang=OCR_LANG) for img in images) # memory optimize list => tuple
    return "\n".join(pages)

    
# ── PDF (text layer + OCR fallback) ───────────────────────────────
def _read_pdf(payload: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    if len(text.strip()) >= MIN_TEXT_CHARS:
        return text

    log.info("PDF text layer too short (%d chars), falling back to OCR", len(text.strip()))
    try:
        return _ocr_pdf(payload)
    except ImportError:
        log.warning("OCR deps not installed (pip install pytesseract pillow pdf2image); returning raw text")
        return text


# ── public entry point ─────────────────────────────────────────────
def read_text(att: Attachment) -> str:
    ext = Path(att.filename).suffix.lower()

    if ext == ".pdf":
        return _read_pdf(att.payload)

    if ext in (".tex", ".latex"):
        return _read_latex(att.payload)

    if ext == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(att.payload))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.extend(c.text for c in row.cells)
        return "\n".join(parts)

    raise ValueError(f"unsupported attachment type: {att.filename}")