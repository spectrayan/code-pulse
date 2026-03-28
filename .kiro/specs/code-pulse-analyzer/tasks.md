# Implementation Plan: CodePulse Analyzer

## Overview

Incremental implementation of the CodePulse CLI tool — a LangGraph-orchestrated, multi-analyzer maintainability scorer for Python/Java/JavaScript/TypeScript codebases. Each task builds on the previous, starting with project scaffolding and data models, then layering in analyzers, the agentic sub-graph, scoring, reporting, and CI integration. Property-based tests (Hypothesis) and unit tests are woven in close to each implementation step.

## Tasks

- [x] 1. Project scaffolding and data models
  - [x] 1.1 Create `pyproject.toml` with all dependencies and CLI entry point
    - Define project metadata, `requires-python = ">=3.10"`
    - Add dependencies: `langgraph`, `langchain-core`, `lizard`, `GitPython`, `PyYAML`, `requests`, `hypothesis`
    - Add optional dependencies: `langchain-openai`, `langchain-anthropic`, `langsmith`, `langfuse`
    - Define CLI entry point: `code-pulse = "code_pulse.cli:main"`
    - Create `src/code_pulse/__init__.py`
    - _Requirements: 1.1_

  - [x] 1.2 Create all data models in `src/code_pulse/models.py`
    - Implement dataclasses: `AnalyzerConfig`, `Config`, `AnalyzerResult`, `CodePulseScore`, `TrendEntry`, `TrendData`, `CostEstimate`, `AuthorStats`, `OwnershipData`, `CodingStandard`, `StandardViolation`, `ReportContext`
    - Define `Tier` and `Recommendation` Literal types
    - _Requirements: 2.1, 10.1, 13.1, 14.1, 15.2, 19.6_

  - [x] 1.3 Create `src/code_pulse/discovery.py` — multi-language file discovery
    - Implement `FileDiscovery.discover(repo_path)` returning `Dict[str, List[Path]]`
    - Support extensions: `.py`, `.java`, `.js`, `.ts`
    - Exclude directories: `node_modules`, `.git`, `__pycache__`, `build`, `dist`
    - _Requirements: 17.1, 17.2_

  - [ ]* 1.4 Write property tests for file discovery (`tests/property/test_discovery_properties.py`)
    - **Property 18: File Discovery Correctness** — only supported extensions returned, excluded dirs skipped
    - **Validates: Requirements 17.1**
    - **Property 19: Language Routing** — files routed to correct language group by extension
    - **Validates: Requirements 17.2**

- [x] 2. Configuration loader
  - [x] 2.1 Implement `src/code_pulse/config.py` — `ConfigLoader` with `load()` and `default()`
    - Parse YAML using PyYAML
    - Validate analyzer weights are in [0.0, 1.0]
    - Validate required fields and types; raise `ConfigError` with field name and expected type
    - Return sensible defaults when no config file is provided
    - Support all config sections: analyzers, output_path, trend_store_path, ci_threshold, coding_standards, LLM providers
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 1.4_

  - [ ]* 2.2 Write property tests for configuration (`tests/property/test_config_properties.py`)
    - **Property 1: Configuration YAML Round-Trip** — serialize Config to YAML, parse back, get equivalent Config
    - **Validates: Requirements 2.1**
    - **Property 2: Configuration Weight Validation** — accept [0.0, 1.0], reject outside range
    - **Validates: Requirements 2.6**
    - **Property 3: Configuration Error Reporting** — error message contains field name and expected type
    - **Validates: Requirements 2.5**

  - [ ]* 2.3 Write unit tests for configuration (`tests/unit/test_config_loader.py`)
    - Test parsing a complete YAML config string
    - Test default config values
    - Test missing required fields
    - Test invalid weight values (negative, >1.0)
    - _Requirements: 2.1, 2.5, 2.6_

