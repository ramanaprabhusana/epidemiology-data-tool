#!/usr/bin/env python3
"""
Batch runner: executes the Data Pipeline for all 6 indications
(CLL, Hodgkin Lymphoma, Non-Hodgkin Lymphoma, Gastric, Ovarian, Prostate)
and optionally patches the Client-presentation workbook (Lookup Tables + Evidence sheets).

NOTE: DLBCL is not a standalone indication; it is reported as a subtype inside NHL
(full Non-Hodgkin Lymphoma, including DLBCL in totals and subtype mix).

Usage:
    # Run for all 6 indications with country US, produce SQLite + CSV + consolidated Excel
    python run_all_indications.py

    # Explicit control
    python run_all_indications.py --country US --workbook "../Client presentation/Integrated_Client_Delivery_Sandbox/Epidemiology_Forecast_Model_Client_Hub_v5.xlsx"

    # Skip workbook patch (just refresh pipeline outputs)
    python run_all_indications.py --no-workbook-patch

    # Run for a subset
    python run_all_indications.py --indications CLL "Hodgkin Lymphoma"

    # Skip PubMed (faster batch; default is PubMed on)
    python run_all_indications.py --no-pubmed

Outputs:
    output/<indication>_<country>/...                 per-indication CSVs, tool-ready tables, KPI scorecard
    output/dashboard/epidemiology_dashboard.db        SQLite (Tableau data source)
    output/dashboard/*.csv                            dashboard CSVs (fallback)
    output/consolidated_run.xlsx                      aggregated Excel with one sheet per indication
    output/run_manifest.json                          run metadata (for Pipeline Metadata sheet)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# Resolve paths relative to this script
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR  # run_all_indications.py lives at pipeline repo root

# Make src importable
sys.path.insert(0, str(_REPO_ROOT))

from src.pipeline.runner import run_pipeline  # noqa: E402


# Indication → config suffix mapping (matches config/ui_options.yaml)
# Accepts both short forms and SEER-style labels.
INDICATION_SUFFIX = {
    "CLL":                   "cll",
    "Hodgkin Lymphoma":      "hodgkin",
    "Hodgkin":               "hodgkin",
    "Non-Hodgkin Lymphoma":  "nhl",
    "Non-Hodgkin":           "nhl",
    "NHL":                   "nhl",
    "Gastric":               "gc",
    "Ovarian":               "ovarian",
    "Prostate":              "prostate",
}

DEFAULT_INDICATIONS = [
    "CLL",
    "Hodgkin Lymphoma",
    "Non-Hodgkin Lymphoma",
    "Gastric",
    "Ovarian",
    "Prostate",
]
DEFAULT_WORKBOOK_REL = "../Client presentation/Integrated_Client_Delivery_Sandbox/Epidemiology_Forecast_Model_Client_Hub_v5.xlsx"
DEFAULT_V6_WORKBOOK_REL = "../Client presentation/Integrated_Client_Delivery_Sandbox/Epidemiology_Forecast_Model_Client_Hub_v6.xlsx"


def _sha256_of_file(path: Path) -> str:
    """SHA-256 hex digest of a file (for Pipeline Metadata checksum column)."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]  # first 16 chars is enough for display


