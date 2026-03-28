"""Abstract base class for all CodePulse analyzers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from code_pulse.core.models import AnalyzerResult


class Analyzer(ABC):
    """Common interface all analyzer plugins must implement."""

    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this analyzer."""
        ...

    @abstractmethod
    def dimension(self) -> str:
        """Quality dimension this analyzer measures."""
        ...

    @abstractmethod
    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run analysis and return normalized results."""
        ...
