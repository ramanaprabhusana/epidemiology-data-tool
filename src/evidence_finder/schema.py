"""
Schema for a single evidence item captured by Evidence Finder.
Aligns with scope: metric, definition, population, year, geography, split, value, source, notes, confidence.
"""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class EvidenceRecord:
    indication: str
    metric: str
    value: Union[str, float]  # point estimate or range as string
    source_citation: str
    source_tier: str  # gold | silver | bronze
    definition: Optional[str] = None
    population: Optional[str] = None
    year_or_range: Optional[str] = None
    geography: Optional[str] = None
    split_logic: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None
    confidence: Optional[str] = None  # low | medium | high
    evidence_id: Optional[str] = None  # optional stable id

    def to_row(self) -> dict:
        """For CSV/Excel export."""
        return {
            "indication": self.indication,
            "metric": self.metric,
            "value": self.value,
            "source_citation": self.source_citation,
            "source_tier": self.source_tier,
            "definition": self.definition or "",
            "population": self.population or "",
            "year_or_range": self.year_or_range or "",
            "geography": self.geography or "",
            "split_logic": self.split_logic or "",
            "source_url": self.source_url or "",
            "notes": self.notes or "",
            "confidence": self.confidence or "",
        }
