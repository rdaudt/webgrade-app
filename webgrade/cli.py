from __future__ import annotations

import argparse
from pathlib import Path
import sys

from webgrade.config import load_settings
from webgrade.pipeline import run_batch
from webgrade.types import RunOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="webgrade")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a WebGrade batch")
    run_parser.add_argument("--input", type=Path, help="Path to input CSV.")
    run_parser.add_argument("--output", type=Path, default=Path("./webgrade-output"), help="Output directory.")
    run_parser.add_argument("--limit", type=int, help="Process only the first N rows.")
    run_parser.add_argument("--skip-vision", action="store_true", help="Skip GPT-5.4 vision scoring.")
    run_parser.add_argument("--skip-screenshots", action="store_true", help="Skip screenshot capture.")
    run_parser.add_argument("--only-vision", action="store_true", help="Reuse existing screenshots and rerun vision only.")
    run_parser.add_argument("--site", help="Run against a single URL.")
    run_parser.add_argument("--report-name", help="Override the report name for a single-site run.")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.input is None and not args.site:
        raise ValueError("--input is required unless --site is used")
    if args.only_vision and args.skip_vision:
        raise ValueError("--only-vision cannot be combined with --skip-vision")
    if args.only_vision and args.skip_screenshots:
        raise ValueError("--only-vision cannot be combined with --skip-screenshots")
    if args.report_name and not args.site:
        raise ValueError("--report-name can only be used with --site")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be greater than zero")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_args(args)
        options = RunOptions(
            input_path=args.input,
            output_dir=args.output,
            limit=args.limit,
            skip_vision=args.skip_vision,
            skip_screenshots=args.skip_screenshots,
            only_vision=args.only_vision,
            site=args.site,
            report_name=args.report_name,
        )
        settings = load_settings(args.output)
        summary = run_batch(settings, options)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Batch {summary.batch_id} finished with status: {summary.status}")
    print(f"Sites processed: {summary.total_sites}")
    print(f"Sites complete: {summary.complete_sites}")
    print(f"Sites partial: {summary.partial_sites}")
    print(f"Sites failed: {summary.failed_sites}")
    print(f"Output directory: {summary.batch_dir}")
    return 0
