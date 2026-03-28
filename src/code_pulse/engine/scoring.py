"""Weighted ensemble scoring engine for CodePulse."""

from collections import defaultdict
from typing import Dict, List, Tuple

from code_pulse.core.models import (
    AnalyzerResult,
    CodePulseScore,
    Config,
    Recommendation,
    Tier,
)


def _tier(score: float) -> Tier:
    """Classify a 0-100 score into a tier."""
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "poor"
    return "critical"


def _recommendation(score: float) -> Recommendation:
    """Derive a recommendation from a 0-100 score."""
    if score >= 80:
        return "maintain"
    if score >= 60:
        return "refactor"
    if score >= 40:
        return "partial_rewrite"
    return "full_rewrite"


class ScoringEngine:
    """Computes the weighted ensemble CodePulse Score."""

    @staticmethod
    def compute(results: List[AnalyzerResult], config: Config) -> CodePulseScore:
        """Compute the final CodePulse score from analyzer results.

        Steps:
        1. Return critical defaults when no results exist.
        2. Group results by dimension, taking min() for overlapping dimensions.
        3. Apply weighted formula: Σ(weight_i × score_i) / Σ(weight_i).
        4. Clamp to [0, 100], classify tier and recommendation.
        5. Compute per-file scores by averaging across analyzers.
        """
        if not results:
            return CodePulseScore(
                final_score=0.0,
                tier="critical",
                recommendation="full_rewrite",
            )

        # --- Group by dimension, use min() for overlapping ---
        dimension_results: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        for r in results:
            score = max(0.0, min(100.0, r.normalized_score))
            weight = 1.0
            if r.analyzer_name in config.analyzers:
                weight = config.analyzers[r.analyzer_name].weight
            dimension_results[r.dimension].append((score, weight))

        # For each dimension, pick the minimum score (conservative).
        # Weight for that dimension = max weight among contributors.
        dimension_scores: Dict[str, float] = {}
        weighted_pairs: List[Tuple[float, float]] = []  # (score, weight)

        for dim, entries in dimension_results.items():
            min_score = min(s for s, _ in entries)
            max_weight = max(w for _, w in entries)
            dimension_scores[dim] = min_score
            weighted_pairs.append((min_score, max_weight))

        # --- Weighted average ---
        total_weight = sum(w for _, w in weighted_pairs)
        if total_weight == 0:
            final_score = 0.0
        else:
            final_score = sum(s * w for s, w in weighted_pairs) / total_weight

        final_score = max(0.0, min(100.0, final_score))

        # --- Per-file scores: average across all analyzers for each file ---
        file_scores: Dict[str, List[float]] = defaultdict(list)
        for r in results:
            for fpath, fscore in r.per_file_scores.items():
                file_scores[fpath].append(max(0.0, min(100.0, fscore)))

        per_file_scores = {
            fpath: sum(scores) / len(scores)
            for fpath, scores in file_scores.items()
        }

        return CodePulseScore(
            final_score=final_score,
            tier=_tier(final_score),
            recommendation=_recommendation(final_score),
            per_file_scores=per_file_scores,
            dimension_scores=dimension_scores,
        )
