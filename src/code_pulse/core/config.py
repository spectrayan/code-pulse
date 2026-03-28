"""YAML configuration loading for CodePulse.

Reading and environment-variable expansion live here; all validation
logic is in ``config_validator.py`` (SRP split).
"""

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml

from code_pulse.core.config_validator import ConfigError, ConfigValidator
from code_pulse.core.models import AnalyzerConfig, Config

# Re-export so existing ``from code_pulse.core.config import ConfigError`` still works.
__all__ = ["ConfigError", "ConfigLoader"]


def _expand_env_vars(obj: Any) -> Any:
    """Recursively expand ${VAR} references in strings to env var values."""
    if isinstance(obj, str):
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            obj,
        )
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


class ConfigLoader:
    """Reads YAML configuration files and delegates validation to ConfigValidator."""

    # Analyzers that ship by default with equal weights
    _DEFAULT_ANALYZERS = [
        "lizard",
        "jscpd",
        "semgrep",
        "sonarqube",
        "git",
        "llm",
        "dependency",
        "coverage",
        "ownership",
    ]

    @staticmethod
    def load(path: Path) -> Config:
        """Read a YAML config file, validate it, and return a Config object.

        Raises:
            ConfigError: on missing/invalid fields or out-of-range weights.
            FileNotFoundError: if *path* does not exist.
        """
        raw_text = path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise ConfigError("config_file", "valid YAML", str(exc)) from exc

        # Expand ${VAR} references to environment variable values
        data = _expand_env_vars(data)

        if not isinstance(data, dict):
            raise ConfigError("config_file", "dict (YAML mapping)", "top-level value is not a mapping")

        # --- Delegate validation to ConfigValidator ---
        project = ConfigValidator.parse_project(data.get("project"))
        coding_standards = ConfigValidator.parse_coding_standards(data.get("coding_standards"))
        report = ConfigValidator.parse_report(data.get("report"))

        analyzers: Dict[str, AnalyzerConfig] = {}
        raw_analyzers = data.get("analyzers", {})
        if raw_analyzers is not None:
            if not isinstance(raw_analyzers, dict):
                raise ConfigError("analyzers", "dict (YAML mapping)")
            for name, section in raw_analyzers.items():
                analyzers[name] = ConfigValidator.parse_analyzer(name, section)

        output_path = ConfigValidator.optional_str(data, "output_path")
        trend_store_path = ConfigValidator.optional_str(data, "trend_store_path")
        if trend_store_path is None:
            trend_store_path = ".codepulse-trend.jsonl"

        ci_threshold = ConfigValidator.optional_float(data, "ci_threshold")

        return Config(
            project=project,
            coding_standards=coding_standards,
            report=report,
            analyzers=analyzers,
            output_path=output_path,
            trend_store_path=trend_store_path,
            ci_threshold=ci_threshold,
        )

    @staticmethod
    def default() -> Config:
        """Return a sensible default Config with all analyzers enabled at equal weights."""
        weight = round(1.0 / len(ConfigLoader._DEFAULT_ANALYZERS), 4)
        analyzers = {
            name: AnalyzerConfig(enabled=True, weight=weight)
            for name in ConfigLoader._DEFAULT_ANALYZERS
        }
        return Config(
            analyzers=analyzers,
            output_path="codepulse-report.md",
            trend_store_path=".codepulse-trend.jsonl",
            ci_threshold=60.0,
        )
