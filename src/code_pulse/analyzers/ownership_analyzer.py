"""Code ownership analysis via git blame — determines primary author per file."""

import logging
from pathlib import Path
from typing import Any, Dict, List

import git

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.discovery import FileDiscovery
from code_pulse.core.models import AnalyzerResult, AuthorStats, OwnershipData

logger = logging.getLogger(__name__)


class OwnershipAnalyzer(Analyzer):
    """Analyzer that uses git blame to determine primary author per file."""

    def name(self) -> str:
        return "ownership"

    def dimension(self) -> str:
        return "ownership"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run git blame on each supported source file to find primary authors.

        For each file, counts lines per author via ``git.Repo.blame()``.
        The primary author is the one with the most blamed lines.
        Stores ``OwnershipData`` (file_to_author mapping and AuthorStats) in
        details for use by the ReportGenerator.

        The normalized_score is set to 0.0 because ownership is informational
        (weight defaults to 0.0).
        """
        try:
            repo = git.Repo(str(repo_path), search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            logger.warning(
                "Path is not a git repository: %s. Skipping ownership analysis.",
                repo_path,
            )
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=0.0,
                details={"ownership": OwnershipData()},
                warnings=[f"Not a git repository: {repo_path}"],
            )

        discovered = FileDiscovery.discover(repo_path)
        all_files: List[Path] = [f for files in discovered.values() for f in files]

        file_to_author: Dict[str, str] = {}
        # author -> list of relative file paths
        author_files: Dict[str, List[str]] = {}

        for filepath in all_files:
            try:
                rel_path = str(filepath.relative_to(repo_path))
            except ValueError:
                rel_path = str(filepath)

            primary = self._primary_author(repo, rel_path)
            if primary is None:
                continue

            file_to_author[rel_path] = primary
            author_files.setdefault(primary, []).append(rel_path)

        # Build AuthorStats (average_score and hotspot_count are placeholders
        # here — they are populated later by the report generator when
        # per-file scores from other analyzers are available).
        author_stats: List[AuthorStats] = [
            AuthorStats(
                author=author,
                file_count=len(files),
                average_score=0.0,
                hotspot_count=0,
            )
            for author, files in author_files.items()
        ]

        ownership_data = OwnershipData(
            authors=author_stats,
            file_to_author=file_to_author,
        )

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=0.0,
            details={"ownership": ownership_data},
            warnings=[],
        )

    @staticmethod
    def _primary_author(repo: git.Repo, rel_path: str) -> str | None:
        """Return the author with the most blamed lines for *rel_path*.

        Returns ``None`` when blame data cannot be obtained (e.g. the file
        is not tracked or binary).
        """
        try:
            blame_data = repo.blame("HEAD", rel_path)
        except Exception as exc:
            logger.debug("Could not blame %s: %s", rel_path, exc)
            return None

        line_counts: Dict[str, int] = {}
        for commit, lines in blame_data:
            author = commit.author.name or "Unknown"
            line_counts[author] = line_counts.get(author, 0) + len(lines)

        if not line_counts:
            return None

        return max(line_counts, key=lambda a: line_counts[a])
