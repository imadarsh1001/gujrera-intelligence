"""Extract text and metadata from PDF files using pypdf or stdlib fallback."""

import io
import re
import zlib
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


COMMON_LEGAL_MARKERS = {
    "the", "and", "for", "project", "date", "rera", "cost", "gujarat", "total", "form",
    "bank", "plot", "survey", "city", "taluka", "district", "area", "unit", "completion",
    "building", "office", "name", "road", "state", "india", "flat", "lakhs", "crores",
    "approval", "permission", "plan", "layout", "shree", "llp", "pvt", "ltd", "limited",
    "developer", "promoter", "gujrera", "architect", "engineer", "ca", "account", "ifsc",
    "balance", "incurred", "estimated", "quarter", "year", "work", "done", "percentage",
    "certificate", "registration", "title", "clearance", "encumbrance", "mortgage", "loan",
}


def sanitize_pdf_page_text(text: str) -> str:
    """Sanitize extracted PDF text, removing unprintable binary CAD/bitmap artifacts."""
    if not text:
        return ""

    # Strip raw binary control bytes and raster 0xFF byte-masks
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\xff]", " ", text)
    cleaned = re.sub(r"([^\w\s])\1{4,}", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    stripped = cleaned.strip()

    if len(stripped) < 15:
        return ""

    # Check for presence of real language vocabulary
    words = set(w.lower() for w in re.findall(r"\b[a-zA-Z]{2,15}\b", stripped[:10000]))
    if len(stripped) > 200 and len(words & COMMON_LEGAL_MARKERS) < 2:
        # Long page without recognizable regulatory/legal vocabulary is a CAD raster dump
        return ""

    # Cap each page at 25,000 characters
    return stripped[:25000].strip()


def extract_pages_pypdf(file_bytes: bytes) -> List[Tuple[int, str]]:
    """Extract page text using pypdf."""
    pages = []
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    for idx, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
            clean = sanitize_pdf_page_text(text)
            if clean:
                pages.append((idx, clean))
        except Exception:
            pass
    return pages


def extract_pages_stdlib(file_bytes: bytes) -> List[Tuple[int, str]]:
    """Fallback standard-library text extraction from uncompressed PDF streams."""
    pages = []
    # Identify decompressed streams with text operators
    text_chunks = []
    for match in re.finditer(rb"stream[\r\n]+(.*?)[\r\n]+endstream", file_bytes, re.DOTALL):
        stream_raw = match.group(1)
        try:
            decomp = zlib.decompress(stream_raw)
            for tmatch in re.finditer(rb"\((.*?)\)", decomp):
                chunk = tmatch.group(1).decode("latin1", errors="ignore").strip()
                if len(chunk) > 1 and not chunk.startswith("/"):
                    text_chunks.append(chunk)
        except Exception:
            pass

    if text_chunks:
        # Group into single synthesized document page
        full_text = " ".join(text_chunks)
        clean = sanitize_pdf_page_text(full_text)
        if clean:
            pages.append((1, clean))
    return pages


def extract_pdf_pages(file_path: Path) -> List[Tuple[int, str]]:
    """Extract page-indexed text from a PDF file."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return []

    raw = file_path.read_bytes()
    if not raw.startswith(b"%PDF-"):
        return []

    if HAS_PYPDF:
        try:
            pages = extract_pages_pypdf(raw)
            if pages:
                return pages
        except Exception:
            pass

    return extract_pages_stdlib(raw)


def classify_document_type(json_path: str, request_key: str, file_name: str) -> str:
    """Classify the semantic role of a document from its request and json_path."""
    key = (request_key + " " + json_path).lower()
    if "form_one" in key or "formone" in key:
        return "form_one_architect"
    if "form_two" in key or "formtwo" in key:
        return "form_two_engineer"
    if "form_three" in key or "formthree" in key:
        return "form_three_ca"
    if "annual_compliance" in key or "form_five" in key:
        return "form_five_annual_audit"
    if "form_four" in key:
        return "form_four_completion"
    if "noc_bu" in key or "budoc" in key or "bupdf" in key:
        return "bu_permission_noc"
    if "titlereport" in key:
        return "title_search_report"
    if "titleclearance" in key:
        return "title_clearance_certificate"
    if "buildingplan" in key:
        return "approved_building_plan"
    if "layoutplan" in key:
        return "approved_layout_plan"
    if "encumbrance" in key:
        return "encumbrance_certificate"
    if "agreement" in key:
        return "sale_agreement_proforma"
    if "loan" in key:
        return "loan_sanction_or_charge"
    if "passbook" in key or "banks" in key:
        return "bank_escrow_passbook"
    return "other_regulatory_doc"
