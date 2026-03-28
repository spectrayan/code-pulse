"""Anti-pattern and security smell detection via semgrep (CLI tool)."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)


def _count_lines(repo_path: Path) -> int:
    """Count total lines of code across supported source files."""
    supported = {".py", ".java", ".js", ".ts"}
    excluded = {"node_modules", ".git", "__pycache__", "build", "dist", ".venv", "venv"}
    total = 0
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for filename in filenames:
            if Path(filename).suffix in supported:
                try:
                    total += sum(1 for _ in open(Path(dirpath) / filename, encoding="utf-8", errors="ignore"))
                except OSError:
                    pass
    return total


def _normalize_findings(findings_per_kloc: float) -> float:
    """Normalize findings per KLOC to a 0-100 score.

    Formula: max(0, 100 - findings_per_kloc * 10) clamped to [0, 100].
    0 findings/KLOC scores 100; 10+ findings/KLOC scores 0.
    """
    raw = 100.0 - findings_per_kloc * 10.0
    return max(0.0, min(100.0, raw))


class SemgrepAnalyzer(Analyzer):
    """Analyzer that uses semgrep to detect anti-patterns and security smells."""

    def name(self) -> str:
        return "semgrep"

    def dimension(self) -> str:
        return "anti_patterns"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run semgrep on the repository and return normalized anti-pattern score."""
        rulesets = settings.get("rulesets", ["auto"])

        # Build the semgrep command with configurable rulesets
        cmd = ["semgrep", "--json"]
        for ruleset in rulesets:
            cmd.extend(["--config", ruleset])
        cmd.append(str(repo_path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            logger.warning("semgrep is not installed; skipping anti-pattern analysis")
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=["semgrep is not installed; anti-pattern analysis skipped"],
            )
        except subprocess.CalledProcessError as exc:
            logger.warning("semgrep failed with exit code %d: %s", exc.returncode, exc.stderr)
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=[f"semgrep failed (exit {exc.returncode}); anti-pattern analysis skipped"],
            )
        except subprocess.TimeoutExpired:
            logger.warning("semgrep timed out after 120 seconds")
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=["semgrep timed out; anti-pattern analysis skipped"],
            )

        # Parse JSON output from stdout
        try:
            output = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse semgrep JSON output: %s", exc)
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=["Failed to parse semgrep output; anti-pattern analysis skipped"],
            )

        findings = output.get("results", [])
        total_findings = len(findings)

        # Count total LOC for findings_per_kloc calculation
        total_loc = _count_lines(repo_path)

        if total_loc > 0:
            findings_per_kloc = total_findings / (total_loc / 1000.0)
        else:
            findings_per_kloc = 0.0

        normalized_score = _normalize_findings(findings_per_kloc)

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=round(normalized_score, 2),
            details={
                "total_findings": total_findings,
                "total_loc": total_loc,
                "findings_per_kloc": round(findings_per_kloc, 2),
                "rulesets": rulesets,
            },
        )
