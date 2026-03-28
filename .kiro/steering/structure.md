# CodePulse — Project Structure

```
code-pulse/
├── pyproject.toml              # Package metadata, dependencies, CLI entry point
├── README.md                   # Project overview and usage docs
├── idea.md                     # Original MVP design document (reference only)
├── .github/
│   └── workflows/
│       └── codepulse.yml       # GitHub Action for CI integration
├── src/
│   └── code_pulse/
│       ├── __init__.py
│       ├── cli.py              # CLI argument parsing, builds and invokes LangGraph workflow
│       ├── core/               # Foundational modules
│       │   ├── __init__.py
│       │   ├── models.py       # Dataclass definitions for all domain types
│       │   ├── config.py       # YAML configuration loading and validation
│       │   └── discovery.py    # Multi-language file discovery
│       ├── analyzers/          # Pluggable analyzer plugins
│       │   ├── __init__.py
│       │   ├── base.py         # Analyzer ABC
│       │   ├── registry.py     # AnalyzerRegistry — discovers and manages plugins
│       │   ├── lizard_analyzer.py    # Cyclomatic complexity via lizard
│       │   ├── jscpd_analyzer.py     # Duplication detection via jscpd (subprocess)
│       │   ├── semgrep_analyzer.py   # Anti-pattern detection via semgrep (subprocess)
│       │   ├── sonarqube_adapter.py  # SonarQube REST API integration
│       │   ├── git_analyzer.py       # Git churn and hotspot analysis
│       │   ├── dependency_analyzer.py # Dependency health scoring
│       │   ├── ownership_analyzer.py  # Code ownership via git blame
│       │   ├── agentic_analyzer.py   # Multi-LLM semantic scoring (LangGraph sub-graph)
│       │   └── standards_loader.py   # Coding standards loading and language filtering
│       ├── engine/             # Orchestration and scoring
│       │   ├── __init__.py
│       │   ├── scoring.py      # Weighted ensemble scoring engine
│       │   └── workflow.py     # LangGraph state graph definition and builder
│       ├── reporting/          # Output generation
│       │   ├── __init__.py
│       │   ├── report.py       # Markdown + Mermaid report generation
│       │   ├── trend.py        # Trend store (historical score persistence)
│       │   └── cost.py         # Cost-to-fix estimation
│       └── standards/          # Bundled coding standards documents
│           ├── __init__.py
│           ├── system/         # Default CodePulse standards
│           └── predefined/     # Industry standards (SOLID, clean-code, OWASP, etc.)
└── tests/
    ├── unit/                   # Unit tests (specific examples, edge cases)
    ├── property/               # Property-based tests (Hypothesis)
    └── integration/            # Integration and end-to-end tests
```

## Architecture Notes
- The entire analysis pipeline is a LangGraph state graph defined in `engine/workflow.py`
- `cli.py` is the entry point: it parses args, loads config, builds the graph, and invokes it
- Each analyzer implements the `Analyzer` ABC from `analyzers/base.py` and is a tool node in the graph
- The Agentic Analyzer (`analyzers/agentic_analyzer.py`) is a LangGraph sub-graph that runs multiple LLMs in parallel
- The Agentic Analyzer loads configurable coding standards and passes them as context to LLMs
- Coding standards are filtered by language relevance per file to optimize token usage
- Deterministic tool nodes execute in parallel; scoring and reporting run sequentially after
- New analyzers should be added under `src/code_pulse/analyzers/` and registered with the registry
- External tool analyzers (jscpd, semgrep, SonarQube) handle missing tools gracefully with logged warnings
- Observability (LangSmith/Langfuse) is optional and configured via YAML

## Package Import Paths
- `code_pulse.core.models` — all dataclasses and type aliases
- `code_pulse.core.config` — ConfigLoader, ConfigError
- `code_pulse.core.discovery` — FileDiscovery
- `code_pulse.analyzers.*` — all analyzer implementations
- `code_pulse.engine.scoring` — ScoringEngine
- `code_pulse.engine.workflow` — build_workflow, AnalysisState
- `code_pulse.reporting.report` — ReportGenerator
- `code_pulse.reporting.trend` — TrendStore
- `code_pulse.reporting.cost` — CostEstimator
