# Requirements Document

## Introduction

CodePulse is an AI-powered maintainability analyzer that evaluates codebases written in Python, Java, JavaScript, TypeScript, or mixed-language projects. It combines deterministic static analysis tools with multi-LLM agentic semantic scoring to produce a structured Markdown report containing a 0-100 maintainability score, a tier classification, and a recommendation on whether to maintain, refactor, partially rewrite, or fully rewrite the codebase. The system is orchestrated as a LangGraph agent workflow where each analyzer runs as a tool node with parallel execution support. The Agentic Analyzer supports configuring multiple LLMs to run in parallel for unbiased semantic scoring. The system uses a pluggable analyzer architecture with configurable weights and outputs reports with Mermaid diagrams.

## Glossary

- **CodePulse**: The CLI application that orchestrates all analyzers and produces the final maintainability report
- **Analyzer**: A pluggable component that evaluates one dimension of code quality (e.g., complexity, duplication, semantic readability)
- **Analyzer_Registry**: The component that discovers, loads, and manages all registered Analyzer plugins
- **Static_Analyzer**: An Analyzer that uses deterministic tools (lizard, jscpd, semgrep) to compute measurable code metrics
- **Agentic_Analyzer**: An Analyzer that uses one or more large language models in parallel to perform semantic scoring of code (readability, architecture clarity, design smells). Replaces the former LLM_Analyzer with multi-LLM support and consensus scoring
- **Git_Analyzer**: An Analyzer that uses GitPython to extract churn, hotspot, and bugfix pattern metrics from git history
- **SonarQube_Adapter**: An Analyzer that pulls existing analysis results from a SonarQube server via its REST API
- **Dependency_Analyzer**: An Analyzer that checks project dependencies for outdated, abandoned, or vulnerable packages
- **Scoring_Engine**: The component that normalizes individual analyzer scores to a 0-100 scale and computes the weighted ensemble CodePulse Score
- **CodePulse_Score**: The final weighted score computed as Σ(weight_i × normalized_score_i) / Σ(weight_i), ranging from 0 to 100
- **Tier**: A classification of the CodePulse_Score into one of four levels: excellent (80-100), good (60-79), poor (40-59), critical (0-39)
- **Recommendation**: An action derived from the Tier: maintain, refactor, partial_rewrite, or full_rewrite
- **Report_Generator**: The component that produces the final Markdown report with Mermaid diagrams
- **Configuration_File**: A YAML file that controls which analyzers are enabled, their weights, tool-specific settings, and LLM provider details
- **Configuration_Loader**: The component that reads and validates the Configuration_File
- **Trend_Store**: A persistent store of historical CodePulse_Score results used for trend analysis
- **Cost_Estimator**: The component that produces a rough effort estimate for improving a codebase from its current Tier to a target Tier
- **Ownership_Analyzer**: The component that correlates git blame data with quality scores to produce team-level insights
- **CI_Integration**: A GitHub Action that runs CodePulse on pull requests and fails the build if the CodePulse_Score drops below a configured threshold
- **LangGraph_Workflow**: The LangGraph-based agent workflow that orchestrates the entire CodePulse analysis pipeline, with each analyzer as a tool node and support for parallel execution
- **Agentic_Analyzer**: A LangGraph sub-graph within the workflow that runs multiple LLMs in parallel for semantic scoring and aggregates their results
- **Coding_Standards**: A set of rules, conventions, and best practices that the Agentic_Analyzer uses as context when evaluating code. Can be system defaults, predefined industry standards, custom team standards, or a combination
- **Coding_Standards_Loader**: The component that discovers and loads coding standards documents from configured sources (system, predefined, custom path) and filters them by language relevance

## Requirements

### Requirement 1: CLI Interface

**User Story:** As a developer, I want to run CodePulse from the command line against a repository path, so that I can quickly assess the maintainability of any codebase.

#### Acceptance Criteria