- [x] 3. Analyzer base interface and registry
  - [x] 3.1 Create `src/code_pulse/analyzers/base.py` — `Analyzer` ABC and `AnalyzerResult` dataclass
    - Define abstract methods: `name()`, `dimension()`, `analyze()`
    - Create `src/code_pulse/analyzers/__init__.py`
    - _Requirements: 3.1_

  - [x] 3.2 Create `src/code_pulse/analyzers/registry.py` — `AnalyzerRegistry`
    - Implement `register()`, `get_enabled()`, `run_all()` methods
    - Skip disabled analyzers based on config
    - Catch exceptions from failing analyzers, log, and continue
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 3.3 Write property tests for registry (`tests/property/test_registry_properties.py`)
    - **Property 5: Analyzer Registry Completeness** — all registered analyzers returned when enabled
    - **Validates: Requirements 3.2**
    - **Property 6: Disabled Analyzers Are Skipped** — only enabled analyzers execute
    - **Validates: Requirements 3.3**
    - **Property 7: Failing Analyzers Are Skipped Gracefully** — non-failing analyzers still return results
    - **Validates: Requirements 3.4**

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Deterministic analyzers
  - [x] 5.1 Implement `src/code_pulse/analyzers/lizard_analyzer.py` — `LizardAnalyzer`
    - Use `lizard.analyze_files()` to compute cyclomatic complexity, LOC, function length
    - Normalize to 0-100: `max(0, 100 - (avg_cc - 5) * (100/15))` clamped
    - Log warning and exclude unparseable files
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 5.2 Implement `src/code_pulse/analyzers/jscpd_analyzer.py` — `JscpdAnalyzer`
    - Invoke jscpd via `subprocess.run()` with timeout and error handling
    - Parse JSON output for duplication percentage
    - Normalize to 0-100: `max(0, 100 - duplication_pct * 2)` clamped
    - Handle missing jscpd gracefully (log warning, skip)
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 5.3 Implement `src/code_pulse/analyzers/semgrep_analyzer.py` — `SemgrepAnalyzer`
    - Invoke semgrep via `subprocess.run()` with timeout and error handling
    - Parse JSON output for finding counts
    - Normalize to 0-100: `max(0, 100 - findings_per_kloc * 10)` clamped
    - Handle missing semgrep gracefully (log warning, skip)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 5.4 Implement `src/code_pulse/analyzers/sonarqube_adapter.py` — `SonarQubeAdapter`
    - Use `requests.get()` to call SonarQube REST API
    - Read server URL, token, project key from config
    - Normalize quality gate: A=100, B=80, C=60, D=40, E=20
    - Handle unreachable server, auth errors, missing project gracefully
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 5.5 Implement `src/code_pulse/analyzers/git_analyzer.py` — `GitAnalyzer`
    - Use GitPython to compute per-file churn, hotspots, bugfix commit counts
    - Respect `max_commits` config (default 500)
    - Normalize to 0-100: `max(0, 90 - churn * 2)` clamped
    - Handle non-git repos gracefully (log warning, skip)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 5.6 Implement `src/code_pulse/analyzers/dependency_analyzer.py` — `DependencyAnalyzer`
    - Detect dependency manifests: `requirements.txt`, `package.json`, `pom.xml`, `build.gradle`
    - Identify outdated, abandoned, and vulnerable dependencies
    - Normalize to 0-100: `max(0, 100 - issue_count * 5)` clamped
    - Log info and produce no score if no manifests found
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 5.7 Implement `src/code_pulse/analyzers/ownership_analyzer.py` — `OwnershipAnalyzer`
    - Use GitPython `blame()` to determine primary author per file
    - Aggregate per-file scores by author to produce per-author averages
    - _Requirements: 15.1, 15.2_

  - [ ]* 5.8 Write property tests for score normalization (`tests/property/test_scoring_properties.py` — Property 8)
    - **Property 8: Score Normalization Monotonicity and Range** — better raw values yield higher normalized scores, all in [0, 100]
    - **Validates: Requirements 4.2, 5.2, 6.2, 7.2, 8.4, 9.2, 12.2**

  - [ ]* 5.9 Write property test for git commit limit (`tests/property/test_git_properties.py`)
    - **Property 20: Git Analyzer Commit Limit** — traverses at most `max_commits` commits
    - **Validates: Requirements 8.2**

  - [ ]* 5.10 Write property test for ownership aggregation (`tests/property/test_ownership_properties.py`)
    - **Property 16: Ownership Score Aggregation** — per-author average equals arithmetic mean of owned file scores
    - **Validates: Requirements 15.2**

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Coding standards loader and Agentic Analyzer
  - [x] 7.1 Implement `src/code_pulse/standards_loader.py` — `CodingStandardsLoader`
    - Implement `load()` with modes: system, predefined, custom, combined
    - Implement `filter_by_language()` — return standards matching language or with empty languages list
    - Load system standards from bundled `src/code_pulse/standards/system/`
    - Load predefined standards from bundled `src/code_pulse/standards/predefined/`
    - Load custom standards from user-specified directory (`.md` and `.txt` files)
    - Log warning if custom_path missing or empty; fall back to system/predefined
    - Default to mode "system" when no coding_standards section configured
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.7, 19.8_

  - [x] 7.2 Create placeholder coding standards files
    - Create `src/code_pulse/standards/system/` with a default system standards Markdown file
    - Create `src/code_pulse/standards/predefined/` with placeholder files for SOLID, clean-code, OWASP
    - _Requirements: 19.1, 19.2_

  - [x] 7.3 Implement `src/code_pulse/agentic_analyzer.py` — `AgenticAnalyzer` as LangGraph sub-graph
    - Implement `_build_subgraph()` creating parallel LLM nodes
    - Implement `_create_llm_node()` for each provider — sends code + coding standards context, receives scores
    - Implement `_aggregate_scores()` with strategies: median, average, conservative (min)
    - Handle LLM errors, timeouts, rate limits with retry logic
    - Single-LLM mode: no aggregation
    - Report coding standards violations per file (`StandardViolation`)
    - Include refactor suggestions and rewrite cost estimations from LLM responses
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 19.1, 19.5, 19.6_

  - [ ]* 7.4 Write property tests for coding standards (`tests/property/test_standards_properties.py`)
    - **Property 23: Coding Standards Language Filtering** — only matching-language or all-language standards returned
    - **Validates: Requirements 19.5**
    - **Property 24: Coding Standards Loading by Mode** — correct sources loaded per mode
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4**

  - [ ]* 7.5 Write property test for multi-LLM aggregation (`tests/property/test_agentic_properties.py`)
    - **Property 21: Agentic Analyzer Multi-LLM Aggregation** — median/average/min strategies produce correct results; single-LLM returns that score
    - **Validates: Requirements 9.1, 9.3, 9.7**

