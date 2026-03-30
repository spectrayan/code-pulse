"""Validation logic for CodePulse configuration, split from ConfigLoader (SRP)."""

from typing import Any, Dict

from code_pulse.core.models import (
    AnalyzerConfig,
    CodingStandardsConfig,
    ProjectConfig,
    ReportConfig,
)


class ConfigError(Exception):
    """Raised when configuration validation fails.

    Includes the field name and expected type in the message.
    """

    def __init__(self, field: str, expected_type: str, detail: str = "") -> None:
        self.field = field
        self.expected_type = expected_type
        msg = f"Configuration error for field '{field}': expected {expected_type}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class ConfigValidator:
    """Validates raw parsed YAML data and returns typed config objects."""

    @staticmethod
    def parse_project(raw: Any) -> ProjectConfig:
        """Parse the top-level project section."""
        if raw is None:
            return ProjectConfig()
        if not isinstance(raw, dict):
            raise ConfigError("project", "dict (YAML mapping)")
        repo_path = raw.get("repo_path")
        if repo_path is not None and not isinstance(repo_path, str):
            raise ConfigError("project.repo_path", "str")
        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise ConfigError("project.name", "str")
        languages = raw.get("languages", [])
        if not isinstance(languages, list):
            raise ConfigError("project.languages", "list")
        exclude_dirs = raw.get("exclude_dirs", [])
        if not isinstance(exclude_dirs, list):
            raise ConfigError("project.exclude_dirs", "list")
        exclude_patterns = raw.get("exclude_patterns", [])
        if not isinstance(exclude_patterns, list):
            raise ConfigError("project.exclude_patterns", "list")
        return ProjectConfig(
            repo_path=repo_path, name=name, languages=languages,
            exclude_dirs=exclude_dirs, exclude_patterns=exclude_patterns,
        )

    @staticmethod
    def parse_coding_standards(raw: Any) -> CodingStandardsConfig:
        """Parse the top-level coding_standards section."""
        if raw is None:
            return CodingStandardsConfig()
        if not isinstance(raw, dict):
            raise ConfigError("coding_standards", "dict (YAML mapping)")

        mode = raw.get("mode", "system")
        if not isinstance(mode, str):
            raise ConfigError("coding_standards.mode", "str")
        valid_modes = {"system", "predefined", "custom", "combined"}
        if mode not in valid_modes:
            raise ConfigError("coding_standards.mode", f"one of {sorted(valid_modes)}", f"got '{mode}'")

        custom_paths = raw.get("custom_paths", [])
        if isinstance(custom_paths, str):
            custom_paths = [custom_paths]
        if not isinstance(custom_paths, list):
            raise ConfigError("coding_standards.custom_paths", "list or str")

        predefined = raw.get("predefined", [])
        if not isinstance(predefined, list):
            raise ConfigError("coding_standards.predefined", "list")

        system = raw.get("system", True)
        if not isinstance(system, bool):
            raise ConfigError("coding_standards.system", "bool")

        predefined_overrides = raw.get("predefined_overrides", {})
        if not isinstance(predefined_overrides, dict):
            raise ConfigError("coding_standards.predefined_overrides", "dict (YAML mapping)")
        for k, v in predefined_overrides.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ConfigError("coding_standards.predefined_overrides", "dict of str -> str")

        return CodingStandardsConfig(
            mode=mode, custom_paths=custom_paths, predefined=predefined,
            system=system, predefined_overrides=predefined_overrides
        )

    @staticmethod
    def parse_report(raw: Any) -> ReportConfig:
        """Parse the top-level report section."""
        if raw is None:
            return ReportConfig()
        if not isinstance(raw, dict):
            raise ConfigError("report", "dict (YAML mapping)")
        level = raw.get("level", "detailed")
        if level not in ("summary", "detailed"):
            raise ConfigError("report.level", "'summary' or 'detailed'", f"got '{level}'")
        output_dir = raw.get("output_dir", "codepulse-report")
        if not isinstance(output_dir, str):
            raise ConfigError("report.output_dir", "str")
        files_per_page = raw.get("files_per_page", 100)
        if not isinstance(files_per_page, int):
            raise ConfigError("report.files_per_page", "int")
        return ReportConfig(level=level, output_dir=output_dir, files_per_page=files_per_page)

    @staticmethod
    def parse_analyzer(name: str, section: Any) -> AnalyzerConfig:
        """Validate and build an AnalyzerConfig from a raw YAML section."""
        if not isinstance(section, dict):
            raise ConfigError(f"analyzers.{name}", "dict (YAML mapping)")

        enabled = section.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"analyzers.{name}.enabled", "bool")

        weight = section.get("weight", 1.0)
        if not isinstance(weight, (int, float)):
            raise ConfigError(f"analyzers.{name}.weight", "float")
        weight = float(weight)
        if weight < 0.0 or weight > 1.0:
            raise ConfigError(
                f"analyzers.{name}.weight",
                "float in [0.0, 1.0]",
                f"got {weight}",
            )

        settings = section.get("settings", {})
        if settings is not None and not isinstance(settings, dict):
            raise ConfigError(f"analyzers.{name}.settings", "dict (YAML mapping)")
        if settings is None:
            settings = {}

        ConfigValidator._validate_analyzer_settings(name, settings)

        return AnalyzerConfig(enabled=enabled, weight=weight, settings=settings)

    @staticmethod
    def _validate_analyzer_settings(name: str, settings: Dict[str, Any]) -> None:
        """Run analyzer-specific validation on the settings dict."""
        if not settings:
            return

        if name == "sonarqube":
            ConfigValidator._validate_sonarqube(settings)
        elif name == "git":
            ConfigValidator._validate_git(settings)
        elif name in ("llm", "agentic"):
            ConfigValidator._validate_llm(settings)

    @staticmethod
    def _validate_sonarqube(settings: Dict[str, Any]) -> None:
        for key in ("server_url", "token", "project_key"):
            val = settings.get(key)
            if val is not None and not isinstance(val, str):
                raise ConfigError(
                    f"analyzers.sonarqube.settings.{key}", "str"
                )

    @staticmethod
    def _validate_git(settings: Dict[str, Any]) -> None:
        mc = settings.get("max_commits")
        if mc is not None and not isinstance(mc, int):
            raise ConfigError(
                "analyzers.git.settings.max_commits", "int"
            )

    @staticmethod
    def _validate_llm(settings: Dict[str, Any]) -> None:
        prefix = "analyzers.llm.settings"

        strategy = settings.get("aggregation_strategy")
        if strategy is not None:
            if not isinstance(strategy, str):
                raise ConfigError(f"{prefix}.aggregation_strategy", "str")
            valid = {"median", "average", "conservative"}
            if strategy not in valid:
                raise ConfigError(
                    f"{prefix}.aggregation_strategy",
                    f"one of {sorted(valid)}",
                    f"got '{strategy}'",
                )

        cs = settings.get("coding_standards")
        if cs is not None:
            if not isinstance(cs, dict):
                raise ConfigError(f"{prefix}.coding_standards", "dict")
            ConfigValidator._validate_coding_standards(cs, prefix)

        providers = settings.get("providers")
        if providers is not None:
            if not isinstance(providers, list):
                raise ConfigError(f"{prefix}.providers", "list")
            for idx, prov in enumerate(providers):
                ConfigValidator._validate_provider(prov, f"{prefix}.providers[{idx}]")

        obs = settings.get("observability")
        if obs is not None and not isinstance(obs, dict):
            raise ConfigError(f"{prefix}.observability", "dict")

    @staticmethod
    def _validate_coding_standards(cs: Dict[str, Any], prefix: str) -> None:
        cs_prefix = f"{prefix}.coding_standards"
        mode = cs.get("mode")
        if mode is not None:
            if not isinstance(mode, str):
                raise ConfigError(f"{cs_prefix}.mode", "str")
            valid_modes = {"system", "predefined", "custom", "combined"}
            if mode not in valid_modes:
                raise ConfigError(
                    f"{cs_prefix}.mode",
                    f"one of {sorted(valid_modes)}",
                    f"got '{mode}'",
                )

        custom_path = cs.get("custom_path")
        if custom_path is not None and not isinstance(custom_path, str):
            raise ConfigError(f"{cs_prefix}.custom_path", "str")

        predefined = cs.get("predefined")
        if predefined is not None and not isinstance(predefined, list):
            raise ConfigError(f"{cs_prefix}.predefined", "list")

        system = cs.get("system")
        if system is not None and not isinstance(system, bool):
            raise ConfigError(f"{cs_prefix}.system", "bool")

    @staticmethod
    def _validate_provider(prov: Any, prefix: str) -> None:
        if not isinstance(prov, dict):
            raise ConfigError(prefix, "dict")

        name = prov.get("name")
        if name is None:
            raise ConfigError(f"{prefix}.name", "str", "field is required")
        if not isinstance(name, str):
            raise ConfigError(f"{prefix}.name", "str")

        model = prov.get("model")
        if model is None:
            raise ConfigError(f"{prefix}.model", "str", "field is required")
        if not isinstance(model, str):
            raise ConfigError(f"{prefix}.model", "str")

        api_key = prov.get("api_key")
        if api_key is not None and not isinstance(api_key, str):
            raise ConfigError(f"{prefix}.api_key", "str")

        max_retries = prov.get("max_retries")
        if max_retries is not None and not isinstance(max_retries, int):
            raise ConfigError(f"{prefix}.max_retries", "int")

        weight = prov.get("weight")
        if weight is not None:
            if not isinstance(weight, (int, float)):
                raise ConfigError(f"{prefix}.weight", "float")
            w = float(weight)
            if w < 0.0 or w > 1.0:
                raise ConfigError(
                    f"{prefix}.weight",
                    "float in [0.0, 1.0]",
                    f"got {w}",
                )

    # ------------------------------------------------------------------
    # Generic field helpers
    # ------------------------------------------------------------------

    @staticmethod
    def optional_str(data: Dict[str, Any], key: str) -> Any:
        val = data.get(key)
        if val is not None and not isinstance(val, str):
            raise ConfigError(key, "str")
        return val

    @staticmethod
    def optional_float(data: Dict[str, Any], key: str) -> Any:
        val = data.get(key)
        if val is not None and not isinstance(val, (int, float)):
            raise ConfigError(key, "float")
        return float(val) if val is not None else None
