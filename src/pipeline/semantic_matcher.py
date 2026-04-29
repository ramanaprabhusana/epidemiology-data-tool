"""
Semantic Metric Matcher — resolves raw extracted metric labels
to canonical metric_ids using synonym expansion (fast path) and
optional sentence-transformer embeddings (optional, off by default
for Streamlit Community Cloud compatibility).

Usage:
    from src.pipeline.semantic_matcher import SemanticMatcher
    matcher = SemanticMatcher(config_dir=Path("config/"))
    metric_id, score = matcher.match("IGHV mutation status: mutated")
    # → ("ighv_mutated_pct", 0.92)

Architecture:
    1. Synonym expansion: checks config/metric_synonyms.yaml
       (exact substring match after lowercasing)
    2. Embedding similarity (optional): uses sentence-transformers
       all-MiniLM-L6-v2; enabled with use_embeddings=True
    3. Fallback: returns (raw_label_slug, 0.0)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Slug: convert raw label to metric_id-like string for fallback
def _to_slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


class SemanticMatcher:
    """
    Resolves raw metric label strings to canonical metric_ids.

    Args:
        config_dir: Directory containing metric_synonyms.yaml
        synonyms_file: Name of synonyms config (default: metric_synonyms.yaml)
        use_embeddings: Enable embedding-based fallback (requires sentence-transformers)
        threshold_synonyms: Min score for synonym match to be accepted (0–1)
        threshold_embeddings: Min cosine similarity for embedding match (0–1)
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        synonyms_file: str = "metric_synonyms.yaml",
        use_embeddings: bool = False,
        threshold_synonyms: float = 0.5,
        threshold_embeddings: float = 0.6,
    ):
        self.threshold_synonyms = threshold_synonyms
        self.threshold_embeddings = threshold_embeddings
        self.use_embeddings = use_embeddings
        self._synonyms: dict[str, list[str]] = {}
        self._embedding_model = None
        self._metric_embeddings = None

        # Load synonyms
        if config_dir is None:
            config_dir = Path(__file__).resolve().parents[2] / "config"
        synonyms_path = Path(config_dir) / synonyms_file
        if synonyms_path.exists():
            try:
                with open(synonyms_path, encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                self._synonyms = {k: [str(v).lower() for v in vs] for k, vs in raw.items()}
                logger.debug(f"Loaded {len(self._synonyms)} metric synonym groups")
            except Exception as e:
                logger.warning(f"Could not load synonyms from {synonyms_path}: {e}")

        # Load embedding model (lazy, optional)
        if use_embeddings:
            try:
                from sentence_transformers import SentenceTransformer, util  # noqa
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                self._util = util
                logger.info("Embedding model loaded: all-MiniLM-L6-v2")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. Embeddings disabled. "
                    "Install with: pip install sentence-transformers"
                )
                self.use_embeddings = False
            except Exception as e:
                logger.warning(f"Could not load embedding model: {e}")
                self.use_embeddings = False

    def match(self, raw_label: str) -> Tuple[str, float]:
        """
        Match raw_label to a canonical metric_id.

        Returns:
            (metric_id, confidence_score)  where score ∈ [0, 1]
            If no match found: returns (_to_slug(raw_label), 0.0)
        """
        if not raw_label or not isinstance(raw_label, str):
            return ("unknown", 0.0)

        label_lower = raw_label.lower().strip()

        # ── 1. Synonym expansion (fast path) ────────────────────
        best_mid, best_score = self._synonym_match(label_lower)
        if best_score >= self.threshold_synonyms:
            return (best_mid, best_score)

        # ── 2. Embedding similarity (optional slow path) ────────
        if self.use_embeddings and self._embedding_model is not None:
            emb_mid, emb_score = self._embedding_match(raw_label)
            if emb_score >= self.threshold_embeddings:
                return (emb_mid, emb_score)
            # Return best of synonym/embedding
            if emb_score > best_score:
                return (emb_mid, emb_score)

        # ── 3. Fallback ──────────────────────────────────────────
        if best_mid and best_score > 0:
            return (best_mid, best_score)
        return (_to_slug(raw_label), 0.0)

    def match_batch(self, raw_labels: List[str]) -> List[Tuple[str, float]]:
        """Match a list of raw labels; returns list of (metric_id, score) tuples."""
        return [self.match(label) for label in raw_labels]

    def _synonym_match(self, label_lower: str) -> Tuple[str, float]:
        """
        Check each metric_id's synonym list for substring match.
        Scoring:
          - Exact match on a synonym: 0.95
          - Synonym is substring of label: 0.80
          - Label is substring of synonym: 0.70
        Returns (best_metric_id, best_score).
        """
        best_mid = ""
        best_score = 0.0

        for metric_id, synonyms in self._synonyms.items():
            for syn in synonyms:
                score = 0.0
                if label_lower == syn:
                    score = 0.95
                elif syn in label_lower:
                    # Longer synonym matches = higher confidence
                    score = 0.75 + 0.15 * (len(syn) / max(len(label_lower), 1))
                elif label_lower in syn:
                    score = 0.65
                if score > best_score:
                    best_score = score
                    best_mid = metric_id

        return (best_mid, best_score)

    def _embedding_match(self, raw_label: str) -> Tuple[str, float]:
        """
        Use sentence-transformer cosine similarity to find best matching metric_id.
        Each metric_id is represented by: metric_id + ". " + all synonyms concatenated.
        """
        if not self._synonyms or self._embedding_model is None:
            return ("", 0.0)

        import torch  # noqa — only reached if sentence-transformers available

        # Build candidate texts lazily
        if self._metric_embeddings is None:
            metric_ids = list(self._synonyms.keys())
            texts = []
            for mid in metric_ids:
                syns = self._synonyms[mid]
                texts.append(f"{mid.replace('_', ' ')}. {'. '.join(syns)}")
            self._metric_ids = metric_ids
            self._metric_embeddings = self._embedding_model.encode(
                texts, convert_to_tensor=True
            )

        query_emb = self._embedding_model.encode(raw_label, convert_to_tensor=True)
        scores = self._util.pytorch_cos_sim(query_emb, self._metric_embeddings)[0]
        best_idx = int(scores.argmax().item())
        best_score = float(scores[best_idx].item())
        return (self._metric_ids[best_idx], best_score)

    def explain(self, raw_label: str) -> str:
        """Return a human-readable explanation of how a label was matched."""
        metric_id, score = self.match(raw_label)
        label_lower = raw_label.lower().strip()
        matched_synonyms = []
        if metric_id in self._synonyms:
            for syn in self._synonyms[metric_id]:
                if syn in label_lower or label_lower in syn:
                    matched_synonyms.append(syn)
        method = "synonym" if matched_synonyms else "embedding" if score > 0 else "fallback slug"
        return (
            f"'{raw_label}' → '{metric_id}' "
            f"(score={score:.2f}, method={method}"
            + (f", matched via: {matched_synonyms[:2]}" if matched_synonyms else "")
            + ")"
        )


# ── Convenience function ──────────────────────────────────────────
_default_matcher: Optional[SemanticMatcher] = None


def get_default_matcher(config_dir: Optional[Path] = None) -> SemanticMatcher:
    """Return a module-level singleton matcher (lazy init)."""
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = SemanticMatcher(config_dir=config_dir)
    return _default_matcher


def resolve_metric_id(raw_label: str, config_dir: Optional[Path] = None) -> Tuple[str, float]:
    """
    Module-level shortcut: resolve a raw metric label string to metric_id.
    Uses the singleton matcher (synonym expansion only, cloud-safe).

    Returns (metric_id, confidence_score).
    """
    return get_default_matcher(config_dir).match(raw_label)
