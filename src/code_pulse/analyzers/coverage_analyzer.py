"""Code coverage analysis — executes test suites or reads existing coverage reports.

Supports three modes (configurable via settings):
  - "execute": Run a test command with coverage instrumentation
  - "report":  Read existing coverage report files from the repo
  - "sonarqube": Pull coverage metrics from a SonarQube server

When multiple sources are available, the analyzer uses the highest-confidence one.
"""

import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportPattern:
    """Describes a well-known coverage report file pattern."""

    glob: str
    parser: Callable[[Path], Optional[float]]
    lang: Optional[str] = None


# ---------------------------------------------------------------------------
# Report parsers
# ---------------------------------------------------------------------------


def _parse_jacoco_xml(path: Path) -> Optional[float]:
    """Parse a JaCoCo XML report and return line coverage percentage."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for counter in root.findall(".//counter[@type='LINE']"):
            missed = int(counter.get("missed", 0))
            covered = int(counter.get("covered", 0))
            total = missed + covered
            if total > 0:
                return (covered / total) * 100.0
    except Exception as exc:
        logger.warning("Failed to parse JaCoCo XML %s: %s", path, exc)
    return None


def _parse_cobertura_xml(path: Path) -> Optional[float]:
    """Parse a Cobertura XML report and return line-rate as percentage."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        line_rate = root.get("line-rate")
        if line_rate is not None:
            return float(line_rate) * 100.0
    except Exception as exc:
        logger.warning("Failed to parse Cobertura XML %s: %s", path, exc)
    return None


def _parse_coverage_json(path: Path) -> Optional[float]:
    """Parse a coverage.py JSON report and return total coverage percentage."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # coverage.py format: {"totals": {"percent_covered": 85.5}}
        totals = data.get("totals", {})
        pct = totals.get("percent_covered")
        if pct is not None:
            return float(pct)
        # Alternative format: {"meta": ..., "totals": {"covered_lines": N, "num_statements": M}}
        covered = totals.get("covered_lines", 0)
        total = totals.get("num_statements", 0)
        if total > 0:
            return (covered / total) * 100.0
    except Exception as exc:
        logger.warning("Failed to parse coverage JSON %s: %s", path, exc)
    return None


def _parse_lcov(path: Path) -> Optional[float]:
    """Parse an lcov.info file and return overall line coverage percentage."""
    try:
        lines_found = 0
        lines_hit = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("LF:"):
                lines_found += int(line[3:])
            elif line.startswith("LH:"):
                lines_hit += int(line[3:])
        if lines_found > 0:
            return (lines_hit / lines_found) * 100.0
    except Exception as exc:
        logger.warning("Failed to parse lcov %s: %s", path, exc)
    return None


def _parse_istanbul_json(path: Path) -> Optional[float]:
    """Parse an Istanbul coverage-summary.json and return line coverage."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        total = data.get("total", {})
        lines = total.get("lines", {})
        pct = lines.get("pct")
        if pct is not None:
            return float(pct)
    except Exception as exc:
        logger.warning("Failed to parse Istanbul JSON %s: %s", path, exc)
    return None


# Well-known coverage report file patterns
_REPORT_PATTERNS: List[ReportPattern] = [
    # JaCoCo (Java)
    ReportPattern(glob="**/jacoco.xml", parser=_parse_jacoco_xml, lang="java"),
    ReportPattern(glob="**/jacoco-report/jacoco.xml", parser=_parse_jacoco_xml, lang="java"),
    ReportPattern(glob="**/site/jacoco/jacoco.xml", parser=_parse_jacoco_xml, lang="java"),
    # coverage.py / pytest-cov (Python)
    ReportPattern(glob="**/coverage.json", parser=_parse_coverage_json, lang="python"),
    ReportPattern(glob="**/.coverage.json", parser=_parse_coverage_json, lang="python"),
    ReportPattern(glob="**/htmlcov/status.json", parser=_parse_coverage_json, lang="python"),
    # lcov (JS/TS/multi)
    ReportPattern(glob="**/lcov.info", parser=_parse_lcov, lang="javascript"),
    ReportPattern(glob="**/coverage/lcov.info", parser=_parse_lcov, lang="javascript"),
    # Cobertura XML (multi-language)
    ReportPattern(glob="**/cobertura.xml", parser=_parse_cobertura_xml),
    ReportPattern(glob="**/coverage.xml", parser=_parse_cobertura_xml),
    # Istanbul JSON (JS/TS)
    ReportPattern(glob="**/coverage/coverage-summary.json", parser=_parse_istanbul_json, lang="javascript"),
]


# ---------------------------------------------------------------------------
# Test execution helpers
# ---------------------------------------------------------------------------

# Auto-detected test commands per build system
_AUTO_DETECT_COMMANDS: List[Dict[str, Any]] = [
    # Java / Gradle
    {"marker": "build.gradle", "cmd": ["./gradlew", "test", "jacocoTestReport"], "report_glob": "**/jacoco.xml"},
    {"marker": "build.gradle.kts", "cmd": ["./gradlew", "test", "jacocoTestReport"], "report_glob": "**/jacoco.xml"},
    # Java / Maven
    {"marker": "pom.xml", "cmd": ["mvn", "test", "-q"], "report_glob": "**/jacoco.xml"},
    # Python / pytest
    {"marker": "pyproject.toml", "cmd": ["pytest", "-q"], "report_glob": "**/coverage.json"},
    {"marker": "setup.py", "cmd": ["pytest", "-q"], "report_glob": "**/coverage.json"},
    # JavaScript / npm
    {"marker": "package.json", "cmd": ["npm", "test", "--", "--coverage"], "report_glob": "**/lcov.info"},
]