1. WHEN a user invokes `code-pulse <path-to-repo>`, THE CodePulse SHALL analyze the repository at the specified path and print a summary to standard output
2. WHEN a user provides the `--config <path>` flag, THE CodePulse SHALL load analyzer settings from the specified Configuration_File
3. WHEN a user provides the `--output <path>` flag, THE CodePulse SHALL write the Markdown report to the specified file path
4. WHEN no `--config` flag is provided, THE CodePulse SHALL use default configuration values for all analyzers and weights
5. IF the specified repository path does not exist or is not a directory, THEN THE CodePulse SHALL exit with a non-zero exit code and print a descriptive error message to standard error
6. IF the specified Configuration_File path does not exist or contains invalid YAML, THEN THE CodePulse SHALL exit with a non-zero exit code and print a descriptive error message to standard error

### Requirement 2: YAML Configuration

**User Story:** As a developer, I want to configure CodePulse via a YAML file, so that I can enable or disable analyzers, set weights, and provide tool-specific settings without modifying code.

#### Acceptance Criteria

1. THE Configuration_Loader SHALL parse a YAML Configuration_File containing sections for each Analyzer, including enabled/disabled status and confidence weight
2. WHEN the Configuration_File specifies a SonarQube section, THE Configuration_Loader SHALL read the SonarQube server URL and authentication token from that section
3. WHEN the Configuration_File specifies an agentic analyzer section, THE Configuration_Loader SHALL read a list of LLM provider configurations, each containing a provider name, model identifier, API key, and optional weight for multi-LLM aggregation
4. WHEN the Configuration_File specifies a git section, THE Configuration_Loader SHALL read the maximum commit count to analyze from that section
5. IF a required configuration field is missing or has an invalid type, THEN THE Configuration_Loader SHALL report the specific field name and expected type in the error message
6. THE Configuration_Loader SHALL allow each Analyzer weight to be a floating-point number between 0.0 and 1.0 inclusive

### Requirement 3: Pluggable Analyzer Architecture

**User Story:** As a developer extending CodePulse, I want each analysis source to be a self-contained plugin following an adapter pattern, so that I can add new analyzers without modifying existing code.

#### Acceptance Criteria

1. THE Analyzer_Registry SHALL define a common Analyzer interface with methods for initialization, execution, and result normalization
2. THE Analyzer_Registry SHALL discover and load all Analyzer plugins that implement the common Analyzer interface
3. WHEN an Analyzer is disabled in the Configuration_File, THE Analyzer_Registry SHALL skip that Analyzer during execution
4. IF an Analyzer raises an exception during execution, THEN THE Analyzer_Registry SHALL log the error, skip that Analyzer, and continue with the remaining Analyzers
5. WHEN a new Analyzer plugin is registered, THE Analyzer_Registry SHALL make the new Analyzer available without requiring changes to existing Analyzer plugins or the Scoring_Engine

### Requirement 4: Static Analysis via Lizard

**User Story:** As a developer, I want CodePulse to compute cyclomatic complexity, lines of code, and function length metrics using lizard, so that I get accurate deterministic metrics across Python, Java, JavaScript, and TypeScript files.

#### Acceptance Criteria

1. WHEN a repository contains Python, Java, JavaScript, or TypeScript source files, THE Static_Analyzer SHALL use lizard to compute cyclomatic complexity, lines of code, and function length for each source file
2. THE Static_Analyzer SHALL normalize lizard metrics to a 0-100 score where lower complexity and shorter functions yield higher scores
3. IF a source file cannot be parsed by lizard, THEN THE Static_Analyzer SHALL log a warning with the file path and exclude that file from lizard results

### Requirement 5: Duplication Detection via jscpd

**User Story:** As a developer, I want CodePulse to detect copy-paste duplication across the codebase, so that I can identify redundant code that harms maintainability.

#### Acceptance Criteria

1. WHEN a repository is analyzed, THE Static_Analyzer SHALL use jscpd to detect duplicated code blocks across all supported language files
2. THE Static_Analyzer SHALL normalize jscpd duplication percentage to a 0-100 score where lower duplication yields a higher score
3. IF jscpd is not installed or fails to execute, THEN THE Static_Analyzer SHALL log a warning and proceed without duplication metrics

### Requirement 6: Anti-Pattern Detection via Semgrep

