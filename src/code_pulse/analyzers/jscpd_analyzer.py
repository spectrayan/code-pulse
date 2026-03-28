"""Duplication detection via jscpd (Node.js CLI tool)."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)


def _normalize_duplication(duplication_pct: float) -> float:
    """Normalize duplication percentage to a 0-100 score.

    Formula: max(0, 100 - duplication_pct * 2) clamped to [0, 100].
    0% duplication scores 100; 50%+ duplication scores 0.
    """
    raw = 100.0 - duplication_pct * 2.0
    return max(0.0, min(100.0, raw))


class JscpdAnalyzer(Analyzer):
    """Analyzer that uses jscpd to detect copy-paste duplication."""

    def name(self) -> str:
        return "jscpd"

    def dimension(self) -> str:
        return "duplication"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run jscpd on the repository and return normalized duplication score."""
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                subprocess.run(
                    ["jscpd", "--reporters", "json", "--output", tmpdir, str(repo_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True,
                )
            except FileNotFoundError:
                logger.warning("jscpd is not installed; skipping duplication analysis")
                return AnalyzerResult(
                    analyzer_name=self.name(),
                    dimension=self.dimension(),
                    normalized_score=100.0,
                    warnings=["jscpd is not installed; duplication analysis skipped"],
                )
            except subprocess.CalledProcessError as exc:
                logger.warning("jscpd failed with exit code %d: %s", exc.returncode, exc.stderr)
                return AnalyzerResult(
                    analyzer_name=self.name(),
                    dimension=self.dimension(),
                    normalized_score=100.0,
                    warnings=[f"jscpd failed (exit {exc.returncode}); duplication analysis skipped"],
                )
            except subprocess.TimeoutExpired:
                logger.warning("jscpd timed out after 120 seconds")
                return AnalyzerResult(
                    analyzer_name=self.name(),
                    dimension=self.dimension(),
                    normalized_score=100.0,
                    warnings=["jscpd timed out; duplication analysis skipped"],
                )

            # Parse the JSON report produced by jscpd
            report_path = Path(tmpdir) / "jscpd-report.json"
            if not report_path.exists():
                logger.warning("jscpd JSON report not found at %s", report_path)
                return AnalyzerResult(
                    analyzer_name=self.name(),
                    dimension=self.dimension(),
                    normalized_score=100.0,
                    warnings=["jscpd JSON report not found; duplication analysis skipped"],
                )

            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to parse jscpd report: %s", exc)
                return AnalyzerResult(
                    analyzer_name=self.name(),
                    dimension=self.dimension(),
                    normalized_score=100.0,
                    warnings=["Failed to parse jscpd report; duplication analysis skipped"],
                )

            # Extract duplication percentage from the statistics
            statistics = report.get("statistics", {})
            total = statistics.get("total", {})
            duplication_pct = total.get("percentage", 0.0)

            normalized_score = _normalize_duplication(duplication_pct)

            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=round(normalized_score, 2),
                details={
                    "duplication_percentage": round(duplication_pct, 2),
                    "clones_count": len(report.get("duplicates", [])),
                },
            )
