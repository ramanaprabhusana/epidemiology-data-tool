#!/usr/bin/env python3
"""
Main CLI for Evidence Finder + Data Builder. Run for an indication and optional country.
Usage:
  python run_tool.py --indication CLL --country US
  python run_tool.py --indication "Lung Cancer" --dashboard
  python run_tool.py --indication EXAMPLE --no-dashboard
"""

import argparse
from pathlib import Path

from src.pipeline.runner import run_pipeline


def _path(s: str) -> Path:
    return Path(s).resolve()


def main():
    parser = argparse.ArgumentParser(
        description="Run Evidence Finder + Data Builder for an indication and optional country.",
    )
    parser.add_argument("--indication", type=str, default="CLL", help="Indication (e.g. CLL, Lung Cancer, Example)")
    parser.add_argument("--country", type=str, default=None, help="Country/geography (e.g. US, UK); tags evidence and output filenames")
    parser.add_argument("--evidence", type=_path, default=None, help="Path to evidence CSV (optional)")
    parser.add_argument("--config-dir", type=_path, default=None, help="Config directory")
    parser.add_argument("--output-dir", type=_path, default=None, help="Output directory")
    parser.add_argument("--metrics-config", type=_path, default=None, help="Required metrics YAML path")
    parser.add_argument("--dashboard", action="store_true", default=True, help="Export dashboard layer (default: True)")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip dashboard export")
    parser.add_argument("--no-forecast", action="store_true", help="Skip forecast table when exporting dashboard")
    parser.add_argument(
        "--no-pubmed",
        action="store_true",
        help="Skip PubMed API calls (faster/offline; default is PubMed on with stub rows)",
    )
    args = parser.parse_args()

    export_dashboard = args.dashboard and not args.no_dashboard
    use_pubmed = not args.no_pubmed
    result = run_pipeline(
        indication=args.indication,
        country=args.country,
        evidence_path=args.evidence,
        config_dir=args.config_dir,
        output_dir=args.output_dir,
        metrics_config_path=args.metrics_config,
        export_dashboard=export_dashboard,
        include_forecast=not args.no_forecast,
        use_pubmed=use_pubmed,
        add_pubmed_stubs=use_pubmed,
    )

    if result["success"]:
        for k, v in result.get("paths", {}).items():
            print(f"  {k}: {v}")
        print(result["message"])
    else:
        print(result["message"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