**User Story:** As a developer, I want CodePulse to detect common anti-patterns and security smells using semgrep, so that I can identify structural issues that reduce maintainability.

#### Acceptance Criteria

1. WHEN a repository is analyzed, THE Static_Analyzer SHALL use semgrep to scan for anti-patterns and security smells in Python, Java, JavaScript, and TypeScript files
2. THE Static_Analyzer SHALL normalize semgrep finding counts to a 0-100 score where fewer findings yield a higher score
3. IF semgrep is not installed or fails to execute, THEN THE Static_Analyzer SHALL log a warning and proceed without semgrep metrics

### Requirement 7: SonarQube Integration

**User Story:** As a developer working in an enterprise environment, I want CodePulse to pull existing analysis results from my SonarQube server, so that I can incorporate enterprise-grade quality data into the maintainability score.

#### Acceptance Criteria

1. WHEN the SonarQube_Adapter is enabled and configured with a server URL and authentication token, THE SonarQube_Adapter SHALL retrieve project quality metrics via the SonarQube REST API
2. THE SonarQube_Adapter SHALL normalize SonarQube quality gate status and metric values to a 0-100 score
3. IF the SonarQube server is unreachable or returns an authentication error, THEN THE SonarQube_Adapter SHALL log the error and proceed without SonarQube metrics
4. IF the specified project key is not found on the SonarQube server, THEN THE SonarQube_Adapter SHALL log a warning and proceed without SonarQube metrics

### Requirement 8: Git History Analysis

**User Story:** As a developer, I want CodePulse to analyze git history for churn, hotspots, and bugfix patterns, so that I can identify files that are frequently changed and prone to bugs.

#### Acceptance Criteria

1. WHEN a repository has git history, THE Git_Analyzer SHALL compute per-file churn counts, hotspot identification, and bugfix commit counts using GitPython
2. WHEN the Configuration_File specifies a maximum commit count, THE Git_Analyzer SHALL limit history traversal to that number of commits
3. WHEN no maximum commit count is configured, THE Git_Analyzer SHALL use a default limit of 500 commits
4. THE Git_Analyzer SHALL normalize git metrics to a 0-100 score where lower churn and fewer bugfix commits yield a higher score
5. IF the repository path is not a git repository, THEN THE Git_Analyzer SHALL log a warning and proceed without git metrics

### Requirement 9: Agentic Semantic Scoring (Multi-LLM)

**User Story:** As a developer, I want CodePulse to use one or more LLMs in parallel to evaluate code readability, architecture clarity, and design smells, so that I get robust semantic insights that are not biased by any single model.

#### Acceptance Criteria

1. WHEN the Agentic_Analyzer is enabled and configured with one or more LLM providers, THE Agentic_Analyzer SHALL send source code excerpts along with applicable Coding_Standards context to each configured LLM in parallel and receive semantic scores for readability, architecture clarity, design smell detection, and coding standards compliance
2. THE Agentic_Analyzer SHALL normalize each LLM's response scores to a 0-100 scale
3. THE Agentic_Analyzer SHALL aggregate scores from multiple LLMs using a configurable strategy (median, average, or conservative minimum)
4. THE Agentic_Analyzer SHALL include refactor suggestions and rewrite cost estimations returned by the LLMs in the per-file results
5. IF an LLM API returns an error or times out, THEN THE Agentic_Analyzer SHALL log the error and continue with the remaining LLMs for the affected files
6. IF an LLM API rate limit is exceeded, THEN THE Agentic_Analyzer SHALL wait and retry up to a configurable maximum retry count before skipping that LLM for the affected files
7. WHEN only one LLM is configured, THE Agentic_Analyzer SHALL operate as a single-LLM analyzer without aggregation

### Requirement 10: Weighted Ensemble Scoring

**User Story:** As a developer, I want CodePulse to combine scores from all analyzers using configurable weights, so that I get a single meaningful maintainability score that reflects my priorities.

#### Acceptance Criteria

