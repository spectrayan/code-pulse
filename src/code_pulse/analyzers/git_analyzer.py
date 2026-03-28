"""Git churn, hotspot, and bugfix pattern analysis via GitPython."""

import logging
from pathlib import Path
from typing import Any, Dict, List

import git

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult

logger = logging.getLogger(__name__)

_BUGFIX_KEYWORDS = ("fix", "bug", "hotfix")

DEFAULT_MAX_COMMITS = 500

_SUPPORTED_EXTENSIONS = {".py", ".java", ".js", ".ts"}


def _normalize_churn(churn: int) -> float:
    """Normalize per-file churn count to a 0-100 score.

    Formula: max(0, 90 - churn * 2) clamped to [0, 100].
    """
    raw = 90.0 - churn * 2.0
    return max(0.0, min(100.0, raw))


def _is_bugfix_commit(message: str) -> bool:
    """Return True if the commit message contains a bugfix keyword."""
    lower = message.lower()
    return any(kw in lower for kw in _BUGFIX_KEYWORDS)


class GitAnalyzer(Analyzer):
    """Analyzer that uses GitPython to compute git churn and hotspot metrics."""

    def name(self) -> str:
        return "git"

    def dimension(self) -> str:
        return "git_risk"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Compute per-file churn counts, hotspots, and bugfix commit counts.

        Returns an AnalyzerResult with per-file normalized scores and details
        including churn counts, bugfix counts, and hotspot tags.
        """
        max_commits: int = settings.get("max_commits", DEFAULT_MAX_COMMITS)

        try:
            repo = git.Repo(str(repo_path), search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            logger.warning(
                "Path is not a git repository: %s. Skipping git analysis.",
                repo_path,
            )
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                per_file_scores={},
                details={},
                warnings=[f"Not a git repository: {repo_path}"],
            )

        git_root = Path(repo.working_dir).resolve()
        analyzed_path = repo_path.resolve()

        # Compute the prefix to filter files under the analyzed subdirectory
        try:
            sub_prefix = str(analyzed_path.relative_to(git_root))
        except ValueError:
            sub_prefix = ""

        churn_counts: Dict[str, int] = {}
        bugfix_counts: Dict[str, int] = {}

        commits: List[git.Commit] = list(
            repo.iter_commits(max_count=max_commits)
        )

        for commit in commits:
            is_bugfix = _is_bugfix_commit(commit.message)
            # Get the files changed in this commit
            changed_files = self._get_changed_files(commit)
            for file_path in changed_files:
                # Only track supported source files
                if not any(file_path.endswith(ext) for ext in _SUPPORTED_EXTENSIONS):
                    continue
                # Only track files under the analyzed subdirectory
                if sub_prefix and not file_path.startswith(sub_prefix):
                    continue
                # Convert to absolute path to match FileDiscovery output
                abs_path = str(git_root / file_path)
                churn_counts[abs_path] = churn_counts.get(abs_path, 0) + 1
                if is_bugfix:
                    bugfix_counts[abs_path] = bugfix_counts.get(abs_path, 0) + 1
                if is_bugfix:
                    bugfix_counts[file_path] = bugfix_counts.get(file_path, 0) + 1

        # Compute per-file scores and identify hotspots
        per_file_scores: Dict[str, float] = {}
        hotspots: List[str] = []
        file_details: Dict[str, Any] = {}

        for file_path, churn in churn_counts.items():
            score = _normalize_churn(churn)
            per_file_scores[file_path] = score
            is_hotspot = churn > 15
            if is_hotspot:
                hotspots.append(file_path)
            file_details[file_path] = {
                "churn": churn,
                "bugfix_commits": bugfix_counts.get(file_path, 0),
                "hotspot": is_hotspot,
            }

        # Overall score is average of per-file scores
        if per_file_scores:
            normalized_score = sum(per_file_scores.values()) / len(per_file_scores)
        else:
            normalized_score = 100.0

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=round(normalized_score, 2),
            per_file_scores=per_file_scores,
            details={
                "commits_analyzed": len(commits),
                "max_commits": max_commits,
                "file_count": len(per_file_scores),
                "hotspots": hotspots,
                "file_details": file_details,
            },
            warnings=[],
        )

    @staticmethod
    def _get_changed_files(commit: git.Commit) -> List[str]:
        """Return the list of file paths changed in a commit."""
        try:
            if commit.parents:
                diffs = commit.diff(commit.parents[0])
            else:
                # Initial commit — diff against empty tree
                diffs = commit.diff(git.NULL_TREE)
            return [
                diff.b_path or diff.a_path
                for diff in diffs
                if diff.b_path or diff.a_path
            ]
        except Exception as exc:
            logger.warning("Failed to get diff for commit %s: %s", commit.hexsha, exc)
            return []
