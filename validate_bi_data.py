#!/usr/bin/env python3
"""
Standalone BI_Data schema validator.

Usage:
    python3 validate_bi_data.py                    # checks output/ per-indication files
    python3 validate_bi_data.py --file <path.csv>  # checks a specific evidence CSV

Checks for:
  - Required evidence columns (indication, metric, value, source_citation, source_tier)
  - cluster / cluster_label columns present and ≥80% populated
  - Tier values valid (gold / silver / bronze)
  - No duplicate metric/year/geography keys
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.evidence_finder.validation import validate_evidence_df, validate_bi_data_df

OUTPUT_DIR = Path(__file__).parent / "output"
INDICATION_SLUGS = ["CLL", "Hodgkin", "Non-Hodgkin_Lymphoma", "Gastric", "Ovarian", "Prostate"]


def check_file(csv_path: Path) -> tuple[bool, str]:
    """Run both validators on a single CSV. Returns (passed, summary_line)."""
    if not csv_path.exists():
        return False, f"❌ FILE NOT FOUND: {csv_path.name}"

    df = pd.read_csv(csv_path)
    ok1, r1 = validate_evidence_df(df)
    ok2, r2 = validate_bi_data_df(df)
    all_entries = r1 + r2
    errors   = [x for x in all_entries if x["level"] == "error"]
    warnings = [x for x in all_entries if x["level"] == "warning"]

    cluster_fill = ""
    if "cluster" in df.columns:
        pct = df["cluster"].notna().mean() * 100
        cluster_fill = f" | cluster {pct:.0f}% filled"

    detail_lines = []
    for e in errors:
        detail_lines.append(f"     ❌ [{e['code']}] {e['message']}")
    for w in warnings:
        detail_lines.append(f"     ⚠️  [{w['code']}] {w['message']}")

    name = csv_path.name
    if errors:
        summary = f"❌ {name}  ({len(df):,} rows{cluster_fill})"
    elif warnings:
        summary = f"⚠️  {name}  ({len(df):,} rows{cluster_fill})"
    else:
        summary = f"✅ {name}  ({len(df):,} rows{cluster_fill})"

    return not bool(errors), "\n".join([summary] + detail_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bi_data / evidence CSV schema.")
    parser.add_argument("--file", type=Path, default=None,
                        help="Path to a single evidence CSV to validate")
    args = parser.parse_args()

    if args.file:
        # Single-file mode
        ok, line = check_file(args.file)
        print(line)
        print()
        print("✅ ALL CHECKS PASSED" if ok else "❌ CHECKS FAILED — review issues above")
        return 0 if ok else 1

    # Default: scan output/ per-indication files
    print(f"Scanning output files in: {OUTPUT_DIR}\n")
    any_failure = False

    for slug in INDICATION_SLUGS:
        # Try both naming patterns
        candidates = list(OUTPUT_DIR.glob(f"evidence_by_metric_{slug}_US.csv"))
        if not candidates:
            candidates = list(OUTPUT_DIR.glob(f"evidence_by_metric_{slug}*_US.csv"))
        if not candidates:
            print(f"⚠️  No file found for {slug}")
            continue
        for csv_path in sorted(candidates):
            ok, line = check_file(csv_path)
            if not ok:
                any_failure = True
            print(line)

    print()
    if any_failure:
        print("❌ SOME CHECKS FAILED — review issues above")
        return 1
    else:
        print("✅ ALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
