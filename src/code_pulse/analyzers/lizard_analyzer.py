"""Cyclomatic complexity, LOC, and function length analysis via lizard."""

import logging
from pathlib import Path
from typing import Any, Dict, List

import lizard

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.discovery import FileDiscovery
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".py", ".java", ".js", ".ts"}


def _normalize_complexity(avg_cc: float) -> float:
    """Normalize average cyclomatic complexity to a 0-100 score.

    Formula: max(0, 100 - (avg_cc - 5) * (100/15)) clamped to [0, 100].
    An avg_cc of 5 or below scores 100; an avg_cc of 20 or above scores 0.
    """
    raw = 100.0 - (avg_cc - 5.0) * (100.0 / 15.0)
    return max(0.0, min(100.0, raw))


class LizardAnalyzer(Analyzer):
    """Analyzer that uses lizard to compute cyclomatic complexity metrics."""

    def name(self) -> str:
        return "lizard"

    def dimension(self) -> str:
        return "complexity"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run lizard analysis on all supported source files in the repo.

        Returns an AnalyzerResult with per-file normalized scores and raw
        metrics in the details dict.
        """
        discovered = FileDiscovery.discover(repo_path)
        file_paths: List[str] = []
        for paths in discovered.values():
            file_paths.extend(str(p) for p in paths)

        if not file_paths:
            logger.warning("No supported source files found in %s", repo_path)
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                per_file_scores={},
                details={"file_count": 0, "raw_metrics": {}},
                warnings=["No supported source files found"],
            )

        per_file_scores: Dict[str, float] = {}
        raw_metrics: Dict[str, Any] = {}
        warnings: List[str] = []

        analysis = lizard.analyze_files(file_paths, exts=lizard.get_extensions([]))

        for file_info in analysis:
            file_path = file_info.filename
            try:
                functions = file_info.function_list
                if not functions:
                    # File has no functions — treat as perfect complexity
                    per_file_scores[file_path] = 100.0
                    raw_metrics[file_path] = {
                        "avg_cyclomatic_complexity": 0,
                        "total_loc": file_info.nloc,
                        "function_count": 0,
                        "functions": [],
                    }
                    continue

                total_cc = sum(f.cyclomatic_complexity for f in functions)
                avg_cc = total_cc / len(functions)
                avg_loc = sum(f.nloc for f in functions) / len(functions)
                avg_length = sum(f.length for f in functions) / len(functions)

                score = _normalize_complexity(avg_cc)
                per_file_scores[file_path] = score

                raw_metrics[file_path] = {
                    "avg_cyclomatic_complexity": round(avg_cc, 2),
                    "total_loc": file_info.nloc,
                    "function_count": len(functions),
                    "avg_function_loc": round(avg_loc, 2),
                    "avg_function_length": round(avg_length, 2),
                    "functions": [
                        {
                            "name": f.name,
                            "cyclomatic_complexity": f.cyclomatic_complexity,
                            "nloc": f.nloc,
                            "length": f.length,
                        }
                        for f in functions
                    ],
                }
            except Exception as exc:
                logger.warning(
                    "Failed to process file %s: %s", file_path, exc
                )
                warnings.append(f"Unparseable file excluded: {file_path}")

        if per_file_scores:
            normalized_score = sum(per_file_scores.values()) / len(per_file_scores)
        else:
            normalized_score = 100.0

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=round(normalized_score, 2),
            per_file_scores=per_file_scores,
            details={
                "file_count": len(per_file_scores),
                "raw_metrics": raw_metrics,
            },
            warnings=warnings,
        )
