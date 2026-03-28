"""Coding standards loader — discovers and loads standards from configured sources."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from code_pulse.core.models import CodingStandard, CodingStandardsConfig

logger = logging.getLogger(__name__)

_STANDARDS_DIR = Path(__file__).resolve().parent.parent / "standards"
_SYSTEM_DIR = _STANDARDS_DIR / "system"
_PREDEFINED_DIR = _STANDARDS_DIR / "predefined"

_SUPPORTED_EXTENSIONS = {".md", ".txt"}


class CodingStandardsLoader:
    """Discovers and loads coding standards from configured sources."""

    PREDEFINED_STANDARDS = {
        "solid-principles",
        "clean-code",
        "owasp-secure-coding",
        "google-style-python",
        "google-style-java",
        "airbnb-style-javascript",
    }

    # --- public API ---------------------------------------------------

    def load(
        self,
        settings: Union[Dict[str, Any], None] = None,
        *,
        standards_config: Optional[CodingStandardsConfig] = None,
    ) -> List[CodingStandard]:
        """Load standards from a CodingStandardsConfig or legacy settings dict.

        Prefer passing ``standards_config`` (top-level config). Falls back to
        reading ``settings["coding_standards"]`` for backward compatibility.
        """
        if standards_config is not None:
            return self._load_from_config(standards_config)

        # Legacy: read from analyzer settings dict
        cs = (settings or {}).get("coding_standards", {})
        mode = cs.get("mode", "system")

        if mode == "system":
            return self._load_system_standards()

        if mode == "predefined":
            names: List[str] = cs.get("predefined", [])
            return self._load_predefined_standards(names)

        if mode == "custom":
            custom_path = cs.get("custom_path", "")
            paths = [custom_path] if isinstance(custom_path, str) and custom_path else cs.get("custom_paths", [])
            return self._load_custom_paths(paths)

        if mode == "combined":
            standards: List[CodingStandard] = []
            standards.extend(self._load_system_standards())
            standards.extend(
                self._load_predefined_standards(cs.get("predefined", []))
            )
            paths = cs.get("custom_paths", [])
            if not paths:
                cp = cs.get("custom_path")
                if cp:
                    paths = [cp]
            standards.extend(self._load_custom_paths(paths))
            return standards

        logger.warning("Unknown coding_standards mode '%s', falling back to system", mode)
        return self._load_system_standards()

    def _load_from_config(self, cfg: CodingStandardsConfig) -> List[CodingStandard]:
        """Load standards from a top-level CodingStandardsConfig object."""
        if cfg.mode == "system":
            return self._load_system_standards()

        if cfg.mode == "predefined":
            return self._load_predefined_standards(cfg.predefined)

        if cfg.mode == "custom":
            return self._load_custom_paths(cfg.custom_paths)

        if cfg.mode == "combined":
            standards: List[CodingStandard] = []
            if cfg.system:
                standards.extend(self._load_system_standards())
            standards.extend(self._load_predefined_standards(cfg.predefined))
            standards.extend(self._load_custom_paths(cfg.custom_paths))
            return standards

        logger.warning("Unknown coding_standards mode '%s', falling back to system", cfg.mode)
        return self._load_system_standards()

    def _load_custom_paths(self, paths: List[str]) -> List[CodingStandard]:
        """Load custom standards from multiple directories."""
        standards: List[CodingStandard] = []
        for p in paths:
            if p:
                standards.extend(self._load_custom_standards(Path(p)))
        return standards

    # --- private helpers ----------------------------------------------

    def _load_system_standards(self) -> List[CodingStandard]:
        """Load built-in CodePulse default standards from the bundled system/ dir."""
        return self._load_dir(_SYSTEM_DIR, source="system")

    def _load_predefined_standards(self, names: List[str]) -> List[CodingStandard]:
        """Load named industry-standard rulesets from the bundled predefined/ dir."""
        standards: List[CodingStandard] = []
        for name in names:
            if name not in self.PREDEFINED_STANDARDS:
                logger.warning("Unknown predefined standard '%s', skipping", name)
                continue
            for ext in _SUPPORTED_EXTENSIONS:
                filepath = _PREDEFINED_DIR / f"{name}{ext}"
                if filepath.is_file():
                    std = self._read_file(filepath, source="predefined")
                    if std is not None:
                        standards.append(std)
                    break
            else:
                logger.warning(
                    "Predefined standard '%s' not found in %s", name, _PREDEFINED_DIR
                )
        return standards

    def _load_custom_standards(self, path: Path) -> List[CodingStandard]:
        """Load ``.md`` and ``.txt`` files from a user-specified directory."""
        if not path.exists():
            logger.warning("Custom standards path does not exist: %s", path)
            return []
        if not path.is_dir():
            logger.warning("Custom standards path is not a directory: %s", path)
            return []
        standards = self._load_dir(path, source="custom")
        if not standards:
            logger.warning("No .md or .txt files found in custom standards path: %s", path)
        return standards

    @staticmethod
    def filter_by_language(
        standards: List[CodingStandard], language: str
    ) -> List[CodingStandard]:
        """Return standards applicable to *language* (or with an empty languages list)."""
        return [
            s for s in standards
            if not s.languages or language in s.languages
        ]

    # --- file I/O helpers ---------------------------------------------

    @staticmethod
    def _load_dir(directory: Path, source: str) -> List[CodingStandard]:
        """Read all supported files from *directory* and return CodingStandard list."""
        standards: List[CodingStandard] = []
        if not directory.is_dir():
            return standards
        for filepath in sorted(directory.iterdir()):
            if filepath.suffix in _SUPPORTED_EXTENSIONS and filepath.is_file():
                std = CodingStandardsLoader._read_file(filepath, source=source)
                if std is not None:
                    standards.append(std)
        return standards

    @staticmethod
    def _read_file(filepath: Path, source: str) -> "CodingStandard | None":
        """Read a single standards file and return a ``CodingStandard``."""
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read standards file %s: %s", filepath, exc)
            return None

        name = filepath.stem
        languages = _infer_languages(name)
        return CodingStandard(
            name=name,
            content=content,
            languages=languages,
            source=source,
        )


def _infer_languages(name: str) -> List[str]:
    """Heuristically infer applicable languages from the standard's file name."""
    lower = name.lower()
    mapping: Dict[str, str] = {
        "python": "python",
        "java": "java",
        "javascript": "javascript",
        "typescript": "typescript",
    }
    langs: List[str] = []
    for keyword, lang in mapping.items():
        if keyword in lower:
            langs.append(lang)
    return langs
