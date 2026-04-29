"""
Metric Clustering — assigns a cluster label to each evidence row based on metric_id.

6 clusters:
  core_epi     → Core Epidemiology      (incidence, prevalence, mortality, rates)
  outcomes     → Patient Outcomes       (survival, median age, sex ratio)
  stage        → Stage Distribution     (stage I-IV, Rai, localized/regional/distant, subtypes)
  treatment    → Treatment & LOT        (LOT cascade, disease course, treatment lines)
  demographics → Age & Demographics     (age <65, 65-74, 75+)
  biomarker    → Biomarkers & Genomics  (IGHV, HER2, BRCA, PSMA, PDL1)

Usage:
    from src.pipeline.clustering import assign_clusters
    evidence_df = assign_clusters(evidence_df, config_dir=Path("config/"))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Human-readable labels for cluster IDs
CLUSTER_LABELS: dict[str, str] = {
    "core_epi":     "Core Epidemiology",
    "outcomes":     "Patient Outcomes",
    "stage":        "Stage Distribution",
    "treatment":    "Treatment & LOT",
    "demographics": "Age & Demographics",
    "biomarker":    "Biomarkers & Genomics",
    "unknown":      "Other / Unclassified",
}

_DEFAULT_CLUSTER = "unknown"

# Pattern-based fallback rules (checked in order when exact lookup fails).
# Each tuple is (keyword_substring, cluster_id).  First match wins.
_PATTERN_RULES: list[tuple[str, str]] = [
    # ── Biomarkers first (specific keywords trump broader ones) ──
    ("ighv", "biomarker"),
    ("tp53", "biomarker"),
    ("del17p", "biomarker"),
    ("her2", "biomarker"),
    ("pdl1", "biomarker"),
    ("pd_l1", "biomarker"),
    ("brca", "biomarker"),
    ("hrr", "biomarker"),
    ("psma", "biomarker"),
    ("msi_h", "biomarker"),
    ("kras", "biomarker"),
    ("nras", "biomarker"),
    ("braf", "biomarker"),
    ("atm_", "biomarker"),
    ("birc3", "biomarker"),
    ("cd38_", "biomarker"),
    ("hrd_", "biomarker"),
    ("beta2_micro", "biomarker"),
    # ── Stage / histology ──
    ("_stage_", "stage"),
    ("rai_", "stage"),
    ("pct_binet_", "stage"),
    ("pct_rai_", "stage"),
    ("pct_diagnosed_distant", "stage"),
    ("pct_diagnosed_regional", "stage"),
    ("pct_diagnosed_localized", "stage"),
    ("subtype_", "stage"),
    ("histology_", "stage"),
    ("risk_low", "stage"),
    ("risk_intermediate", "stage"),
    ("risk_high", "stage"),
    ("pct_advanced_stage", "stage"),
    ("localized_pct", "stage"),
    ("regional_pct", "stage"),
    ("distant_pct", "stage"),
    # ── Age & Demographics ──
    ("age_distribution_", "demographics"),
    ("age_lt65", "demographics"),
    ("age_65_", "demographics"),
    ("age_75", "demographics"),
    ("_under_65", "demographics"),
    ("_65_plus", "demographics"),
    ("_75_plus", "demographics"),
    ("pediatric", "demographics"),
    ("geriatric", "demographics"),
    # ── Treatment & LOT ──
    ("first_line", "treatment"),
    ("second_line", "treatment"),
    ("third_line", "treatment"),
    ("fourth_line", "treatment"),
    ("relapsed_refractory", "treatment"),
    ("watch_wait", "treatment"),
    ("active_surveillance", "treatment"),
    ("lot_", "treatment"),
    ("cascade_", "treatment"),
    ("parp_", "treatment"),
    ("platinum_", "treatment"),
    ("debulking", "treatment"),
    ("bcr_adt", "treatment"),
    ("mcspc", "treatment"),
    ("mcrpc", "treatment"),
    ("crpc", "treatment"),
    ("maintenance", "treatment"),
    ("salvage", "treatment"),
    ("palliative", "treatment"),
    ("treatment_watch", "treatment"),
    ("treatment_active_", "treatment"),
    ("pct_requiring_first_line", "treatment"),
    ("pct_relapsed", "treatment"),
    ("disease_course", "treatment"),
    ("disease_indolent", "treatment"),
    ("disease_progress", "treatment"),
    ("disease_recurrent", "treatment"),
    ("disease_chronic", "treatment"),
    # ── Patient Outcomes ──
    ("five_year_survival", "outcomes"),
    ("survival_localized", "outcomes"),
    ("survival_regional", "outcomes"),
    ("survival_distant", "outcomes"),
    ("median_age", "outcomes"),
    ("male_female_ratio", "outcomes"),
    ("sex_ratio", "outcomes"),
    ("conditional_", "outcomes"),
    ("aapc_survival", "outcomes"),
    # ── Core Epidemiology (broad — must come after more specific patterns) ──
    ("incidence", "core_epi"),
    ("prevalence", "core_epi"),
    ("mortality", "core_epi"),
    ("aapc_", "core_epi"),
]


def _load_cluster_map(config_dir: Path, clusters_file: str = "metric_clusters.yaml") -> dict[str, str]:
    """
    Load metric_clusters.yaml and invert it to metric_id → cluster_id.
    Returns dict like {"incidence": "core_epi", "rai_stage_0_pct": "stage", ...}.
    """
    path = Path(config_dir) / clusters_file
    if not path.exists():
        logger.warning(f"Cluster config not found: {path}. All rows will be 'unknown'.")
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load cluster config {path}: {e}")
        return {}

    # Invert: cluster_id → [metric_ids]  to  metric_id → cluster_id
    metric_to_cluster: dict[str, str] = {}
    for cluster_id, metric_ids in raw.items():
        if not isinstance(metric_ids, list):
            continue
        for mid in metric_ids:
            metric_to_cluster[str(mid).strip()] = cluster_id

    logger.debug(f"Loaded cluster map: {len(metric_to_cluster)} metric_id → cluster_id entries")
    return metric_to_cluster


def _resolve_metric_col(evidence_df: pd.DataFrame) -> Optional[str]:
    """Find the metric column name (metric_id or metric)."""
    for col in ("metric_id", "metric"):
        if col in evidence_df.columns:
            return col
    return None


def assign_clusters(
    evidence_df: pd.DataFrame,
    config_dir: Optional[Path] = None,
    clusters_file: str = "metric_clusters.yaml",
    overwrite: bool = False,
) -> pd.DataFrame:
    """
    Add a 'cluster' column to evidence_df by looking up each row's metric_id.

    Args:
        evidence_df:   Input DataFrame with at least a 'metric_id' or 'metric' column.
        config_dir:    Directory containing metric_clusters.yaml.
                       Defaults to <project_root>/config/.
        clusters_file: Name of the clusters config file.
        overwrite:     If True, overwrite existing 'cluster' column. Default False.

    Returns:
        DataFrame with 'cluster' (str) and 'cluster_label' (str) columns added.
    """
    if evidence_df.empty:
        evidence_df = evidence_df.copy()
        evidence_df["cluster"] = pd.Series(dtype="object")
        evidence_df["cluster_label"] = pd.Series(dtype="object")
        return evidence_df

    if "cluster" in evidence_df.columns and not overwrite:
        logger.debug("'cluster' column already present; skipping (set overwrite=True to force)")
        return evidence_df

    if config_dir is None:
        config_dir = Path(__file__).resolve().parents[2] / "config"

    metric_to_cluster = _load_cluster_map(config_dir, clusters_file)

    metric_col = _resolve_metric_col(evidence_df)
    if metric_col is None:
        logger.warning("No 'metric_id' or 'metric' column found. Setting all clusters to 'unknown'.")
        df = evidence_df.copy()
        df["cluster"] = _DEFAULT_CLUSTER
        df["cluster_label"] = CLUSTER_LABELS[_DEFAULT_CLUSTER]
        return df

    df = evidence_df.copy()

    def _lookup_cluster(metric_id) -> str:
        if metric_id is None or (isinstance(metric_id, float) and pd.isna(metric_id)):
            return _DEFAULT_CLUSTER
        mid = str(metric_id).strip()
        if not mid:
            return _DEFAULT_CLUSTER
        # 1. Direct lookup
        if mid in metric_to_cluster:
            return metric_to_cluster[mid]
        # 2. Try stripping indication prefix (e.g. "cll_rai_stage_0_pct" → "rai_stage_0_pct")
        parts = mid.split("_", 1)
        if len(parts) == 2 and parts[1] in metric_to_cluster:
            return metric_to_cluster[parts[1]]
        # 3. Pattern-based fallback (keyword substring matching)
        mid_lower = mid.lower()
        for keyword, cluster_id in _PATTERN_RULES:
            if keyword in mid_lower:
                return cluster_id
        return _DEFAULT_CLUSTER

    df["cluster"] = df[metric_col].apply(_lookup_cluster)
    df["cluster_label"] = df["cluster"].map(CLUSTER_LABELS).fillna(CLUSTER_LABELS[_DEFAULT_CLUSTER])

    # Summary log
    cluster_counts = df["cluster"].value_counts().to_dict()
    logger.info(f"Cluster assignment complete: {cluster_counts}")

    return df


def get_cluster_summary(evidence_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a summary DataFrame of cluster coverage per indication.

    Columns: indication, cluster, cluster_label, count, pct_of_indication
    """
    if evidence_df.empty or "cluster" not in evidence_df.columns:
        return pd.DataFrame()

    ind_col = "indication" if "indication" in evidence_df.columns else None
    if ind_col is None:
        # No indication column: single-indication mode
        summary = evidence_df["cluster"].value_counts().reset_index()
        summary.columns = ["cluster", "count"]
        summary["cluster_label"] = summary["cluster"].map(CLUSTER_LABELS)
        return summary

    grouped = evidence_df.groupby([ind_col, "cluster"]).size().reset_index(name="count")
    ind_totals = evidence_df.groupby(ind_col).size().reset_index(name="total")
    grouped = grouped.merge(ind_totals, on=ind_col)
    grouped["pct_of_indication"] = (grouped["count"] / grouped["total"] * 100).round(1)
    grouped["cluster_label"] = grouped["cluster"].map(CLUSTER_LABELS)
    return grouped[[ind_col, "cluster", "cluster_label", "count", "pct_of_indication"]].sort_values(
        [ind_col, "count"], ascending=[True, False]
    )
