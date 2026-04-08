"""CLI entry point for CodePulse — parses arguments, builds and invokes the LangGraph workflow."""

import argparse
import logging
import os
import sys
from pathlib import Path

from code_pulse.core.config import ConfigError, ConfigLoader
from code_pulse.analyzers.registry import AnalyzerRegistry
from code_pulse.analyzers.lizard_analyzer import LizardAnalyzer
from code_pulse.analyzers.jscpd_analyzer import JscpdAnalyzer
from code_pulse.analyzers.semgrep_analyzer import SemgrepAnalyzer
from code_pulse.analyzers.sonarqube_adapter import SonarQubeAdapter
from code_pulse.analyzers.git_analyzer import GitAnalyzer
from code_pulse.analyzers.dependency_analyzer import DependencyAnalyzer
from code_pulse.analyzers.ownership_analyzer import OwnershipAnalyzer
from code_pulse.analyzers.agentic_analyzer import AgenticAnalyzer
from code_pulse.analyzers.coverage_analyzer import CoverageAnalyzer
from code_pulse.analyzers.prompt_scanner import PromptScanner
from code_pulse.engine.workflow import build_workflow


def _load_dotenv() -> None:
    """Load .env file from the current directory if it exists."""
    env_path = Path(".env")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    """Entry point for the ``code-pulse`` CLI command."""

    # 0. Load .env file if present
    _load_dotenv()

    # 1. Parse arguments
    parser = argparse.ArgumentParser(
        prog="code-pulse",
        description="CodePulse — AI-powered codebase maintainability analyzer",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to the repository to analyze (overrides config project.repo_path)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a YAML configuration file",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path for the Markdown report output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    # 2. Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(name)s: %(message)s")

    # 3. Load config (before repo path so we can use project.repo_path as fallback)
    #    Auto-discover codepulse-config.yaml in the current directory if no --config given.
    try:
        if args.config:
            config_path = Path(args.config)
            if not config_path.exists():
                print(f"Error: configuration file '{args.config}' does not exist", file=sys.stderr)
                sys.exit(1)
            config = ConfigLoader.load(config_path)
        elif Path("codepulse-config.yaml").is_file():
            config = ConfigLoader.load(Path("codepulse-config.yaml"))
        else:
            config = ConfigLoader.default()
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 4. Resolve repo path: CLI arg > config project.repo_path > current dir
    raw_path = args.path or config.project.repo_path or "."
    repo_path = Path(raw_path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Error: repository path '{raw_path}' does not exist or is not a directory", file=sys.stderr)
        sys.exit(1)

    # 5. Build registry and register all analyzers
    registry = AnalyzerRegistry()
    registry.register(LizardAnalyzer())
    registry.register(JscpdAnalyzer())
    registry.register(SemgrepAnalyzer())
    registry.register(SonarQubeAdapter())
    registry.register(GitAnalyzer())
    registry.register(DependencyAnalyzer())
    registry.register(OwnershipAnalyzer())
    registry.register(AgenticAnalyzer())
    registry.register(CoverageAnalyzer())
    registry.register(PromptScanner())

    # 6. Build and invoke the LangGraph workflow
    graph = build_workflow(config, registry)
    state = graph.invoke({
        "repo_path": str(repo_path),
        "config": config,
        "discovered_files": {},
        "results": [],
        "score": None,
        "trend": None,
        "cost": None,
        "ownership": None,
        "report": None,
    })

    # 7. Report is written to disk by the workflow's report_generator_node
    report_dir = config.report.output_dir
    print(f"Report written to: {report_dir}/")

    # 8. Print summary to stdout
    score = state.get("score")
    if score is not None:
        print(f"CodePulse Score: {score.final_score:.1f}")
        print(f"Tier: {score.tier}")
        print(f"Recommendation: {score.recommendation}")
        print(f"Files analyzed: {len(score.per_file_scores)}")
    else:
        print("No score computed.")
