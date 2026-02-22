"""
Schema for Data Builder: scenario options (dropdown-style) and tool-ready output rows.
"""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class ScenarioOption:
    """One selectable alternative (e.g. growth rate, stage split) with rationale."""
    scenario_type: str   # e.g. "growth_rate", "stage_split"
    option_id: str       # e.g. "seer_trend", "literature_low"
    label: str           # display label for dropdown
    rationale: str       # short rationale for forecaster
    sources: str        # source(s) backing this option
    # Optional: resulting values or link to computed table
    value_numeric: Optional[float] = None
    value_text: Optional[str] = None

    def to_row(self) -> dict:
        return {
            "scenario_type": self.scenario_type,
            "option_id": self.option_id,
            "label": self.label,
            "rationale": self.rationale,
            "sources": self.sources,
            "value_numeric": self.value_numeric,
            "value_text": self.value_text,
        }


@dataclass
class ToolReadyRow:
    """One row in the tool-ready epidemiology table (InsightACE / Epidemiology Beta aligned)."""
    indication: str
    metric: str
    year: Optional[int] = None
    split_type: Optional[str] = None   # e.g. stage, line
    split_value: Optional[str] = None  # e.g. "Stage I"
    value: Union[float, str] = 0.0
    scenario_growth_rate: Optional[str] = None   # which growth scenario was used
    scenario_stage_split: Optional[str] = None   # which stage scenario was used
    source: Optional[str] = None
    notes: Optional[str] = None

    def to_row(self) -> dict:
        return {
            "indication": self.indication,
            "metric": self.metric,
            "year": self.year,
            "split_type": self.split_type or "",
            "split_value": self.split_value or "",
            "value": self.value,
            "scenario_growth_rate": self.scenario_growth_rate or "",
            "scenario_stage_split": self.scenario_stage_split or "",
            "source": self.source or "",
            "notes": self.notes or "",
        }