1. THE Scoring_Engine SHALL compute the CodePulse_Score using the formula: CodePulse_Score = Σ(weight_i × normalized_score_i) / Σ(weight_i) where each weight_i is the configured confidence weight for Analyzer i
2. THE Scoring_Engine SHALL normalize all individual Analyzer scores to a 0-100 scale before applying weights
3. WHEN multiple Analyzers score the same quality dimension, THE Scoring_Engine SHALL use the more conservative (lower) score for that dimension
4. THE Scoring_Engine SHALL classify the CodePulse_Score into a Tier: excellent for scores 80-100, good for 60-79, poor for 40-59, critical for 0-39
5. THE Scoring_Engine SHALL derive a Recommendation from the Tier: maintain for excellent, refactor for good, partial_rewrite for poor, full_rewrite for critical
6. IF no Analyzers produce results, THEN THE Scoring_Engine SHALL report a CodePulse_Score of 0 with a critical Tier and full_rewrite Recommendation


### Requirement 11: Markdown Report Generation

**User Story:** As a developer, I want CodePulse to generate a structured Markdown report with Mermaid diagrams, so that I can read and share a clear visual summary of the codebase's maintainability.

#### Acceptance Criteria

1. THE Report_Generator SHALL produce a Markdown file containing the overall CodePulse_Score, Tier, and Recommendation
2. THE Report_Generator SHALL include a per-file table with individual scores, tags (e.g., hotspot, high_complexity), and refactor suggestions
3. THE Report_Generator SHALL include Mermaid diagram blocks for score distribution and dimension breakdown visualizations
4. WHEN the `--output` flag specifies a file path, THE Report_Generator SHALL write the Markdown report to that path
5. WHEN no `--output` flag is provided, THE Report_Generator SHALL write the Markdown report to `codepulse-report.md` in the current working directory

### Requirement 12: Dependency Health Scoring

**User Story:** As a developer, I want CodePulse to check project dependencies for outdated, abandoned, or vulnerable packages, so that I can factor dependency risk into the maintainability assessment.

#### Acceptance Criteria

1. WHEN a repository contains dependency manifest files (requirements.txt, package.json, pom.xml, build.gradle), THE Dependency_Analyzer SHALL identify outdated, abandoned, and vulnerable dependencies
2. THE Dependency_Analyzer SHALL normalize dependency health findings to a 0-100 score where fewer issues yield a higher score
3. IF no dependency manifest files are found, THEN THE Dependency_Analyzer SHALL log an informational message and produce no dependency score

### Requirement 13: Trend Analysis

**User Story:** As a developer, I want to run CodePulse periodically and see whether maintainability is improving or degrading over time, so that I can track the impact of my maintenance efforts.

#### Acceptance Criteria

1. WHEN a CodePulse analysis completes, THE Trend_Store SHALL persist the CodePulse_Score, Tier, and timestamp to a local storage file
2. WHEN previous analysis results exist in the Trend_Store, THE Report_Generator SHALL include a trend section showing score changes over time
3. THE Report_Generator SHALL indicate whether the CodePulse_Score is improving, stable, or degrading compared to the previous analysis run

### Requirement 14: Cost-to-Fix Estimation

**User Story:** As a technical lead, I want CodePulse to estimate the rough effort required to improve the codebase from its current tier to a target tier, so that I can plan refactoring work.

#### Acceptance Criteria

1. THE Cost_Estimator SHALL produce a rough effort estimate in person-days for improving the codebase from its current Tier to the next higher Tier
2. THE Cost_Estimator SHALL base the estimate on the number of files, their individual scores, and the severity of identified issues
3. THE Report_Generator SHALL include the cost-to-fix estimate in the Markdown report

### Requirement 15: Team-Level Insights

**User Story:** As a technical lead, I want CodePulse to correlate code ownership with quality scores, so that I can identify which team members own the most problematic areas of the codebase.

#### Acceptance Criteria

1. WHEN a repository has git history, THE Ownership_Analyzer SHALL use git blame data to determine the primary author of each file
2. THE Ownership_Analyzer SHALL aggregate per-file scores by author to produce per-author average maintainability scores
3. THE Report_Generator SHALL include a team insights section listing authors and their associated average scores and hotspot counts

