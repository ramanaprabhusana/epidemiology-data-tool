"""
One-pager evidence summary per indication: key numbers, confidence, top sources, gaps, caveats.
Output: Markdown (can be exported to PDF via browser or pandoc).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _is_stub_value(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    s = str(value).strip().lower()
    return "see link" in s or s == "" or s == "nan"


def _extract_first_numeric(value: Any) -> Optional[float]:
    import re
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s or _is_stub_value(value):
        return None
    match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+|\d+)", s.replace(" ", ""))
    if not match:
        return None
    try:
        num = float(match.group(1).replace(",", ""))
        if 1e-2 <= num <= 1e8 or (0 < num < 1 and "." in match.group(1)):
            return num
        if 1900 <= num <= 2030:
            return None
        return num
    except (ValueError, TypeError):
        return None


def generate_evidence_summary_md(
    indication: str,
    geography: str,
    evidence_df: pd.DataFrame,
    scorecard_df: Optional[pd.DataFrame] = None,
    white_space_summary: Optional[str] = None,
    top_n_sources: int = 5,
) -> str:
    """
    Generate one-page markdown summary: key numbers, confidence, top sources, gaps, caveats.
    """
    lines = [
        f"# Evidence summary: {indication}",
        f"**Geography:** {geography}",
        "",
        "---",
        "",
    ]
    # Key numbers (from scorecard or evidence)
    lines.append("## Key numbers")
    lines.append("")
    if scorecard_df is not None and not scorecard_df.empty:
        for _, r in scorecard_df[scorecard_df["best_value"] != ""].iterrows():
            lines.append(f"- **{r['label']}:** {r['best_value']} (source: {r['best_source']}, status: {r['validation_status']})")
        if scorecard_df[scorecard_df["best_value"] != ""].empty:
            lines.append("- No best values from scorecard; see evidence table for raw extractions.")
    else:
        # Fallback: from evidence, pick first numeric per metric
        seen_metric = set()
        for _, r in evidence_df.iterrows():
            mid = r.get("metric", "")
            if mid in seen_metric:
                continue
            num = _extract_first_numeric(r.get("value"))
            if num is not None:
                seen_metric.add(mid)
                lines.append(f"- **{mid}:** {num} (source: {r.get('source_citation', '')})")
        if not seen_metric:
            lines.append("- No extracted numeric values in evidence table.")
    lines.append("")

    # Confidence (if computed)
    if evidence_df is not None and not evidence_df.empty:
        conf_col = "computed_confidence" if "computed_confidence" in evidence_df.columns else "confidence"
        if conf_col in evidence_df.columns:
            dist = evidence_df[conf_col].fillna("").astype(str).str.lower().value_counts()
            lines.append("## Confidence (evidence rows)")
            lines.append("")
            for label, count in dist.items():
                if label:
                    lines.append(f"- {label.capitalize()}: {count} row(s)")
            lines.append("")

    # Top sources
    lines.append("## Top sources used")
    lines.append("")
    if evidence_df is not None and not evidence_df.empty:
        top_sources = evidence_df["source_citation"].value_counts().head(top_n_sources)
        for src, count in top_sources.items():
            lines.append(f"- {src}: {count} row(s)")
    else:
        lines.append("- No evidence data.")
    lines.append("")

    # Gaps (white-space)
    lines.append("## Gaps (white-space)")
    lines.append("")
    if white_space_summary:
        # Use the summary section only (after "## Summary")
        for line in white_space_summary.split("\n"):
            if line.strip().startswith("- ") or line.strip().startswith("**"):
                lines.append(line)
    else:
        lines.append("- Run white-space analysis for gap details.")
    lines.append("")

    # Caveats
    lines.append("## Caveats")
    lines.append("")
    if scorecard_df is not None and not scorecard_df.empty:
        needs_review = scorecard_df[scorecard_df["validation_status"] == "Needs review"]
        no_source = scorecard_df[scorecard_df["validation_status"] == "No source"]
        if not needs_review.empty:
            lines.append("- The following metrics need review (multiple sources or low confidence):")
            for _, r in needs_review.iterrows():
                lines.append(f"  - {r['label']}: {r.get('agreement_flag', '')}")
        if not no_source.empty:
            lines.append("- No source in current run for: " + ", ".join(no_source["label"].astype(str).tolist()) + ".")
        if needs_review.empty and no_source.empty:
            lines.append("- No major caveats; all metrics have at least one Ready or high-confidence source.")
    else:
        lines.append("- Review evidence table and KPI scorecard for caveats.")
    lines.append("")
    lines.append("---")
    lines.append("*Generated by Epidemiology Evidence Pack. Source-backed; no AI-generated numbers.*")
    return "\n".join(lines)


def export_evidence_summary(
    content_md: str,
    output_path: Path,
) -> None:
    """Write summary markdown to file. User can open in browser and print to PDF."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content_md, encoding="utf-8")
