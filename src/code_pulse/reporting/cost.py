"""Cost-to-fix estimator for CodePulse."""

from typing import Dict, List

from code_pulse.core.models import AnalyzerResult, CodePulseScore, CostEstimate, Tier

# Tier thresholds — the minimum score to reach each tier.
_TIER_THRESHOLDS: Dict[Tier, float] = {
    "excellent": 80.0,
    "good": 60.0,
    "poor": 40.0,
    "critical": 0.0,
}

# Map current tier → next higher tier.
_NEXT_TIER: Dict[Tier, Tier] = {
    "critical": "poor",
    "poor": "good",
    "good": "excellent",
    "excellent": "excellent",  # already at top
}

# Base effort per file-point gap (person-days per point of deficit).
_EFFORT_PER_POINT = 0.1


class CostEstimator:
    """Estimates effort to improve from current tier to the next higher tier."""

    @staticmethod
    def estimate(
        score: CodePulseScore, results: List[AnalyzerResult]
    ) -> CostEstimate:
        """Produce a rough person-day estimate.

        For each file whose score is below the target threshold, the effort
        is proportional to the gap between the file score and the target.
        """
        current_tier = score.tier
        target_tier = _NEXT_TIER[current_tier]
        target_score = _TIER_THRESHOLDS[target_tier]

        breakdown: Dict[str, float] = {}
        total_days = 0.0

        # Collect per-file scores from all analyzer results.
        file_scores: Dict[str, List[float]] = {}
        for r in results:
            for fpath, fscore in r.per_file_scores.items():
                file_scores.setdefault(fpath, []).append(fscore)

        # Average per-file scores across analyzers.
        for fpath, scores in file_scores.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            gap = target_score - avg
            if gap > 0:
                effort = gap * _EFFORT_PER_POINT
                breakdown[fpath] = max(0.0, effort)
                total_days += effort

        total_days = max(0.0, total_days)

        return CostEstimate(
            current_tier=current_tier,
            target_tier=target_tier,
            estimated_person_days=round(total_days, 2),
            breakdown=breakdown,
        )
