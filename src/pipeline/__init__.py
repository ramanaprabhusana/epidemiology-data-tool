"""
Single pipeline entry point: run Evidence Finder + Data Builder + KPI + optional dashboard
for a given indication and country. Used by run_tool.py (CLI) and the Streamlit UI.
"""

from .runner import run_pipeline

__all__ = ["run_pipeline"]