### Requirement 16: CI Integration via GitHub Action

**User Story:** As a team lead, I want a GitHub Action that runs CodePulse on pull requests and fails the build if maintainability drops below a threshold, so that I can enforce quality standards automatically.

#### Acceptance Criteria

1. THE CI_Integration SHALL provide a GitHub Action workflow definition that runs CodePulse on the pull request branch
2. WHEN the CodePulse_Score is below the configured threshold, THE CI_Integration SHALL fail the GitHub Action step with a non-zero exit code
3. WHEN the CodePulse_Score is at or above the configured threshold, THE CI_Integration SHALL pass the GitHub Action step with a zero exit code
4. THE CI_Integration SHALL post the CodePulse_Score summary as a comment on the pull request

### Requirement 17: Multi-Language File Discovery

**User Story:** As a developer, I want CodePulse to automatically discover and analyze Python, Java, JavaScript, and TypeScript files in a repository, so that mixed-language projects are fully covered.

#### Acceptance Criteria

1. THE CodePulse SHALL discover source files with extensions .py, .java, .js, and .ts within the target repository, excluding common non-source directories (node_modules, .git, __pycache__, build, dist)
2. WHEN a repository contains files in multiple supported languages, THE CodePulse SHALL analyze each file using the appropriate language-specific analysis pipeline
3. THE CodePulse SHALL report per-language score breakdowns in the Markdown report

### Requirement 18: LangGraph Agent Workflow Orchestration

**User Story:** As a developer, I want CodePulse to use a LangGraph agent workflow to orchestrate the entire analysis pipeline, so that analyzers run as tool nodes with parallel execution support and the system is observable and extensible.

#### Acceptance Criteria

1. THE LangGraph_Workflow SHALL define the analysis pipeline as a state graph where each analyzer is a tool node
2. THE LangGraph_Workflow SHALL execute deterministic analyzer tool nodes (lizard, jscpd, semgrep, git, SonarQube, dependency) in parallel
3. THE LangGraph_Workflow SHALL execute the Agentic_Analyzer as a sub-graph that runs multiple LLMs in parallel
4. WHEN an analyzer tool node fails, THE LangGraph_Workflow SHALL log the error, skip that node, and continue with the remaining nodes
5. THE LangGraph_Workflow SHALL support optional observability integration via LangSmith or Langfuse for tracing and debugging
6. THE LangGraph_Workflow SHALL pass the aggregated results from all tool nodes to the scoring engine and report generator nodes sequentially

### Requirement 19: Configurable Coding Standards Validation

**User Story:** As a developer, I want the Agentic Analyzer to validate code against configurable coding standards (system defaults, industry best practices, or my team's custom standards), so that the semantic scoring reflects the specific conventions and quality expectations of my project.

#### Acceptance Criteria

1. WHEN the Configuration_File specifies a coding_standards section with mode "system", THE Agentic_Analyzer SHALL include CodePulse built-in coding standards as context when scoring code
2. WHEN the Configuration_File specifies a coding_standards section with mode "predefined", THE Agentic_Analyzer SHALL load the specified industry standard rulesets (e.g., SOLID principles, clean code, OWASP secure coding) as context when scoring code
3. WHEN the Configuration_File specifies a coding_standards section with mode "custom" and a custom_path, THE Agentic_Analyzer SHALL load all Markdown and text files from the specified directory as coding standards context
4. WHEN the Configuration_File specifies a coding_standards section with mode "combined", THE Agentic_Analyzer SHALL load and merge system defaults, selected predefined standards, and custom standards from the configured path
5. THE Agentic_Analyzer SHALL filter loaded coding standards by language relevance, including only standards applicable to the language of the file being analyzed
6. THE Agentic_Analyzer SHALL report which specific coding standards were violated per file, including the standard name and a description of the violation, in the per-file results
7. IF the configured custom_path does not exist or contains no readable files, THEN THE Agentic_Analyzer SHALL log a warning and proceed with only system and predefined standards
8. WHEN no coding_standards section is configured, THE Agentic_Analyzer SHALL default to mode "system" using built-in standards only
