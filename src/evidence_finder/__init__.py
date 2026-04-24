"""
Evidence Finder: tiered source discovery and evidence collection.
Outputs structured evidence table + source log; feeds Data Builder and KPI.
"""

# Lazy import to avoid circular import issues with frozen importlib (Streamlit Cloud).
# Import directly from src.evidence_finder.schema when EvidenceRecord is needed.
__all__ = ["EvidenceRecord"]


def __getattr__(name):
    if name == "EvidenceRecord":
        from .schema import EvidenceRecord
        return EvidenceRecord
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
