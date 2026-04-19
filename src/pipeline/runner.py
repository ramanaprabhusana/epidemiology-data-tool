"""
Pipeline runner: one function to run the full data pipeline (evidence -> tool-ready -> KPI -> optional dashboard).
Accepts indication, country, paths; returns result dict with paths, success, and optional data for UI preview.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from ..evidence_finder.sources import collect_from_multiple_levels
from ..evidence_finder.collector import write_source_log, export_evidence_by_metric
from ..data_builder.builder import (
    load_evidence_table,
    build_tool_ready_table,
    export_tool_ready,
    export_insightace_epidemiology,
    build_scenario_registry,
    build_insightace_epidemiology_table,
    load_scenario_options,
)
from ..repository.scorecard import load_required_metrics
from ..repository.reconciliation import compute_conflicts
from ..repository.confidence import add_computed_confidence, export_rubric as export_confidence_rubric
from ..repository.scorecard import build_kpi_scorecard, export_kpi_scorecard
from ..repository.white_space import (
    build_coverage_matrix,
    build_white_space_summary,
    export_white_space as export_white_space_files,
)
from ..repository.reconciliation import build_reconciliation_table, export_reconciliation
from ..repository.evidence_summary import generate_evidence_summary_md, export_evidence_summary


def _safe_name(s: str) -> str:
    return s.replace(" ", "_").replace(",", "").strip() or "unknown"


def _excel_sheet_name(path: Path, key: str) -> str:
    """Return a valid Excel sheet name (max 31 chars, no : \\ / ? * [ ])."""
    s = key.replace("-", "_").strip()
    for c in ":\\/?*[]":
        s = s.replace(c, "")
    s = s[:31].strip() if s else "Sheet"
    return s or "Sheet"


def _consolidate_csvs_to_excel(paths: Dict[str, str], output_path: Path) -> None:
    """Write key CSV outputs from paths into a single Excel file. Skip redundant sheets."""
    # Only include these sheets (in order), skip redundant ones like tool_ready, scenario_registry
    INCLUDE_KEYS = [
        "evidence", "kpi_scorecard", "insightace_epi", "source_log",
        "reference_links", "validation_report", "forecast", "insights_summary",
    ]
    csv_items = [(k, Path(p)) for k, p in paths.items()
                 if p and str(p).lower().endswith(".csv") and k in INCLUDE_KEYS]
    # Sort by INCLUDE_KEYS order
    key_order = {k: i for i, k in enumerate(INCLUDE_KEYS)}
    csv_items.sort(key=lambda x: key_order.get(x[0], 99))
    if not csv_items:
        return
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        used = set()
        for key, p in csv_items:
            if not p.exists():
                continue
            sheet = _excel_sheet_name(p, key)
            base, n = sheet, 0
            while sheet in used:
                n += 1
                sheet = f"{base}_{n}"[:31]
            used.add(sheet)
            try:
                df = pd.read_csv(p, encoding="utf-8")
                df.to_excel(writer, sheet_name=sheet, index=False)
            except Exception:
                pass


def _add_year_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 'year' column (int or NaN) parsed from 'year_or_range' so which year's data is explicit.
    Keeps year_or_range as-is; year is the first 4-digit year when present (e.g. 2020 or 2018 from '2018-2022').
    """
    if df is None or df.empty:
        return df
    if "year_or_range" not in df.columns:
        df = df.copy()
        df["year"] = pd.NA
        return df
    def parse_year(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        if not s:
            return None
        try:
            # Take first token that looks like a 4-digit year
            for part in s.replace("-", " ").split():
                if len(part) >= 4 and part[:4].isdigit():
                    return int(part[:4])
        except (ValueError, TypeError):
            pass
        return None
    out = df.copy()
    out["year"] = df["year_or_range"].apply(parse_year)
    # Place year next to year_or_range for readability
    cols = list(out.columns)
    if "year_or_range" in cols and "year" in cols:
        cols.remove("year")
        idx = cols.index("year_or_range") + 1
        cols.insert(idx, "year")
        out = out[cols]
    return out


def run_pipeline(
    indication: str,
    country: Optional[str] = None,
    evidence_path: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    metrics_config_path: Optional[Path] = None,
    export_dashboard: bool = True,
    include_forecast: bool = True,
    validate_evidence: bool = True,
    strict_validation: bool = False,
    use_pubmed: bool = False,
    add_pubmed_stubs: bool = True,
    max_run_seconds: Optional[int] = 2400,  # 40 minutes default
) -> Dict[str, Any]:
    """
    Run the full pipeline for one indication and optional country.
    Returns dict with:
      success (bool), message (str), paths (dict), evidence_df, kpi_df, tool_ready_df,
      validation_report (list), validation_passed (bool).
    If validate_evidence=True, runs schema/tier validation; if strict_validation=True and
    validation has errors, pipeline stops and success=False.
    """
    root = Path(__file__).resolve().parents[2]
    config_dir = Path(config_dir or root / "config")
    output_dir = Path(output_dir or root / "output")
    templates_dir = root / "templates"

    ind_safe = _safe_name(indication)
    country_safe = _safe_name(country) if country else ""
    file_suffix = f"{ind_safe}_{country_safe}" if country_safe else ind_safe
    # avoid trailing underscore
    if file_suffix.endswith("_"):
        file_suffix = file_suffix[:-1]

    result = {
        "success": False,
        "message": "",
        "paths": {},
        "evidence_df": None,
        "kpi_df": None,
        "tool_ready_df": None,
        "record_count": 0,
        "validation_report": [],
        "validation_passed": True,
    }

    # Resolve evidence path (try indication-specific slug then known slugs)
    if evidence_path is None or not Path(evidence_path).exists():
        slug = ind_safe.lower().replace(" ", "_").replace("(", "").replace(")", "").strip("_")
        for try_slug in [slug, "cll", "lung_cancer", "example"]:
            candidate = templates_dir / f"evidence_{try_slug}.csv"
            if candidate.exists():
                evidence_path = candidate
                break
        if evidence_path is None or not Path(evidence_path).exists():
            evidence_path = templates_dir / "evidence_upload_template.csv"

    # Resolve metrics config (indication-specific file or default)
    if metrics_config_path is None or not Path(metrics_config_path).exists():
        slug = ind_safe.lower().replace(" ", "_").replace("(", "").replace(")", "")
        for suffix in [slug, "cll", "lung_cancer", "example"]:
            candidate = config_dir / f"required_metrics_{suffix}.yaml"
            if candidate.exists():
                metrics_config_path = candidate
                break
        if metrics_config_path is None or not Path(metrics_config_path).exists():
            metrics_config_path = config_dir / "required_metrics.yaml"

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Single dynamic connector: explores all sources in config/sources_to_explore.yaml (links + APIs)
        from ..evidence_finder.connectors.explore_all import explore_all_connector_factory
        connectors = {
            "bronze:Explore all": explore_all_connector_factory(),
        }
        connector_kwargs = {
            "country": country,
            "config_dir": config_dir,
            "use_pubmed": use_pubmed,
            "add_pubmed_stubs": add_pubmed_stubs,
            "max_deep_dive_links": 140,
        }
        if max_run_seconds is not None:
            connector_kwargs["max_run_seconds"] = max_run_seconds

        # 1) Multi-level source finder (with country and config for dynamic explorer)
        records, source_log = collect_from_multiple_levels(
            indication,
            config_dir,
            manual_evidence_path=evidence_path if Path(evidence_path).exists() else None,
            country=country,
            connectors=connectors,
            connector_kwargs=connector_kwargs,
        )
        # Filter out stub/empty rows and noisy web-scraped link rows
        # Reference_links CSV already captures source URLs separately
        def _is_low_quality(r):
            v = getattr(r, 'value', None)
            if not isinstance(v, str):
                return False
            vl = v.strip().lower()
            if 'see link' in vl or vl == '' or vl == 'nan':
                return True
            # Drop *_links metrics — these are noisy web scraping artifacts
            m = getattr(r, 'metric', '')
            if isinstance(m, str) and m.endswith('_links'):
                return True
            return False
        records = [r for r in records if not _is_low_quality(r)]
        # Single evidence file: sorted by metric (evidence_by_metric); used for all downstream steps
        evidence_path_out = output_dir / f"evidence_by_metric_{file_suffix}.csv"
        evidence_df_raw = pd.DataFrame([r.to_row() for r in records])
        export_evidence_by_metric(evidence_df_raw, evidence_path_out)
        result["paths"]["evidence"] = str(evidence_path_out)
        source_log_path = output_dir / f"source_log_{file_suffix}.csv"
        write_source_log(source_log, source_log_path)
        result["paths"]["source_log"] = str(source_log_path)
        # Reference links (all link-type sources) – no extracted value; user opens these to find data
        from ..evidence_finder.connectors.explore_all import build_reference_links
        reference_links = build_reference_links(config_dir, indication, country)
        if reference_links:
            ref_path = output_dir / f"reference_links_{file_suffix}.csv"
            pd.DataFrame(reference_links).to_csv(ref_path, index=False)
            result["paths"]["reference_links"] = str(ref_path)
        result["record_count"] = len(records)
        result["source_log"] = source_log
        result["sources_explored"] = sorted(
            {str(r.source_citation).strip() for r in records if getattr(r, "source_citation", None)}
        )
        # KPIs we collect for (from required_metrics / NCCN-aligned)
        try:
            required = load_required_metrics(metrics_config_path)
            result["kpi_labels"] = [m.get("label") or m.get("id", "") for m in required if m.get("id") or m.get("label")]
        except Exception:
            result["kpi_labels"] = ["Incidence", "Prevalence"]

        # Validation (optional; fail fast if strict and errors)
        if validate_evidence and records:
            from ..evidence_finder.validation import validate_evidence_df, export_validation_report
            evidence_df_check = pd.DataFrame([r.to_row() for r in records])
            val_ok, val_report = validate_evidence_df(evidence_df_check)
            result["validation_report"] = val_report
            result["validation_passed"] = val_ok
            # Persist validation report for audit trail (CSV only)
            val_path = export_validation_report(val_report, output_dir, file_suffix)
            result["paths"]["validation_report"] = str(val_path)
            if strict_validation and not val_ok:
                result["message"] = "Validation failed: " + "; ".join(
                    e["message"] for e in val_report if e.get("level") == "error"
                )
                return result

        if not records:
            result["message"] = "No evidence records. Add an evidence CSV and try again."
            return result

        # 2) Data Builder (scenario options from config)
        scenario_config = config_dir / "scenario_options.yaml"
        scenario_options, selected = load_scenario_options(scenario_config)
        scenario_path = output_dir / f"scenario_registry_{file_suffix}.csv"
        build_scenario_registry(scenario_options, scenario_path)
        result["paths"]["scenario_registry"] = str(scenario_path)
        evidence_df = load_evidence_table(evidence_path_out)
        evidence_df = _add_year_column(evidence_df)
        tool_rows = build_tool_ready_table(evidence_df, indication, selected)
        tool_path = output_dir / f"tool_ready_{file_suffix}.csv"
        export_tool_ready(tool_rows, tool_path)
        insightace_path = output_dir / f"insightace_epi_{file_suffix}.csv"
        export_insightace_epidemiology(tool_rows, insightace_path, scenario_label="High")
        result["paths"]["tool_ready"] = str(tool_path)
        result["paths"]["insightace_epi"] = str(insightace_path)

        # 3) Conflicts only (kpi_table dropped; scorecard built in 3b after confidence)
        conflicts_path = output_dir / f"kpi_conflicts_{file_suffix}.csv"
        conflicts = compute_conflicts(evidence_df)
        if conflicts:
            cdf = pd.DataFrame(conflicts)
            cdf.insert(0, "indication", indication)
            conflicts_path.parent.mkdir(parents=True, exist_ok=True)
            cdf.to_csv(conflicts_path, index=False)
            result["paths"]["kpi_conflicts"] = str(conflicts_path)
        result["evidence_df"] = evidence_df  # keep in-memory version with year column
        result["tool_ready_df"] = pd.DataFrame([r.to_row() for r in tool_rows])

        # 3b) Epidemiology Evidence Pack: confidence, scorecard, white-space, reconciliation, one-pager
        evidence_df_epi = result["evidence_df"].copy()
        evidence_df_epi = add_computed_confidence(evidence_df_epi)
        # Write single evidence file (sorted by metric)
        evidence_df_epi_sorted = evidence_df_epi.sort_values("metric").reset_index(drop=True) if "metric" in evidence_df_epi.columns else evidence_df_epi
        evidence_df_epi_sorted.to_csv(evidence_path_out, index=False)
        result["evidence_df"] = evidence_df_epi
        required_metrics_list = load_required_metrics(metrics_config_path)
        scorecard_df = build_kpi_scorecard(evidence_df_epi, required_metrics_list, indication=indication)
        scorecard_path = output_dir / f"kpi_scorecard_{file_suffix}.csv"
        export_kpi_scorecard(scorecard_df, scorecard_path)
        result["paths"]["kpi_scorecard"] = str(scorecard_path)
        result["kpi_df"] = scorecard_df
        coverage_df = build_coverage_matrix(evidence_df_epi, required_metrics_list, indication=indication, geography=country or "")
        white_space_summary_text = build_white_space_summary(coverage_df, indication=indication, geography=country or "")
        export_white_space_files(coverage_df, white_space_summary_text, output_dir, file_suffix)
        result["paths"]["white_space_summary"] = str(output_dir / f"white_space_{file_suffix}_summary.md")
        recon_df = build_reconciliation_table(evidence_df_epi, required_metrics_list, indication=indication, geography=country or "")
        if not recon_df.empty:
            recon_path = output_dir / f"reconciliation_{file_suffix}.csv"
            export_reconciliation(recon_df, recon_path)
            result["paths"]["reconciliation"] = str(recon_path)
        summary_md = generate_evidence_summary_md(
            indication, country or "", evidence_df_epi,
            scorecard_df=scorecard_df,
            white_space_summary=white_space_summary_text,
        )
        summary_path = output_dir / f"evidence_summary_{file_suffix}.md"
        export_evidence_summary(summary_md, summary_path)
        result["paths"]["evidence_summary"] = str(summary_path)
        rubric_path = output_dir / "confidence_rubric.md"
        export_confidence_rubric(rubric_path)
        result["paths"]["confidence_rubric"] = str(rubric_path)

        # 4) Optional: dashboard layer + forecast + insights
        if export_dashboard:
            from ..analytics.forecast import build_forecast_table
            from ..analytics.insights import build_insights_summary
            from ..dashboard.export import export_dashboard_layer

            dashboard_dir = output_dir / "dashboard"
            dashboard_dir.mkdir(parents=True, exist_ok=True)
            kpi_df = result["kpi_df"]
            evidence_df_for_analytics = result["evidence_df"]

            forecast_df = pd.DataFrame()
            if include_forecast:
                forecast_df = build_forecast_table(evidence_df_for_analytics, indication, years_ahead=5)
                fp = output_dir / f"forecast_{file_suffix}.csv"
                forecast_df.to_csv(fp, index=False)
                result["paths"]["forecast"] = str(fp)

            insights_df = build_insights_summary(evidence_df_for_analytics, kpi_df=kpi_df, indication=indication)
            ip = output_dir / f"insights_summary_{file_suffix}.csv"
            insights_df.to_csv(ip, index=False)
            result["paths"]["insights_summary"] = str(ip)

            tool_ready_df = result["tool_ready_df"]
            insightace_epi_df = build_insightace_epidemiology_table(tool_rows, scenario_label="High")
            scenario_registry_df = pd.DataFrame([o.to_row() for o in scenario_options])
            source_log_df = pd.read_csv(source_log_path)

            export_dashboard_layer(
                dashboard_dir,
                evidence_df=evidence_df_for_analytics,
                tool_ready_df=tool_ready_df,
                kpi_df=kpi_df,
                scenario_registry_df=scenario_registry_df,
                insightace_epi_df=insightace_epi_df,
                source_log_df=source_log_df,
                forecast_df=forecast_df if not forecast_df.empty else None,
                insights_summary_df=insights_df,
                export_csv=True,
                export_sqlite=True,
                sqlite_db_name="epidemiology_dashboard.db",
            )
            result["paths"]["dashboard_dir"] = str(dashboard_dir)

        # Consolidate all CSVs into a single Excel file (one sheet per extract)
        excel_path = output_dir / f"extract_consolidated_{file_suffix}.xlsx"
        _consolidate_csvs_to_excel(result["paths"], excel_path)
        if excel_path.exists():
            result["paths"]["extract_consolidated"] = str(excel_path)

        result["success"] = True
        result["message"] = f"Pipeline complete. {result['record_count']} evidence rows; outputs in {output_dir}."
        return result

    except Exception as e:
        result["message"] = f"Pipeline error: {e}"
        result["paths"] = {}
        return result
