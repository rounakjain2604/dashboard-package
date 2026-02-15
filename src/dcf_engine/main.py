"""
CLI entry point for the IB-Grade DCF Engine.

Usage:
    python -m src.dcf_engine.main --ticker AAPL --output output/aapl_dcf.xlsx
    python -m src.dcf_engine.main --file data/company.csv --output output/dcf.xlsx
    python -m src.dcf_engine.main --config config.json --output output/dcf.xlsx --pdf output/memo.pdf
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import DCFEngineConfig
from .pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dcf_engine")


def main():
    parser = argparse.ArgumentParser(
        description="IB-Grade Automated DCF Model Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ticker", type=str, help="Company ticker (for SEC EDGAR / market data)")
    parser.add_argument("--file", type=str, help="Path to historical financials CSV/XLSX")
    parser.add_argument("--config", type=str, help="Path to JSON config file")
    parser.add_argument("--output", type=str, required=True, help="Output Excel file path")
    parser.add_argument("--pdf", type=str, default=None, help="Output PDF memo path")
    parser.add_argument("--revenue", type=float, default=1_000_000, help="Base year revenue")
    parser.add_argument("--cash", type=float, default=50_000, help="Base year cash")
    parser.add_argument("--ppe", type=float, default=200_000, help="Base year PP&E")
    parser.add_argument("--nwc", type=float, default=0, help="Base year NWC")
    parser.add_argument("--retained-earnings", type=float, default=0, help="Base retained earnings")
    parser.add_argument("--common-stock", type=float, default=100_000, help="Base common stock")
    parser.add_argument("--quiet", action="store_true", help="Suppress info output")
    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # ── Load config ──────────────────────────────────────────────────
    if args.config:
        logger.info("Loading config from %s", args.config)
        cfg = DCFEngineConfig.from_json(args.config)
    else:
        cfg = DCFEngineConfig()

    # Override company info from CLI
    if args.ticker:
        cfg.company.ticker = args.ticker
        if not cfg.company.name or cfg.company.name == "Target Company":
            cfg.company.name = args.ticker

    # ── Load historical data ─────────────────────────────────────────
    historical = None
    if args.file:
        import pandas as pd
        fpath = Path(args.file)
        if fpath.suffix.lower() == ".csv":
            historical = pd.read_csv(fpath)
        elif fpath.suffix.lower() in (".xlsx", ".xls"):
            historical = pd.read_excel(fpath)
        else:
            logger.warning("Unsupported file format: %s", fpath.suffix)
        if historical is not None:
            logger.info("Loaded %d rows from %s", len(historical), fpath)

    # ── Run pipeline ─────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("IB-Grade DCF Engine — %s", cfg.company.name)
    logger.info("=" * 60)

    result = run_pipeline(
        cfg=cfg,
        historical=historical,
        base_year_revenue=args.revenue,
        base_cash=args.cash,
        base_ppe=args.ppe,
        base_nwc=args.nwc,
        base_retained_earnings=args.retained_earnings,
        base_common_stock=args.common_stock,
        output_excel=args.output,
        output_pdf=args.pdf,
    )

    # ── Report ───────────────────────────────────────────────────────
    logger.info("=" * 60)
    if result.excel_path:
        logger.info("✓ Excel: %s", result.excel_path)
    if result.pdf_path:
        logger.info("✓ PDF:   %s", result.pdf_path)
    if result.dcf:
        logger.info("✓ Equity Value (Blended): %s", f"{result.dcf.equity_blended:,.0f}")
        logger.info("✓ Price/Share (Blended):  $%s", f"{result.dcf.price_blended:.2f}")
    if result.errors:
        logger.warning("⚠ %d errors encountered:", len(result.errors))
        for err in result.errors:
            logger.warning("  → %s", err)
    else:
        logger.info("✓ No errors")
    logger.info("=" * 60)

    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(main())
