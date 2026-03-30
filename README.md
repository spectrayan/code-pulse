# CodePulse — AI-Powered Maintainability Analyzer

CodePulse evaluates any codebase (Python, Java, JavaScript, TypeScript, or mixed) and generates a structured Markdown report with a 0–100 maintainability score, tier classification, and a recommendation on whether to maintain, refactor, or rewrite.

It combines deterministic static analysis with multi-LLM semantic scoring, orchestrated as a LangGraph agent workflow.

## What It Does

- Computes a **0–100 maintainability score** via weighted ensemble scoring
- Classifies codebases as **excellent**, **good**, **poor**, or **critical**
- Recommends whether to **maintain, refactor, partial_rewrite, or full_rewrite**
- Generates a **Markdown report** with Mermaid diagrams, per-file scores, trend analysis, and cost-to-fix estimates
- Validates code against **configurable coding standards** (system, industry, or custom)

## Analysis Dimensions

| Dimension | Tool | What It Measures |
|-----------|------|-----------------|
| Complexity | lizard | Cyclomatic complexity, LOC, function length |
| Duplication | jscpd | Copy-paste detection |
| Anti-patterns | semgrep | Security smells, code smells |
| Enterprise quality | SonarQube | Quality gate, ratings (optional) |
| Git risk | GitPython | Churn, hotspots, bugfix patterns |
| Semantic | Multi-LLM (Gemini, GPT, Claude, Ollama) | Readability, architecture, design smells |
| Dependencies | pip/npm/maven | Outdated, vulnerable packages |
| Ownership | git blame | Code ownership, team insights |

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

### Install

```bash
git clone https://github.com/your-org/code-pulse.git
cd code-pulse

# Install with uv
uv sync

# Install with LLM support (Gemini, OpenAI, Anthropic)
uv sync --extra llm

# Install everything (LLM + observability + dev tools)
uv sync --extra all
```

### Configure

```bash
# Copy the example env file and add your API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your-key-here
```

### Run

```bash
# Analyze a repo with default config
uv run code-pulse /path/to/repo

# Analyze with custom config
uv run code-pulse /path/to/repo --config codepulse-config.yaml

# Analyze with custom output path
uv run code-pulse /path/to/repo --output my-report.md

# Verbose mode (debug logging)
uv run code-pulse /path/to/repo --verbose
```

### Run Tests

```bash
uv run pytest
```

## Configuration

CodePulse is configured via a YAML file. See `codepulse-config.yaml` for the default config.

### Project Settings

```yaml
project:
  name: "My Project"
  exclude_dirs: ["generated", "target"]       # additional dirs to skip (on top of node_modules, .git, etc.)
  exclude_patterns: [".*\\.test\\.js$", ".*\\.min\\.js$"]  # regex patterns to exclude files
```

### Analyzers

Each analyzer can be enabled/disabled and weighted independently:

```yaml
analyzers:
  lizard:
    enabled: true
    weight: 0.25
  llm:
    enabled: true
    weight: 0.20
    settings:
      aggregation_strategy: "median"
      providers:
        - name: "google_genai"
          model: "gemini-2.0-flash"
          api_key: "${GEMINI_API_KEY}"
        # Local Ollama (no API key needed)
        - name: "ollama"
          model: "llama3.1"
          base_url: "http://localhost:11434"
```

Environment variables in `${VAR}` format are automatically expanded from your `.env` file or shell environment.

## Scoring Model

```
CodePulse_Score = Σ(weight_i × normalized_score_i) / Σ(weight_i)
```

| Score | Tier | Recommendation |
|-------|------|---------------|
| 80–100 | excellent | maintain |
| 60–79 | good | refactor |
| 40–59 | poor | partial_rewrite |
| 0–39 | critical | full_rewrite |

## Supported Languages

| Language | Static Analysis | Git Churn | AI Scoring | Status |
|----------|----------------|-----------|------------|--------|
| Python | ✅ | ✅ | ✅ | Supported |
| Java | ✅ | ✅ | ✅ | Supported |
| JavaScript | ✅ | ✅ | ✅ | Supported |
| TypeScript | ✅ | ✅ | ✅ | Supported |

## Tech Stack

- Python 3.10+ with [uv](https://docs.astral.sh/uv/) for package management
- [LangGraph](https://github.com/langchain-ai/langgraph) for agent workflow orchestration
- [lizard](https://github.com/terryyin/lizard) for multi-language complexity analysis
- [GitPython](https://github.com/gitpython-developers/GitPython) for git history insights
- [jscpd](https://github.com/kucherenko/jscpd) for duplication detection
- [semgrep](https://github.com/returntocorp/semgrep) for anti-pattern detection
- Multi-LLM support via LangChain (Gemini, OpenAI, Anthropic, Ollama)

## License

This project is licensed under a modified MIT License - see the [LICENSE](LICENSE) file for details. Any updates, modifications, or reselling require credit or mention of **Spectrayan**.

## Support

For any questions, issues, or feedback, please contact us at [support@spectrayan.com](mailto:support@spectrayan.com).
