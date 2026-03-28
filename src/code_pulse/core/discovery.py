"""Multi-language file discovery for CodePulse."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
}


def _compile_patterns(patterns: List[str]) -> List[Pattern]:
    """Compile a list of regex strings, skipping invalid ones."""
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            pass  # skip invalid patterns silently
    return compiled


class FileDiscovery:
    """Discovers source files in the repository, grouped by language."""

    SUPPORTED_EXTENSIONS = {".py", ".java", ".js", ".ts"}
    EXCLUDED_DIRS = {"node_modules", ".git", "__pycache__", "build", "dist", ".venv", "venv"}

    @staticmethod
    def discover(
        repo_path: Path,
        extra_exclude_dirs: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, List[Path]]:
        """Walk directory tree, skip excluded dirs/patterns, group files by language.

        Args:
            repo_path: Root directory to scan.
            extra_exclude_dirs: Additional directory names to skip.
            exclude_patterns: Regex patterns — files whose path (relative to
                repo_path) matches any pattern are excluded.
        """
        excluded = FileDiscovery.EXCLUDED_DIRS | set(extra_exclude_dirs or [])
        compiled = _compile_patterns(exclude_patterns or [])
        result: Dict[str, List[Path]] = {}

        for dirpath, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [d for d in dirnames if d not in excluded]

            for filename in filenames:
                ext = Path(filename).suffix
                if ext not in FileDiscovery.SUPPORTED_EXTENSIONS:
                    continue

                filepath = Path(dirpath) / filename

                # Apply regex exclude patterns against the relative path
                if compiled:
                    try:
                        rel = str(filepath.relative_to(repo_path))
                    except ValueError:
                        rel = str(filepath)
                    if any(pat.search(rel) for pat in compiled):
                        continue

                language = EXTENSION_TO_LANGUAGE[ext]
                result.setdefault(language, []).append(filepath)

        return result
