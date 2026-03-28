"""SonarQube REST API integration for pulling existing analysis results."""

import logging
from pathlib import Path
from typing import Any, Dict

import requests

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)

# Quality gate rating to normalized score mapping
_RATING_SCORES: Dict[str, float] = {
    "A": 100.0,
    "B": 80.0,
    "C": 60.0,
    "D": 40.0,
    "E": 20.0,
}


class SonarQubeAdapter(Analyzer):
    """Analyzer that pulls quality metrics from a SonarQube server via REST API."""

    def name(self) -> str:
        return "sonarqube"

    def dimension(self) -> str:
        return "sonarqube"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Retrieve SonarQube metrics and return a normalized score."""
        server_url = settings.get("server_url", "")
        token = settings.get("token", "")
        project_key = settings.get("project_key", "")

        if not server_url or not project_key:
            msg = "SonarQube server_url or project_key not configured; skipping"
            logger.warning(msg)
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=[msg],
            )

        base_url = server_url.rstrip("/")
        auth = (token, "") if token else None

        # Fetch quality gate status
        gate_score = self._fetch_quality_gate(base_url, auth, project_key)
        if gate_score is None:
            return self._skip_result()

        # Fetch component measures for finer-grained metrics
        measures = self._fetch_measures(base_url, auth, project_key)

        normalized_score = gate_score
        details: Dict[str, Any] = {"quality_gate_score": gate_score}

        if measures is not None:
            details["measures"] = measures
            # If we got a reliability_rating from measures, average it with gate score
            measure_scores = [
                _RATING_SCORES.get(v, gate_score)
                for k, v in measures.items()
                if k.endswith("_rating") and v in _RATING_SCORES
            ]
            if measure_scores:
                normalized_score = round(
                    (gate_score + sum(measure_scores)) / (1 + len(measure_scores)), 2
                )

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=max(0.0, min(100.0, normalized_score)),
            details=details,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_quality_gate(
        self, base_url: str, auth: Any, project_key: str
    ) -> float | None:
        """Call /api/qualitygates/project_status and return a normalized score."""
        url = f"{base_url}/api/qualitygates/project_status"
        params = {"projectKey": project_key}

        resp = self._safe_get(url, params, auth)
        if resp is None:
            return None

        try:
            data = resp.json()
            status = (
                data.get("projectStatus", {}).get("status", "").upper()
            )
        except (ValueError, AttributeError):
            logger.warning("Failed to parse SonarQube quality gate response")
            return None

        if status == "OK":
            return 100.0
        elif status == "ERROR":
            return 40.0
        # Fallback for WARN or unknown statuses
        return 60.0

    def _fetch_measures(
        self, base_url: str, auth: Any, project_key: str
    ) -> Dict[str, str] | None:
        """Call /api/measures/component and return a dict of metric key → value."""
        url = f"{base_url}/api/measures/component"
        metric_keys = ",".join([
            "reliability_rating",
            "security_rating",
            "sqale_rating",
            "coverage",
            "duplicated_lines_density",
        ])
        params = {"component": project_key, "metricKeys": metric_keys}

        resp = self._safe_get(url, params, auth)
        if resp is None:
            return None

        try:
            data = resp.json()
            measures_list = data.get("component", {}).get("measures", [])
            return {m["metric"]: m["value"] for m in measures_list if "metric" in m and "value" in m}
        except (ValueError, KeyError, TypeError):
            logger.warning("Failed to parse SonarQube measures response")
            return None

    def _safe_get(
        self, url: str, params: Dict[str, str], auth: Any
    ) -> requests.Response | None:
        """Perform a GET request with graceful error handling."""
        try:
            resp = requests.get(url, params=params, auth=auth, timeout=30)
        except requests.ConnectionError:
            logger.warning("SonarQube server unreachable at %s", url)
            return None
        except requests.Timeout:
            logger.warning("SonarQube request timed out: %s", url)
            return None
        except requests.RequestException as exc:
            logger.warning("SonarQube request failed: %s", exc)
            return None

        if resp.status_code in (401, 403):
            logger.warning("SonarQube authentication error (HTTP %d)", resp.status_code)
            return None
        if resp.status_code == 404:
            logger.warning("SonarQube project not found (HTTP 404)")
            return None
        if resp.status_code >= 400:
            logger.warning("SonarQube returned HTTP %d", resp.status_code)
            return None

        return resp

    def _skip_result(self) -> AnalyzerResult:
        """Return a default result when SonarQube data cannot be retrieved."""
        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=100.0,
            warnings=["SonarQube data unavailable; analysis skipped"],
        )