def _run_test_command(repo_path: Path, cmd: List[str], timeout: int = 300) -> bool:
    """Execute a test command in the repo directory. Returns True on success."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("Test command %s exited with code %d: %s", cmd, result.returncode, result.stderr[:500])
        return result.returncode == 0
    except FileNotFoundError:
        logger.warning("Command not found: %s", cmd[0])
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Test command timed out after %ds: %s", timeout, cmd)
        return False
    except Exception as exc:
        logger.warning("Test command failed: %s — %s", cmd, exc)
        return False


# ---------------------------------------------------------------------------
# SonarQube coverage fetcher
# ---------------------------------------------------------------------------


def _fetch_sonarqube_coverage(settings: Dict[str, Any]) -> Optional[float]:
    """Pull coverage percentage from a SonarQube server."""
    server_url = settings.get("sonarqube_url", "")
    token = settings.get("sonarqube_token", "")
    project_key = settings.get("sonarqube_project_key", "")

    if not server_url or not project_key:
        return None

    base_url = server_url.rstrip("/")
    auth = (token, "") if token else None
    url = f"{base_url}/api/measures/component"
    params = {"component": project_key, "metricKeys": "coverage"}

    try:
        resp = requests.get(url, params=params, auth=auth, timeout=30)
        if resp.status_code != 200:
            logger.warning("SonarQube coverage request returned HTTP %d", resp.status_code)
            return None
        data = resp.json()
        measures = data.get("component", {}).get("measures", [])
        for m in measures:
            if m.get("metric") == "coverage":
                return float(m["value"])
    except Exception as exc:
        logger.warning("Failed to fetch SonarQube coverage: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------


class CoverageAnalyzer(Analyzer):
    """Analyzer that measures code coverage via execution, reports, or SonarQube.

    Settings:
        mode: "auto" | "execute" | "report" | "sonarqube" (default: "auto")
        test_command: Custom test command (list of strings) for "execute" mode
        test_timeout: Timeout in seconds for test execution (default: 300)
        report_path: Explicit path to a coverage report file
        sonarqube_url: SonarQube server URL (for "sonarqube" mode)
        sonarqube_token: SonarQube auth token
        sonarqube_project_key: SonarQube project key

    In "auto" mode, the analyzer tries in order:
      1. Read existing report files from the repo
      2. Pull from SonarQube if configured
      3. Auto-detect and execute test command
    """

    def name(self) -> str:
        return "coverage"

    def dimension(self) -> str:
        return "coverage"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        mode = settings.get("mode", "auto")
        coverage_pct: Optional[float] = None
        source = "none"
        warnings: List[str] = []
        details: Dict[str, Any] = {"mode": mode}

        if mode == "report":
            coverage_pct, source = self._try_reports(repo_path, settings)
        elif mode == "sonarqube":
            coverage_pct = _fetch_sonarqube_coverage(settings)
            source = "sonarqube" if coverage_pct is not None else "none"
        elif mode == "execute":
            coverage_pct, source = self._try_execute(repo_path, settings)
        else:  # auto
            # 1. Try existing reports
            coverage_pct, source = self._try_reports(repo_path, settings)
            # 2. Try SonarQube
            if coverage_pct is None:
                coverage_pct = _fetch_sonarqube_coverage(settings)
                if coverage_pct is not None:
                    source = "sonarqube"
            # 3. Try executing tests
            if coverage_pct is None:
                coverage_pct, source = self._try_execute(repo_path, settings)

        if coverage_pct is None:
            warnings.append("No coverage data available from any source")
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=0.0,
                details={"mode": mode, "source": "none"},
                warnings=warnings,
            )

        coverage_pct = max(0.0, min(100.0, coverage_pct))
        details["source"] = source
        details["coverage_percentage"] = round(coverage_pct, 2)

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=round(coverage_pct, 2),  # coverage % IS the score
            details=details,
            warnings=warnings,
        )

    def _try_reports(self, repo_path: Path, settings: Dict[str, Any]) -> tuple:
        """Search for existing coverage report files in the repo."""
        # Check explicit report_path first
        explicit = settings.get("report_path")
        if explicit:
            p = Path(explicit)
            if not p.is_absolute():
                p = repo_path / p
            if p.is_file():
                for rp in _REPORT_PATTERNS:
                    result = rp.parser(p)
                    if result is not None:
                        return result, f"report:{p.name}"

        # Auto-discover report files
        for rp in _REPORT_PATTERNS:
            for match in repo_path.glob(rp.glob):
                result = rp.parser(match)
                if result is not None:
                    logger.info("Found coverage report: %s (%.1f%%)", match, result)
                    return result, f"report:{match.name}"

        return None, "none"

    def _try_execute(self, repo_path: Path, settings: Dict[str, Any]) -> tuple:
        """Execute a test command and then read the generated report."""
        timeout = settings.get("test_timeout", 300)

        # Custom command
        custom_cmd = settings.get("test_command")
        if custom_cmd:
            if isinstance(custom_cmd, str):
                custom_cmd = custom_cmd.split()
            logger.info("Running custom test command: %s", custom_cmd)
            success = _run_test_command(repo_path, custom_cmd, timeout)
            if success:
                pct, src = self._try_reports(repo_path, settings)
                if pct is not None:
                    return pct, f"execute:{src}"

        # Auto-detect based on build system markers
        for detect in _AUTO_DETECT_COMMANDS:
            marker = repo_path / detect["marker"]
            if marker.is_file():
                cmd = detect["cmd"]
                logger.info("Auto-detected build system (%s), running: %s", detect["marker"], cmd)
                success = _run_test_command(repo_path, cmd, timeout)
                if success:
                    pct, src = self._try_reports(repo_path, settings)
                    if pct is not None:
                        return pct, f"execute:{src}"

        return None, "none"
