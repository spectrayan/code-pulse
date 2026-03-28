"""Dependency health scoring — detects manifest files and counts dependencies."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)

# Supported dependency manifest filenames
_MANIFEST_FILES = (
    "requirements.txt",
    "package.json",
    "pom.xml",
    "build.gradle",
)


def _normalize_issues(issue_count: int) -> float:
    """Normalize dependency issue count to a 0-100 score.

    Formula: max(0, 100 - issue_count * 5) clamped to [0, 100].
    """
    raw = 100.0 - issue_count * 5.0
    return max(0.0, min(100.0, raw))


def _count_requirements_txt(path: Path) -> int:
    """Count dependencies in a requirements.txt file."""
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
            count += 1
    return count


def _count_package_json(path: Path) -> int:
    """Count dependencies in a package.json file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps = len(data.get("dependencies", {}))
        dev_deps = len(data.get("devDependencies", {}))
        return deps + dev_deps
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return 0


def _count_pom_xml(path: Path) -> int:
    """Count <dependency> entries in a pom.xml file."""
    content = path.read_text(encoding="utf-8")
    return content.count("<dependency>")


def _count_build_gradle(path: Path) -> int:
    """Count dependency declarations in a build.gradle file."""
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if any(
            stripped.startswith(prefix)
            for prefix in (
                "implementation ",
                "implementation(",
                "compile ",
                "compile(",
                "api ",
                "api(",
                "testImplementation ",
                "testImplementation(",
                "runtimeOnly ",
                "runtimeOnly(",
                "compileOnly ",
                "compileOnly(",
            )
        ):
            count += 1
    return count


_COUNTERS = {
    "requirements.txt": _count_requirements_txt,
    "package.json": _count_package_json,
    "pom.xml": _count_pom_xml,
    "build.gradle": _count_build_gradle,
}


class DependencyAnalyzer(Analyzer):
    """Analyzer that checks dependency manifests for potential issues."""

    def name(self) -> str:
        return "dependency"

    def dimension(self) -> str:
        return "dependency_health"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Detect dependency manifests and score based on dependency count.

        Each dependency is treated as 1 potential issue (placeholder for real
        vulnerability/outdated checks). Score is normalized via
        max(0, 100 - issue_count * 5) clamped to [0, 100].
        """
        manifests_found: Dict[str, int] = {}

        for manifest_name in _MANIFEST_FILES:
            manifest_path = repo_path / manifest_name
            if manifest_path.is_file():
                counter = _COUNTERS[manifest_name]
                dep_count = counter(manifest_path)
                manifests_found[manifest_name] = dep_count
                logger.info(
                    "Found %s with %d dependencies.", manifest_name, dep_count
                )

        if not manifests_found:
            logger.info(
                "No dependency manifest files found in %s.", repo_path
            )
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                per_file_scores={},
                details={},
                warnings=["No dependency manifest files found"],
            )

        total_issues = sum(manifests_found.values())
        normalized_score = _normalize_issues(total_issues)

        per_file_scores: Dict[str, float] = {
            name: _normalize_issues(count)
            for name, count in manifests_found.items()
        }

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=round(normalized_score, 2),
            per_file_scores=per_file_scores,
            details={
                "manifests": manifests_found,
                "total_dependencies": total_issues,
            },
            warnings=[],
        )