def run_one(indication: str, country: str, output_dir: Path, config_dir: Path,
            use_pubmed: bool = True) -> Dict[str, Any]:
    """Run the pipeline for one indication. Returns per-indication result dict."""
    started = time.time()
    print(f"\n{'=' * 60}\n► {indication}  ({country})\n{'=' * 60}")

    suffix = INDICATION_SUFFIX.get(indication)
    metrics_config = config_dir / f"required_metrics_{suffix}.yaml" if suffix else None
    if metrics_config and not metrics_config.exists():
        print(f"  [warn] missing {metrics_config}; runner will fall back to default")
        metrics_config = None

    try:
        result = run_pipeline(
            indication=indication,
            country=country,
            config_dir=config_dir,
            output_dir=output_dir,
            metrics_config_path=metrics_config,
            export_dashboard=True,
            include_forecast=True,
            use_pubmed=use_pubmed,
            add_pubmed_stubs=use_pubmed,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.time() - started
        print(f"  [ERROR] {type(exc).__name__}: {exc}")
        return {
            "indication": indication,
            "country": country,
            "success": False,
            "message": f"{type(exc).__name__}: {exc}",
            "elapsed_sec": round(elapsed, 1),
            "paths": {},
            "record_count": 0,
        }

    elapsed = time.time() - started
    print(f"  ✓ {indication} done in {elapsed:.1f}s  ({result.get('record_count', 0)} records)")
    if not result.get("success"):
        print(f"  [warn] {result.get('message')}")

    return {
        "indication": indication,
        "country": country,
        "success": bool(result.get("success")),
        "message": result.get("message", ""),
        "elapsed_sec": round(elapsed, 1),
        "paths": result.get("paths", {}),
        "record_count": result.get("record_count", 0),
        "validation_passed": result.get("validation_passed", True),
    }


def build_consolidated_excel(results: List[Dict[str, Any]], output_path: Path) -> None:
    """Aggregate each indication's KPI scorecard + evidence into a single Excel file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Cover sheet
        cover = pd.DataFrame(
            [
                {
                    "Indication": r["indication"],
                    "Country": r["country"],
                    "Success": r["success"],
                    "Records": r["record_count"],
                    "Elapsed (s)": r["elapsed_sec"],
                    "Message": r["message"][:100] if r["message"] else "",
                }
                for r in results
            ]
        )
        cover.to_excel(writer, sheet_name="Run Summary", index=False)

        for r in results:
            if not r["success"]:
                continue
            ind = r["indication"]
            for key, path in r["paths"].items():
                if not path or not str(path).lower().endswith(".csv"):
                    continue
                p = Path(path)
                if not p.exists():
                    continue
                # Only pull the most presentation-worthy CSVs
                if key not in {"evidence", "kpi_scorecard", "insightace_epi", "forecast"}:
                    continue
                try:
                    df = pd.read_csv(p, encoding="utf-8")
                except Exception:
                    continue
                sheet_name = f"{ind}_{key}"[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)


def build_manifest(results: List[Dict[str, Any]], workbook_path: Path | None) -> Dict[str, Any]:
    """Produce a manifest dict that refresh_workbook.py writes into Pipeline Metadata."""
    return {
        "pipeline_version": "v1.0",
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_user": __import__("os").environ.get("USER") or __import__("os").environ.get("USERNAME") or "unknown",
        "workbook_target": str(workbook_path) if workbook_path else None,
        "indications": [
            {
                "indication": r["indication"],
                "country": r["country"],
                "success": r["success"],
                "record_count": r["record_count"],
                "elapsed_sec": r["elapsed_sec"],
                "checksums": {
                    k: _sha256_of_file(Path(v))
                    for k, v in r["paths"].items()
                    if v and Path(v).exists() and k in {"evidence", "kpi_scorecard", "forecast"}
                },
            }
            for r in results
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Data Pipeline for all 6 indications and aggregate outputs.")
    parser.add_argument("--indications", nargs="+", default=DEFAULT_INDICATIONS,
                        help="Indications to run (default: all 6)")
    parser.add_argument("--country", default="US", help="Country/geography (default: US)")
    parser.add_argument("--config-dir", type=Path, default=_REPO_ROOT / "config",
                        help="Config directory containing required_metrics_*.yaml")
    parser.add_argument("--output-dir", type=Path, default=_REPO_ROOT / "output",
                        help="Output directory")
    parser.add_argument("--workbook", type=Path, default=_REPO_ROOT / DEFAULT_WORKBOOK_REL,
                        help="Path to the v5.2 workbook to patch")
    parser.add_argument("--no-workbook-patch", action="store_true",
                        help="Skip patching the workbook - just produce pipeline outputs")
    parser.add_argument(
        "--no-pubmed",
        action="store_true",
        help="Skip PubMed for each indication (default: PubMed on; faster batch or offline)",
    )
    parser.add_argument("--consolidated-excel-name", default="consolidated_run.xlsx",
                        help="Filename under output/ for the aggregated Excel")
    parser.add_argument("--update-excel", action="store_true", default=False,
                        help="After pipeline run, write best-value metrics back to Excel v6 via excel_updater.py")
    parser.add_argument("--v6-workbook", type=Path, default=_REPO_ROOT / DEFAULT_V6_WORKBOOK_REL,
                        help="Path to the v6 one-stop Excel workbook (target of --update-excel)")
    args = parser.parse_args()

    results: List[Dict[str, Any]] = []
    for ind in args.indications:
        if ind not in INDICATION_SUFFIX:
            print(f"  [warn] unknown indication '{ind}' - skipping")
            continue
        results.append(
            run_one(
                indication=ind,
                country=args.country,
                output_dir=args.output_dir,
                config_dir=args.config_dir,
                use_pubmed=not args.no_pubmed,
            )
        )

    # Consolidated Excel
    consolidated_path = args.output_dir / args.consolidated_excel_name
    print(f"\nBuilding consolidated Excel: {consolidated_path}")
    try:
        build_consolidated_excel(results, consolidated_path)
        print(f"  ✓ {consolidated_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] consolidated Excel failed: {exc}")

    # Manifest
    manifest_path = args.output_dir / "run_manifest.json"
    workbook_path = None if args.no_workbook_patch else args.workbook.resolve()
    manifest = build_manifest(results, workbook_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  ✓ manifest → {manifest_path}")

    # Workbook patch
    if not args.no_workbook_patch and args.workbook.exists():
        print(f"\nPatching workbook: {args.workbook}")
        try:
            from refresh_workbook import patch_workbook  # local sibling import
            patch_workbook(args.workbook, manifest, results)
            print("  ✓ workbook patched (Lookup Tables + Evidence + Pipeline Metadata)")
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] workbook patch skipped: {exc}")
    elif not args.no_workbook_patch:
        print(f"  [warn] workbook not found at {args.workbook}; skipping patch")

    # Excel v6 auto-population (optional)
    if args.update_excel:
        v6_path = args.v6_workbook.resolve()
        if v6_path.exists():
            print(f"\nUpdating Excel v6: {v6_path}")
            try:
                from src.pipeline.excel_updater import update_excel_from_pipeline
                changes = update_excel_from_pipeline(
                    kpi_csv_dir=args.output_dir,
                    excel_path=v6_path,
                    indications=args.indications,
                    dry_run=False,
                )
                print(f"  ✓ Excel v6 updated: {len(changes)} metrics written")
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] Excel v6 update failed: {exc}")
        else:
            print(f"  [warn] v6 workbook not found at {v6_path}; skipping Excel update")

    # Summary
    succeeded = sum(1 for r in results if r["success"])
    print(f"\n{'=' * 60}\nSummary: {succeeded}/{len(results)} indications succeeded\n{'=' * 60}")
    return 0 if succeeded == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
