"""Markdown report generator for CodePulse — powered by Jinja2 templates.

Supports two report levels:
  - "summary": High-level overview without per-file details (single file)
  - "detailed": Full report split across multiple files in a report directory

For detailed mode, the output structure is:
  {output_dir}/
    index.md              — Main report with summary, charts, links to detail pages
    files-001.md          — Per-file scores (page 1)
    files-002.md          — Per-file scores (page 2)
    ...
    violations.md         — Coding standards violations (if any)
    team-insights.md      — Team/ownership insights (if available)
    ai-insights.md        — AI/LLM analysis insights (if available)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from jinja2 import Environment, PackageLoader, select_autoescape

from code_pulse.core.models import AnalyzerResult, ReportConfig, ReportContext


# ---------------------------------------------------------------------------
# Jinja2 environment setup
# ---------------------------------------------------------------------------

def _create_jinja_env() -> Environment:
    """Create and configure the Jinja2 template environment."""
    env = Environment(
        loader=PackageLoader("code_pulse.reporting", "templates"),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    # Custom filters
    env.filters["fmt_score"] = lambda v: f"{v:.1f}"
    env.filters["fmt_int"] = lambda v: f"{v:.0f}"
    env.filters["join_quoted"] = lambda vals: ", ".join(f'"{d}"' for d in vals)
    env.filters["join_scores"] = lambda vals: ", ".join(f"{v:.1f}" for v in vals)
    return env


_ENV = _create_jinja_env()


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def _hotspot_files(results: List[AnalyzerResult]) -> Set[str]:
    hotspots: Set[str] = set()
    for r in results:
        if r.analyzer_name == "git":
            for fpath in r.details.get("hotspots", []):
                hotspots.add(fpath)
    return hotspots


def _high_complexity_files(results: List[AnalyzerResult]) -> Set[str]:
    complex_files: Set[str] = set()
    for r in results:
        if r.dimension == "complexity":
            for fpath, fscore in r.per_file_scores.items():
                if fscore < 40:
                    complex_files.add(fpath)
    return complex_files


def _refactor_suggestions(results: List[AnalyzerResult]) -> Dict[str, List[str]]:
    suggestions: Dict[str, List[str]] = {}
    for r in results:
        file_suggestions = r.details.get("refactor_suggestions", {})
        if isinstance(file_suggestions, dict):
            for fpath, suggs in file_suggestions.items():
                if isinstance(suggs, list):
                    suggestions.setdefault(fpath, []).extend(suggs)
    return suggestions


def _collect_violations(results: List[AnalyzerResult]) -> list:
    violations = []
    for r in results:
        for v in r.violations:
            violations.append(v)
    return violations


def _tier_buckets(per_file: Dict[str, float]) -> Dict[str, int]:
    buckets = {"excellent": 0, "good": 0, "poor": 0, "critical": 0}
    for s in per_file.values():
        if s >= 80:
            buckets["excellent"] += 1
        elif s >= 60:
            buckets["good"] += 1
        elif s >= 40:
            buckets["poor"] += 1
        else:
            buckets["critical"] += 1
    return buckets


def _get_ai_insights(results: List[AnalyzerResult]) -> Optional[Dict[str, Any]]:
    """Extract AI insights data from agentic analyzer results."""
    for r in results:
        if r.analyzer_name == "agentic":
            return {
                "suggestions": r.details.get("refactor_suggestions", {}),
                "per_file_llm_details": r.details.get("per_file_llm_details", {}),
                "strategy": r.details.get("aggregation_strategy", "median"),
                "violations": r.violations,
            }
    return None


def _get_prompt_security_data(results: List[AnalyzerResult]) -> Optional[Dict[str, Any]]:
    """Extract prompt security scan data from prompt_scanner results."""
    for r in results:
        if r.analyzer_name == "prompt_scanner":
            total = r.details.get("total_threats", 0)
            if total == 0 and not r.details.get("threats"):
                return None
            return {
                "total_threats": total,
                "severity_summary": r.details.get("severity_summary", {}),
                "category_summary": r.details.get("category_summary", {}),
                "threats": r.details.get("threats", []),
                "files_scanned": r.details.get("files_scanned", 0),
                "score": r.normalized_score,
            }
    return None


def _ai_insights_data(results: List[AnalyzerResult]) -> Optional[Dict[str, Any]]:
    """Structured AI insights data for the index/summary template."""
    data = _get_ai_insights(results)
    if not data:
        return None
    suggestions = data["suggestions"]
    details = data["per_file_llm_details"]
    if not details and not suggestions:
        return None

    total_suggestions = sum(len(v) for v in suggestions.values())
    total_violations = len(data["violations"])

    worst_files: List[Tuple[str, float]] = []
    if details:
        scored = []
        for fp, provider_results in details.items():
            avg = sum(r.get("overall_score", 50) for r in provider_results) / len(provider_results)
            scored.append((fp, avg))
        scored.sort(key=lambda x: x[1])
        worst = scored[:5]
        if worst and worst[0][1] < 80:
            worst_files = worst

    return {
        "total_files": len(details),
        "strategy": data["strategy"],
        "total_suggestions": total_suggestions,
        "suggestion_file_count": len(suggestions),
        "total_violations": total_violations,
        "worst_files": worst_files,
    }


# ---------------------------------------------------------------------------
# Template context builders
# ---------------------------------------------------------------------------

def _build_summary_context(ctx: ReportContext) -> Dict[str, Any]:
    """Build the template context dict shared by summary and index pages."""
    score = ctx.score
    return {
        "score": score,
        "total_files": len(score.per_file_scores),
        "buckets": _tier_buckets(score.per_file_scores),
        "dims": score.dimension_scores,
        "per_file": score.per_file_scores,
        "trend": ctx.trend,
        "cost": ctx.cost,
        "per_language_scores": ctx.per_language_scores,
        "ai_data": _ai_insights_data(ctx.results),
        "prompt_security": _get_prompt_security_data(ctx.results),
        "ownership_count": len(ctx.ownership.authors) if ctx.ownership and ctx.ownership.authors else 0,
    }


def _build_file_detail_rows(
    file_items: List[Tuple[str, float]],
    hotspots: Set[str],
    complex_files: Set[str],
    suggestions: Dict[str, List[str]],
) -> List[Tuple[str, float, str, str, str]]:
    """Build row tuples for the file detail template."""
    rows = []
    for fpath, fscore in file_items:
        tags: List[str] = []
        if fpath in hotspots:
            tags.append("hotspot")
        if fpath in complex_files:
            tags.append("high_complexity")
        tag_str = ", ".join(tags) if tags else "-"
        sugg_list = suggestions.get(fpath, [])
        sugg_str = "; ".join(sugg_list) if sugg_list else "-"
        short = fpath.split("/")[-1] if "/" in fpath else fpath
        rows.append((fpath, fscore, tag_str, sugg_str, short))
    return rows


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Produces Markdown reports using Jinja2 templates."""

    @staticmethod
    def generate(context: ReportContext, report_config: Optional[ReportConfig] = None) -> str:
        """Generate report content. Returns the main report as a string.

        For summary mode: returns a single markdown string (no file details).
        For detailed mode: call write_report() instead to get multi-file output.
        """
        cfg = report_config or ReportConfig()
        template = _ENV.get_template("summary.md.j2")
        tpl_ctx = _build_summary_context(context)
        return template.render(**tpl_ctx)

    @staticmethod
    def write_report(
        context: ReportContext,
        report_config: Optional[ReportConfig] = None,
        output_dir: Optional[str] = None,
    ) -> str:
        """Write the full report to disk. Returns the output directory path.

        Summary mode: writes a single index.md
        Detailed mode: writes index.md + paginated file details + violations + team insights
        """
        cfg = report_config or ReportConfig()
        out_dir = Path(output_dir or cfg.output_dir)
        # Clean previous report artifacts so stale files don't linger
        if out_dir.exists():
            for old_file in out_dir.glob("*.md"):
                old_file.unlink()
        out_dir.mkdir(parents=True, exist_ok=True)

        tpl_ctx = _build_summary_context(context)

        if cfg.level == "summary":
            index_ctx = {
                **tpl_ctx,
                "file_page_links": [],
                "violations_count": 0,
            }
            content = _ENV.get_template("index.md.j2").render(**index_ctx)
            (out_dir / "index.md").write_text(content, encoding="utf-8")
            # Still write AI insights even in summary mode
            ReportGenerator._write_ai_insights(context, out_dir)
            # Still write prompt security even in summary mode
            ReportGenerator._write_prompt_security(context, out_dir)
            return str(out_dir)

        # --- Detailed mode: multi-file ---
        # Build index-specific context
        total_files = len(context.score.per_file_scores)
        total_pages = max(1, (total_files + cfg.files_per_page - 1) // cfg.files_per_page) if total_files > 0 else 0
        file_page_links = []
        for i in range(1, total_pages + 1):
            start = (i - 1) * cfg.files_per_page + 1
            end = min(i * cfg.files_per_page, total_files)
            file_page_links.append(f"[Files {start}–{end}](files-{i:03d}.md)")

        violations = _collect_violations(context.results)

        index_ctx = {
            **tpl_ctx,
            "file_page_links": file_page_links,
            "violations_count": len(violations) if violations else 0,
        }
        index_content = _ENV.get_template("index.md.j2").render(**index_ctx)
        (out_dir / "index.md").write_text(index_content, encoding="utf-8")

        # Per-file detail pages
        ReportGenerator._write_file_pages(context, cfg, out_dir)

        # Violations page
        if violations:
            viol_content = _ENV.get_template("violations.md.j2").render(violations=violations)
            (out_dir / "violations.md").write_text(viol_content, encoding="utf-8")

        # Team insights page
        if context.ownership is not None and context.ownership.authors:
            team_content = _ENV.get_template("team_insights.md.j2").render(
                authors=context.ownership.authors
            )
            (out_dir / "team-insights.md").write_text(team_content, encoding="utf-8")

        # AI insights page
        ReportGenerator._write_ai_insights(context, out_dir)

        # Prompt security page
        ReportGenerator._write_prompt_security(context, out_dir)

        return str(out_dir)

    @staticmethod
    def _write_ai_insights(context: ReportContext, out_dir: Path) -> None:
        """Write the AI insights page if data is available."""
        data = _get_ai_insights(context.results)
        if not data:
            return
        details = data["per_file_llm_details"]
        suggestions = data["suggestions"]
        if not details and not suggestions:
            return
        ai_content = _ENV.get_template("ai_insights.md.j2").render(
            details=details, suggestions=suggestions
        )
        (out_dir / "ai-insights.md").write_text(ai_content, encoding="utf-8")

    @staticmethod
    def _write_prompt_security(context: ReportContext, out_dir: Path) -> None:
        """Write the prompt security scan page if data is available."""
        data = _get_prompt_security_data(context.results)
        if not data:
            return
        security_content = _ENV.get_template("prompt_security.md.j2").render(**data)
        (out_dir / "prompt-security.md").write_text(security_content, encoding="utf-8")

    @staticmethod
    def _write_file_pages(ctx: ReportContext, cfg: ReportConfig, out_dir: Path) -> None:
        """Write paginated per-file detail pages."""
        hotspots = _hotspot_files(ctx.results)
        complex_files = _high_complexity_files(ctx.results)
        suggestions = _refactor_suggestions(ctx.results)

        sorted_files = sorted(ctx.score.per_file_scores.items())
        total_files = len(sorted_files)
        per_page = cfg.files_per_page
        total_pages = max(1, (total_files + per_page - 1) // per_page)

        template = _ENV.get_template("file_detail.md.j2")

        for page_num in range(1, total_pages + 1):
            start = (page_num - 1) * per_page
            end = start + per_page
            page_items = sorted_files[start:end]
            file_rows = _build_file_detail_rows(page_items, hotspots, complex_files, suggestions)

            nav_parts = []
            if page_num > 1:
                nav_parts.append(f"[← Previous](files-{page_num - 1:03d}.md)")
            if page_num < total_pages:
                nav_parts.append(f"[Next →](files-{page_num + 1:03d}.md)")
            nav = " | ".join(nav_parts) if nav_parts else ""

            content = template.render(
                page_num=page_num,
                total_pages=total_pages,
                file_rows=file_rows,
                nav=nav,
            )
            (out_dir / f"files-{page_num:03d}.md").write_text(content, encoding="utf-8")
