"""Analyzer registry — discovers, stores, and runs analyzer plugins."""

import logging
from pathlib import Path
from typing import Dict, List

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerConfig, AnalyzerResult, Config

logger = logging.getLogger(__name__)


class AnalyzerRegistry:
    """Discovers, stores, and manages Analyzer plugins."""

    def __init__(self) -> None:
        self._analyzers: Dict[str, Analyzer] = {}

    def register(self, analyzer: Analyzer) -> None:
        """Register an analyzer instance by its name."""
        self._analyzers[analyzer.name()] = analyzer

    # Map of analyzer names to their config key aliases
    _CONFIG_ALIASES: Dict[str, str] = {"agentic": "llm"}

    def resolve_analyzer_config(
        self, analyzer_name: str, config: Config
    ) -> "AnalyzerConfig | None":
        """Look up the AnalyzerConfig for an analyzer, respecting aliases."""
        ac = config.analyzers.get(analyzer_name)
        if ac is None and analyzer_name in self._CONFIG_ALIASES:
            ac = config.analyzers.get(self._CONFIG_ALIASES[analyzer_name])
        return ac

    def get_enabled(self, config: Config) -> List[Analyzer]:
        """Return analyzers that are enabled in the given config.

        An analyzer is considered enabled when:
        - It has an entry in ``config.analyzers`` with ``enabled=True``, **or**
        - It has no entry in ``config.analyzers`` (default: enabled).
        """
        enabled: List[Analyzer] = []
        for name, analyzer in self._analyzers.items():
            ac = self.resolve_analyzer_config(name, config)
            if ac is None or ac.enabled:
                enabled.append(analyzer)
        return enabled

    def run_all(self, repo_path: Path, config: Config) -> List[AnalyzerResult]:
        """Run all enabled analyzers, catching and logging exceptions.

        Analyzers that raise are skipped — their results are omitted from the
        returned list so the pipeline can continue with the remaining analyzers.
        """
        results: List[AnalyzerResult] = []
        for analyzer in self.get_enabled(config):
            ac = self.resolve_analyzer_config(analyzer.name(), config)
            settings = ac.settings if ac else {}
            try:
                result = analyzer.analyze(repo_path, settings)
                results.append(result)
            except Exception:
                logger.exception(
                    "Analyzer '%s' failed — skipping.", analyzer.name()
                )
        return results