- [x] 8. Scoring engine
  - [x] 8.1 Implement `src/code_pulse/scoring.py` — `ScoringEngine`
    - Implement `compute()` using weighted formula: `Σ(weight_i × score_i) / Σ(weight_i)`
    - Group results by dimension; use `min()` for overlapping dimensions (conservative scoring)
    - Validate all scores in [0, 100] range
    - Classify into tier and derive recommendation
    - Return score=0, tier="critical", recommendation="full_rewrite" when no results
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 8.2 Write property tests for scoring (`tests/property/test_scoring_properties.py` — Properties 9, 10, 11)
    - **Property 9: Weighted Scoring Formula Correctness** — final_score matches formula within float tolerance
    - **Validates: Requirements 10.1**
    - **Property 10: Conservative Dimension Scoring** — min score used for duplicate dimensions
    - **Validates: Requirements 10.3**
    - **Property 11: Tier and Recommendation Classification** — correct tier/recommendation for any score in [0, 100]
    - **Validates: Requirements 10.4, 10.5**

  - [ ]* 8.3 Write unit tests for scoring engine (`tests/unit/test_scoring_engine.py`)
    - Test empty results → score=0, critical, full_rewrite
    - Test boundary scores: 0, 39, 40, 59, 60, 79, 80, 100
    - Test single analyzer result
    - Test overlapping dimensions
    - _Requirements: 10.1, 10.3, 10.4, 10.5, 10.6_

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Report generator, trend store, and cost estimator
  - [x] 10.1 Implement `src/code_pulse/trend.py` — `TrendStore`
    - Persist `TrendEntry` as JSON lines in `.codepulse-trend.jsonl`
    - Implement `save()` and `load()` methods
    - Compute `direction`: improving if latest > previous, degrading if lower, stable if equal (within tolerance)
    - _Requirements: 13.1, 13.3_

  - [x] 10.2 Implement `src/code_pulse/cost.py` — `CostEstimator`
    - Estimate person-days based on file count, individual scores, issue severity
    - Target next higher tier (e.g., poor → good)
    - Ensure non-negative output
    - _Requirements: 14.1, 14.2_

  - [x] 10.3 Implement `src/code_pulse/report.py` — `ReportGenerator`
    - Generate Markdown with sections: Summary (score, tier, recommendation), Per-File Table (scores, tags, refactor suggestions), Dimension Breakdown (Mermaid bar chart), Score Distribution (Mermaid pie chart), Trend Analysis, Cost-to-Fix, Team Insights, Per-Language Breakdowns
    - Default output path: `codepulse-report.md`
    - Include Mermaid diagram blocks fenced with ` ```mermaid `
    - Include coding standards violations in per-file results
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 13.2, 14.3, 15.3, 17.3, 19.6_

  - [ ]* 10.4 Write property tests for trend store (`tests/property/test_trend_properties.py`)
    - **Property 13: Trend Store Round-Trip** — save entry, load, find equivalent entry
    - **Validates: Requirements 13.1**
    - **Property 14: Trend Direction Correctness** — improving/degrading/stable computed correctly
    - **Validates: Requirements 13.3**

  - [ ]* 10.5 Write property test for cost estimator (`tests/property/test_cost_properties.py`)
    - **Property 15: Cost Estimator Non-Negative Output** — estimated_person_days >= 0
    - **Validates: Requirements 14.1**

  - [ ]* 10.6 Write property test for report completeness (`tests/property/test_report_properties.py`)
    - **Property 12: Report Content Completeness** — generated Markdown contains all expected sections based on provided context
    - **Validates: Requirements 11.1, 11.2, 11.3, 13.2, 14.3, 15.3, 17.3**

- [x] 11. LangGraph workflow builder
  - [x] 11.1 Implement `src/code_pulse/workflow.py` — LangGraph state graph
    - Define `AnalysisState` TypedDict
    - Build state graph with `file_discovery` node running first
    - Add parallel branches for all enabled deterministic analyzer tool nodes
    - Add parallel branch for Agentic Analyzer sub-graph
    - Add sequential `scoring_engine`, `trend_store`, `cost_estimator`, `report_generator` nodes after all analyzers complete
    - Wrap each analyzer node in error handling (catch, log, skip, continue)
    - Support optional observability integration (LangSmith/Langfuse) via config
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6_

  - [ ]* 11.2 Write property test for workflow parallel execution (`tests/property/test_workflow_properties.py`)
    - **Property 22: LangGraph Parallel Execution Completeness** — results from all non-failing enabled analyzers regardless of order
    - **Validates: Requirements 18.2, 18.4**

- [x] 12. CLI entry point
  - [x] 12.1 Implement `src/code_pulse/cli.py` — CLI with argparse
    - Parse arguments: `path` (positional), `--config`, `--output`, `--verbose`
    - Validate repo path exists and is a directory; exit non-zero with stderr message if not
    - Load config via `ConfigLoader` (or use defaults); exit non-zero with stderr message on invalid config
    - Build and invoke LangGraph workflow
    - Write report to output path (default: `codepulse-report.md`)
    - Print summary to stdout: score, tier, recommendation
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 12.2 Write property test for CLI error handling (`tests/integration/test_cli_integration.py`)
    - **Property 4: CLI Invalid Input Error Handling** — non-existent paths and invalid configs produce non-zero exit and stderr message
    - **Validates: Requirements 1.5, 1.6**

  - [ ]* 12.3 Write unit tests for CLI (`tests/unit/test_cli.py`)
    - Test valid invocation with mock workflow
    - Test missing repo path error
    - Test invalid config path error
    - _Requirements: 1.1, 1.5, 1.6_

- [x] 13. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. CI integration
  - [x] 14.1 Create GitHub Action workflow definition (`.github/workflows/codepulse.yml`)
    - Run CodePulse on PR branch
    - Fail step (non-zero exit) if score below configured threshold
    - Pass step (zero exit) if score at or above threshold
    - Post score summary as PR comment
    - _Requirements: 16.1, 16.2, 16.3, 16.4_

  - [ ]* 14.2 Write property test for CI threshold (`tests/property/test_ci_properties.py`)
    - **Property 17: CI Threshold Exit Code** — exit 0 iff score >= threshold, non-zero otherwise
    - **Validates: Requirements 16.2, 16.3**

- [x] 15. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (24 properties total)
- Unit tests validate specific examples and edge cases
- The implementation language is Python 3.10+ as specified in the design
