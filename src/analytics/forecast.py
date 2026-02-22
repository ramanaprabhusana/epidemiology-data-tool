"""
Lightweight forecasting for epidemiology metrics: trend-based and scenario (low/base/high).
Use curated historical evidence only; outputs are dashboard-ready for Tableau/Power BI.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _extract_year(val: Any) -> Optional[int]:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        if "-" in s:
            s = s.split("-")[0]
        return int(s)
    except (ValueError, TypeError):
        return None


def simple_trend_forecast(
    evidence_df: pd.DataFrame,
    metric: str,
    years_ahead: int = 5,
    growth_rate: Optional[float] = None,
) -> pd.DataFrame:
    """
    Produce a simple forecast for one metric from evidence (year, value).
    If growth_rate is None, uses last two observed years to estimate annual growth.
    Returns DataFrame with columns: metric, year, value, scenario (base/low/high optional later).
    """
    # Get numeric value and year from evidence for this metric
    sub = evidence_df[evidence_df["metric"] == metric].copy()
    if sub.empty:
        return pd.DataFrame(columns=["metric", "year", "value", "scenario"])

    sub["year"] = sub.get("year_or_range", sub.get("year", None)).apply(_extract_year)
    sub = sub.dropna(subset=["year"])
    sub["value"] = pd.to_numeric(sub.get("value", 0), errors="coerce")
    sub = sub.dropna(subset=["value"]).sort_values("year")

    if sub.empty or len(sub) < 1:
        return pd.DataFrame(columns=["metric", "year", "value", "scenario"])

    last_year = int(sub["year"].max())
    last_val = float(sub[sub["year"] == last_year]["value"].iloc[0])

    if growth_rate is None and len(sub) >= 2:
        y1, y2 = sub["year"].iloc[-2], sub["year"].iloc[-1]
        v1, v2 = sub["value"].iloc[-2], sub["value"].iloc[-1]
        if y2 > y1 and v1 and v1 > 0:
            growth_rate = (v2 / v1) ** (1 / (y2 - y1)) - 1
        else:
            growth_rate = 0.0
    elif growth_rate is None:
        growth_rate = 0.0

    rows = []
    for i in range(1, years_ahead + 1):
        y = last_year + i
        v = last_val * ((1 + growth_rate) ** i)
        rows.append({"metric": metric, "year": y, "value": round(v, 2), "scenario": "base"})
    return pd.DataFrame(rows)


def build_forecast_table(
    evidence_df: pd.DataFrame,
    indication: str,
    metrics: Optional[List[str]] = None,
    years_ahead: int = 5,
    growth_rates: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Build a forecast table for multiple metrics. Each metric gets base (and optionally low/high) scenario.
    growth_rates: optional dict metric -> annual growth rate; else auto from last two years.
    Returns one DataFrame with indication, metric, year, value, scenario.
    """
    if metrics is None:
        metrics = evidence_df["metric"].dropna().unique().tolist()
    if growth_rates is None:
        growth_rates = {}

    out: List[dict] = []
    for metric in metrics:
        rate = growth_rates.get(metric)
        df = simple_trend_forecast(evidence_df, metric, years_ahead=years_ahead, growth_rate=rate)
        if df.empty:
            continue
        df.insert(0, "indication", indication)
        out.append(df)

    if not out:
        return pd.DataFrame(columns=["indication", "metric", "year", "value", "scenario"])
    result = pd.concat(out, ignore_index=True)
    return result
