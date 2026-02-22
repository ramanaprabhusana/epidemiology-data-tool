"""
Analytics: forecasting and insights generation for epidemiology data.
Outputs are dashboard-ready and can feed Tableau / Power BI.
"""

from .forecast import build_forecast_table, simple_trend_forecast
from .insights import build_insights_summary

__all__ = ["build_forecast_table", "simple_trend_forecast", "build_insights_summary"]
