# CodePulse — Tech Stack & Build

## Language & Runtime
- Python 3.10+
- Package manager: [uv](https://docs.astral.sh/uv/)
- Package format: pyproject.toml (PEP 621) with hatchling build backend

## Core Dependencies
- `langgraph` — agent workflow orchestration (state graph, parallel execution, sub-graphs)
- `langchain-core` — base abstractions for LangGraph tool nodes
- `lizard` — multi-language cyclomatic complexity, LOC, function length
- `GitPython` (>=3.1.0) — git history traversal
- `jscpd` — copy-paste duplication detection (Node.js tool, called externally via subprocess)
- `semgrep` — anti-pattern and security smell detection (called externally via subprocess)
- `PyYAML` — YAML configuration file parsing
- `requests` — HTTP client for SonarQube REST API

## LLM / Agentic Dependencies (optional, `uv sync --extra llm`)
- `langchain-openai` — OpenAI LLM provider
- `langchain-anthropic` — Anthropic LLM provider
- `langchain-google-genai` — Google Gemini LLM provider
- `langchain-ollama` — Ollama local LLM provider (no API key needed)

## Observability (optional, `uv sync --extra observability`)
- `langsmith` — hosted tracing/debugging for LangGraph workflows
- `langfuse` — open-source self-hostable alternative

## Dev Dependencies (`uv sync --extra dev`)
- `hypothesis` — property-based testing
- `pytest` — test runner

## Build & Install
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project
uv sync

# Install with LLM support
uv sync --extra llm

# Install everything
uv sync --extra all
```

## Environment Variables
- Copy `.env.example` to `.env` and fill in API keys
- `${VAR}` references in `codepulse-config.yaml` are auto-expanded from `.env` or shell env
- Key variables: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SONAR_TOKEN`

## CLI Entry Point
Defined in pyproject.toml under `[project.scripts]`:
```
code-pulse = "code_pulse.cli:main"
```

Usage:
```bash
uv run code-pulse /path/to/repo
uv run code-pulse /path/to/repo --config codepulse-config.yaml --output report.md --verbose
```

## Testing
```bash
uv run pytest
```
Tests live in `tests/` organized into `unit/`, `property/`, and `integration/` directories.

## Key Conventions
- All source code lives under `src/code_pulse/` organized into `core/`, `analyzers/`, `engine/`, `reporting/`
- Dataclasses are used for all domain models (see `core/models.py`)
- The entire analysis pipeline is a LangGraph state graph defined in `engine/workflow.py`
- Each analyzer implements the `Analyzer` ABC and is registered as a LangGraph tool node
- The Agentic Analyzer (multi-LLM semantic scoring) is a LangGraph sub-graph with parallel LLM nodes
- Deterministic analyzer tool nodes (lizard, jscpd, semgrep, git, SonarQube, dependency) execute in parallel
- External tools (jscpd, semgrep) are invoked as subprocesses; failures are logged and gracefully skipped
- Scores are always normalized to 0–100 before weighting
- Multi-LLM scores are aggregated via configurable strategy (median, average, or conservative min)
- Environment variables in config YAML are expanded via `${VAR}` syntax
