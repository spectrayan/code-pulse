# CodePulse — Product Summary

CodePulse is a Python CLI tool that evaluates codebase maintainability and produces a structured Markdown report with a 0–100 score.

It is orchestrated as a LangGraph agent workflow where each analyzer runs as a tool node with parallel execution support. The Agentic Analyzer supports configuring multiple LLMs to run in parallel for unbiased semantic scoring.

It analyzes repositories across four dimensions:
- Static analysis (cyclomatic complexity, duplication, anti-patterns) via lizard, jscpd, semgrep
- Git history insights (churn, hotspots, bugfix patterns) via GitPython
- AI semantic scoring (readability, architecture clarity, design smells, coding standards compliance) via multi-LLM Agentic Analyzer
- Risk modeling (dependency health, ownership analysis)

Key outputs:
- A weighted maintainability score classified into tiers: excellent (80–100), good (60–79), poor (40–59), critical (0–39)
- A recommendation: maintain, refactor, partial_rewrite, or full_rewrite
- A Markdown report with per-file scores, tags, Mermaid diagrams, trend analysis, and cost-to-fix estimates

Supported languages: Python, Java, JavaScript, TypeScript.

The scoring formula is a configurable weighted ensemble:
`CodePulse_Score = Σ(weight_i × normalized_score_i) / Σ(weight_i)`

The tool uses a pluggable analyzer architecture backed by LangGraph, so new analysis sources can be added as tool nodes without modifying existing code. The Agentic Analyzer supports configurable coding standards — system defaults, predefined industry standards (SOLID, clean code, OWASP), or custom team standards loaded from a configurable directory. Optional observability via LangSmith or Langfuse for tracing and debugging.
