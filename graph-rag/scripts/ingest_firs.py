#!/usr/bin/env python3
"""CLI to ingest the Bengaluru FIR JSON into Neo4j.

Usage:
    python scripts/ingest_firs.py --input ../data/bengaluru_40ps_1000_firs.json

The JSON must be of the form: {"firs": [ {...}, ... ]}
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.config import settings
from app.ingest.pipeline import run_ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest_firs")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FIR JSON into Neo4j graph")
    parser.add_argument(
        "--input",
        default="../data/bengaluru_40ps_1000_firs.json",
        help="Path to the FIR JSON file (default: ../data/bengaluru_40ps_1000_firs.json)",
    )
    args = parser.parse_args()

    # Resolve relative to this script's directory
    script_dir = Path(__file__).parent
    input_path = (script_dir / args.input).resolve()
    if not input_path.is_file():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    logger.info("Starting ingest from %s", input_path)
    result = await run_ingest(str(input_path))
    logger.info(
        "Ingest finished: total=%d processed=%d skipped=%d",
        result["total"],
        result["processed"],
        result["skipped"],
    )


if __name__ == "__main__":
    asyncio.run(main())