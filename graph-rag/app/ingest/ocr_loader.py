"""OPTIONAL OCR loader — only imported/used when settings.enable_ocr is True.

Extracts text from scanned FIR PDFs via pdf2image + pytesseract before they
enter fir_loader. The rest of the pipeline (Cypher templates, intent schema,
NetworkX analysis) works identically whether OCR is enabled or not.

Guards all imports so the service starts fine with zero OCR dependencies.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..config import settings

logger = logging.getLogger("graph-rag.ingest.ocr_loader")


def _enabled() -> bool:
    return getattr(settings, "enable_ocr", False)


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """Return concatenated text from all pages of the PDF, or None if OCR disabled/fails."""
    if not _enabled():
        return None
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR dependencies not available: %s", exc)
        return None

    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as exc:  # noqa: BLE001
        logger.error("pdf2image failed on %s: %s", pdf_path, exc)
        return None

    texts = []
    for img in images:
        try:
            texts.append(pytesseract.image_to_string(img, lang="eng"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("tesseract page OCR failed: %s", exc)
    return "\n\n".join(texts)


def extract_text_from_image(image_path: str) -> Optional[str]:
    if not _enabled():
        return None
    try:
        import pytesseract
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR deps missing: %s", exc)
        return None
    try:
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang="eng")
    except Exception as exc:  # noqa: BLE001
        logger.error("image OCR failed on %s: %s", image_path, exc)
        return None