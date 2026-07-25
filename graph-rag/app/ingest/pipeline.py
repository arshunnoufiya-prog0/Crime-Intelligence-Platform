"""Ingest pipeline orchestrator: reads the JSON file, batches records,
calls fir_loader, prints progress every 100 records.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

from ..config import settings
from .fir_loader import load_batch
from .ocr_loader import extract_text_from_pdf

logger = logging.getLogger("graph-rag.ingest.pipeline")


async def run_ingest(json_path: str) -> Dict[str, int]:
    """Main entry point used by scripts/ingest_firs.py and API endpoint."""
    path = Path(json_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"FIR JSON not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    firs = data.get("firs") or data.get("data") or []
    if not isinstance(firs, list):
        raise ValueError("JSON must contain a top-level 'firs' list")

    total = len(firs)
    logger.info("Starting ingest of %d FIRs from %s", total, path)

    processed = 0
    skipped = 0

    for i in range(0, total, 100):
        batch = firs[i : i + 100]
        try:
            count = await load_batch(batch)
            processed += count
        except Exception as exc:  # noqa: BLE001
            logger.exception("Batch %d-%d failed: %s", i, i + len(batch), exc)
            skipped += len(batch)
        if processed % 100 == 0 or processed + skipped >= total:
            logger.info("Progress: %d/%d processed, %d skipped", processed, total, skipped)

    return {"total": total, "processed": processed, "skipped": skipped}


async def run_ingest_with_ocr(json_path: str, pdf_dir: str | None = None) -> Dict[str, int]:
    """Variant that pre-processes PDFs if OCR is enabled."""
    if not settings.enable_ocr or not pdf_dir:
        return await run_ingest(json_path)

    # OCR path: expect each FIR to have a matching PDF in pdf_dir/<fir_id>.pdf
    # For each, extract text and inject into the FIR record before normal ingest.
    # This is a placeholder — actual matching logic depends on naming convention.
    logger.info("OCR-enabled ingest not yet implemented; falling back to standard ingest")
    return await run_ingest(json_path)