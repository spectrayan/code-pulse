"""LangGraph state graph — orchestrates the full CodePulse analysis pipeline.

The graph structure:
  file_discovery -> [parallel analyzer nodes] -> collect_results
  -> scoring_engine -> trend_store -> cost_estimator -> report_generator -> END

Deterministic analyzer tool nodes and the Agentic Analyzer all run in
parallel after file discovery.  Each analyzer node is wrapped in error
handling so a single failure is logged and skipped without aborting the
pipeline.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from code_pulse.analyzers.registry import AnalyzerRegistry
from code_pulse.reporting.cost import CostEstimator
from code_pulse.core.discovery import FileDiscovery
from code_pulse.core.models import (
    AnalyzerResult,
    CodePulseScore,
    Config,
    CostEstimate,
    OwnershipData,
    ReportContext,
    TrendData,
    TrendEntry,
)
from code_pulse.reporting.report import ReportGenerator
from code_pulse.engine.scoring import ScoringEngine
from code_pulse.reporting.trend import TrendStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

def _merge_lists(left: List[Any], right: List[Any]) -> List[Any]:
    """Reducer that concatenates lists from parallel branches."""
    return left + right


class AnalysisState(TypedDict):
    repo_path: str
    config: Config
    discovered_files: Dict[str, List[str]]
    results: Annotated[List[AnalyzerResult], _merge_lists]
    score: Optional[CodePulseScore]
    trend: Optional[TrendData]
    cost: Optional[CostEstimate]
    ownership: Optional[OwnershipData]
    report: Optional[str]


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _file_discovery_node(state: AnalysisState) -> Dict[str, Any]:
    """Discover source files grouped by language."""
    repo_path = Path(state["repo_path"])
    config: Config = state["config"]
    extra_excludes = config.project.exclude_dirs if config.project else []
    exclude_patterns = config.project.exclude_patterns if config.project else []
    discovered = FileDiscovery.discover(
        repo_path,
        extra_exclude_dirs=extra_excludes,
        exclude_patterns=exclude_patterns,
    )
    # Convert Path objects to strings for serialisability
    discovered_str: Dict[str, List[str]] = {
        lang: [str(p) for p in paths] for lang, paths in discovered.items()
    }
    logger.info(
        "Discovered %d files across %d languages",
        sum(len(v) for v in discovered_str.values()),
        len(discovered_str),
    )
    return {"discovered_files": discovered_str}


def _make_analyzer_node(analyzer, config: Config, registry: AnalyzerRegistry):
    """Return a node function that runs a single analyzer.

    The node catches all exceptions so a failing analyzer never crashes the
    pipeline — it is logged and skipped.
    """
    ac = registry.resolve_analyzer_config(analyzer.name(), config)
    settings = dict(ac.settings) if ac else {}

    # Inject top-level coding_standards config into agentic analyzer settings
    if analyzer.name() in ("agentic", "llm"):
        settings["_coding_standards_config"] = config.coding_standards

    def _node(state: AnalysisState) -> Dict[str, Any]:
        repo_path = Path(state["repo_path"])
        try:
            result = analyzer.analyze(repo_path, settings)
            logger.info("Analyzer '%s' completed (score=%.1f)", analyzer.name(), result.normalized_score)
            return {"results": [result]}
        except Exception:
            logger.exception("Analyzer '%s' failed — skipping.", analyzer.name())
            return {"results": []}

    # Give the function a readable name for LangGraph introspection
    _node.__name__ = f"analyzer_{analyzer.name()}"
    _node.__qualname__ = _node.__name__
    return _node


def _collect_results_node(state: AnalysisState) -> Dict[str, Any]:
    """No-op merge point after parallel analyzer branches.

    LangGraph automatically merges state from parallel branches, so this
    node simply passes through.  It exists as a synchronisation barrier.
    """
    return {}


def _build_allowed_files(
    discovered: Dict[str, List[str]], repo_path: Path
) -> set:
    """Build the set of file paths that are allowed in the report."""
    allowed: set = set()
    for file_list in discovered.values():
        for fp in file_list:
            allowed.add(fp)
            try:
                allowed.add(str(Path(fp).relative_to(repo_path)))
            except ValueError:
                pass
    return allowed


def _filter_results_by_discovered(
    results: List[AnalyzerResult], allowed_files: set
) -> List[AnalyzerResult]:
    """Return results with per_file_scores filtered to only discovered files."""
    if not allowed_files:
        return results
    filtered: List[AnalyzerResult] = []
    for r in results:
        if r.per_file_scores:
            filtered_scores = {
                fp: sc for fp, sc in r.per_file_scores.items()
                if fp in allowed_files
            }
            filtered.append(AnalyzerResult(
                analyzer_name=r.analyzer_name,
                dimension=r.dimension,
                normalized_score=r.normalized_score,
                per_file_scores=filtered_scores,
                details=r.details,
                warnings=r.warnings,
                violations=r.violations,
            ))
        else:
            filtered.append(r)
    return filtered


def _scoring_engine_node(state: AnalysisState) -> Dict[str, Any]:
    """Compute the weighted ensemble CodePulse score."""
    config: Config = state["config"]
    results: List[AnalyzerResult] = state.get("results") or []
    repo_path = Path(state["repo_path"])

    discovered = state.get("discovered_files") or {}
    allowed_files = _build_allowed_files(discovered, repo_path)
    results = _filter_results_by_discovered(results, allowed_files)

    score = ScoringEngine.compute(results, config)
    logger.info("Scoring complete — final_score=%.1f, tier=%s", score.final_score, score.tier)

    # Extract ownership data from analyzer results if present
    ownership: Optional[OwnershipData] = None
    for r in results:
        od = r.details.get("ownership")
        if isinstance(od, OwnershipData):
            ownership = od
            break

    return {"score": score, "ownership": ownership}


def _trend_store_node(state: AnalysisState) -> Dict[str, Any]:
    """Persist the current score and load trend history."""
    score: CodePulseScore = state["score"]
    config: Config = state["config"]
    trend_path = Path(config.trend_store_path or ".codepulse-trend.jsonl")

    entry = TrendEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        score=score.final_score,
        tier=score.tier,
    )
    try:
        TrendStore.save(entry, trend_path)
        trend = TrendStore.load(trend_path)
    except Exception:
        logger.exception("Trend store failed — skipping trend data.")
        trend = TrendData()

    return {"trend": trend}


def _cost_estimator_node(state: AnalysisState) -> Dict[str, Any]:
    """Estimate cost-to-fix for reaching the next tier."""
    score: CodePulseScore = state["score"]
    results: List[AnalyzerResult] = state.get("results") or []
    try:
        cost = CostEstimator.estimate(score, results)
    except Exception:
        logger.exception("Cost estimation failed — skipping.")
        cost = None
    return {"cost": cost}


def _report_generator_node(state: AnalysisState) -> Dict[str, Any]:
    """Generate the Markdown report from all collected data."""
    score: CodePulseScore = state["score"]
    results: List[AnalyzerResult] = state.get("results") or []
    trend: Optional[TrendData] = state.get("trend")
    cost: Optional[CostEstimate] = state.get("cost")
    ownership: Optional[OwnershipData] = state.get("ownership")

    # Compute per-language score breakdowns
    per_language_scores: Dict[str, List[float]] = {}
    discovered = state.get("discovered_files") or {}
    for lang, file_paths in discovered.items():
        lang_scores: List[float] = []
        for fp in file_paths:
            if fp in score.per_file_scores:
                lang_scores.append(score.per_file_scores[fp])
        if lang_scores:
            per_language_scores[lang] = lang_scores

    per_lang_avg: Dict[str, float] = {
        lang: sum(scores) / len(scores)
        for lang, scores in per_language_scores.items()
        if scores
    }

    context = ReportContext(
        score=score,
        results=results,
        trend=trend,
        cost=cost,
        ownership=ownership,
        per_language_scores=per_lang_avg,
    )

    config: Config = state["config"]
    report_config = config.report
    output_dir = ReportGenerator.write_report(context, report_config)
    report = ReportGenerator.generate(context, report_config)
    return {"report": report}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_workflow(config: Config, registry: AnalyzerRegistry):
    """Build and compile the LangGraph state graph.

    Returns a compiled ``CompiledGraph`` that can be invoked with an
    ``AnalysisState`` dict.

    Graph topology::

        file_discovery
            ├─► analyzer_A ─┐
            ├─► analyzer_B ─┤
            └─► analyzer_N ─┤
                            ▼
                    collect_results
                            │
                    scoring_engine
                            │
                      trend_store
                            │
                    cost_estimator
                            │
                   report_generator
                            │
                           END
    """
    builder = StateGraph(AnalysisState)

    # --- Nodes ---
    builder.add_node("file_discovery", _file_discovery_node)

    enabled_analyzers = registry.get_enabled(config)
    analyzer_node_names: List[str] = []

    for analyzer in enabled_analyzers:
        node_name = f"analyzer_{analyzer.name()}"
        node_fn = _make_analyzer_node(analyzer, config, registry)
        builder.add_node(node_name, node_fn)
        analyzer_node_names.append(node_name)

    builder.add_node("collect_results", _collect_results_node)
    builder.add_node("scoring_engine", _scoring_engine_node)
    builder.add_node("trend_store", _trend_store_node)
    builder.add_node("cost_estimator", _cost_estimator_node)
    builder.add_node("report_generator", _report_generator_node)

    # --- Edges ---
    builder.set_entry_point("file_discovery")

    if analyzer_node_names:
        # Fan-out: file_discovery -> each analyzer node
        for node_name in analyzer_node_names:
            builder.add_edge("file_discovery", node_name)
            # Fan-in: each analyzer node -> collect_results
            builder.add_edge(node_name, "collect_results")
    else:
        # No analyzers enabled — skip straight to collect_results
        builder.add_edge("file_discovery", "collect_results")

    # Sequential post-analysis pipeline
    builder.add_edge("collect_results", "scoring_engine")
    builder.add_edge("scoring_engine", "trend_store")
    builder.add_edge("trend_store", "cost_estimator")
    builder.add_edge("cost_estimator", "report_generator")
    builder.add_edge("report_generator", END)

    return builder.compile()
