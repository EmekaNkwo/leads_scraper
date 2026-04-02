from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from scraper_config import AppConfig
from scraper_enrichment import enrich_from_websites
from scraper_exporters import append_master_csv, export_csv, export_json
from scraper_maps import scrape_query
from scraper_models import LeadRecord
from scraper_utils import (
    archive_old_exports,
    checkpoint_path,
    compute_confidence,
    load_checkpoint,
    save_checkpoint,
    setup_logger,
    slugify,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Maps leads scraper")
    parser.add_argument("--config", default="scraper_config.json", help="Path to JSON config")
    parser.add_argument("--queries", nargs="*", help="Override query list")
    parser.add_argument("--max-results", type=int, help="MAX_RESULTS_PER_QUERY")
    parser.add_argument("--max-scrolls", type=int, help="MAX_SCROLLS_PER_QUERY")
    parser.add_argument("--max-runtime-seconds", type=int, help="Optional MAX_RUNTIME_SECONDS")
    parser.add_argument("--output-dir", help="Directory for CSV/JSON output")
    parser.add_argument("--show-browser", action="store_true", help="Run with visible browser")
    parser.add_argument("--no-enrich", action="store_true", help="Disable website enrichment pass")
    parser.add_argument("--no-json", action="store_true", help="Disable JSON export")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint if available")
    return parser.parse_args()


def resolve_config(args: argparse.Namespace) -> AppConfig:
    cfg = AppConfig.from_file(args.config)
    if args.queries:
        cfg.queries = args.queries
    if args.max_results is not None:
        cfg.max_results_per_query = args.max_results
    if args.max_scrolls is not None:
        cfg.max_scrolls_per_query = args.max_scrolls
    if args.max_runtime_seconds is not None:
        cfg.max_runtime_seconds = args.max_runtime_seconds
    if args.output_dir:
        cfg.output_dir = args.output_dir
    if args.show_browser:
        cfg.headless = False
    if args.no_enrich:
        cfg.enrich_websites = False
    if args.no_json:
        cfg.export_json = False
    return cfg


def run_query(
    query: str,
    cfg: AppConfig,
    output_dir: Path,
    checkpoints_dir: Path,
    logger,
    resume: bool,
) -> tuple[list[LeadRecord], float, Path]:
    started = time.time()
    run_at = datetime.now()
    checkpoint_file = checkpoint_path(checkpoints_dir, query)
    existing: list[LeadRecord] = []
    if resume:
        _, existing = load_checkpoint(checkpoint_file, query)
        if existing:
            logger.info("Loaded %s leads from checkpoint for query '%s'", len(existing), query)

    leads = scrape_query(
        query=query,
        max_results=max(cfg.max_results_per_query - len(existing), 0),
        max_scrolls=cfg.max_scrolls_per_query,
        max_runtime_seconds=cfg.max_runtime_seconds,
        headless=cfg.headless,
    )
    all_leads = existing + leads

    if cfg.enrich_websites:
        enrich_from_websites(all_leads)

    for lead in all_leads:
        lead.confidence_score = compute_confidence(lead)
        if not lead.scraped_at:
            lead.scraped_at = run_at.strftime("%Y-%m-%d %H:%M:%S")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = run_at.strftime("%Y-%m-%d_%I-%M-%S%p").lower()
    query_slug = slugify(query)
    csv_path = output_dir / f"leads_{query_slug}_{timestamp}.csv"
    export_csv(all_leads, csv_path)
    append_master_csv(all_leads, output_dir / "master_leads.csv")
    if cfg.export_json:
        export_json(all_leads, output_dir / f"leads_{query_slug}_{timestamp}.json")

    save_checkpoint(checkpoint_file, all_leads, len(all_leads))
    elapsed = time.time() - started
    return all_leads, elapsed, csv_path


def main() -> None:
    args = parse_args()
    cfg = resolve_config(args)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(cfg.output_dir)
    checkpoints_dir = Path(cfg.checkpoint_dir)
    logger = setup_logger(Path(cfg.logs_dir), run_id)
    archive_old_exports(output_dir, cfg.archive_after_days)

    total_leads = 0
    total_enriched_email = 0
    total_with_website = 0
    failures = 0

    for query in cfg.queries:
        try:
            leads, elapsed, csv_path = run_query(
                query=query,
                cfg=cfg,
                output_dir=output_dir,
                checkpoints_dir=checkpoints_dir,
                logger=logger,
                resume=args.resume,
            )
            query_emails = sum(1 for x in leads if x.email != "N/A")
            query_websites = sum(1 for x in leads if x.website != "N/A")
            total_leads += len(leads)
            total_enriched_email += query_emails
            total_with_website += query_websites
            logger.info(
                "query=%s leads=%s emails=%s websites=%s output=%s elapsed=%.1fs",
                query,
                len(leads),
                query_emails,
                query_websites,
                csv_path,
                elapsed,
            )
            print(
                f"Success: data fetched for '{query}' ({len(leads)} leads) "
                f"and CSV exported to {csv_path} in {elapsed:.1f}s."
            )
        except Exception as exc:
            failures += 1
            logger.exception("Query failed: %s", query)
            print(f"Failed query '{query}': {exc}")

    print(
        "Run summary: "
        f"total_leads={total_leads}, "
        f"emails_found={total_enriched_email}, "
        f"websites_found={total_with_website}, "
        f"failures={failures}"
    )


if __name__ == "__main__":
    main()