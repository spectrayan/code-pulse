from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Tier = Literal["excellent", "good", "poor", "critical"]
Recommendation = Literal["maintain", "refactor", "partial_rewrite", "full_rewrite"]


# Configuration Models
@dataclass
class CodingStandardsConfig:
    mode: str = "system"  # "system" | "predefined" | "custom" | "combined"
    custom_paths: List[str] = field(default_factory=list)  # repo, org, or user standards dirs
    predefined: List[str] = field(default_factory=list)  # e.g. ["solid-principles", "clean-code"]
    system: bool = True  # include built-in CodePulse standards
    predefined_overrides: Dict[str, str] = field(default_factory=dict)  # map of name -> path or content


@dataclass
class ProjectConfig:
    repo_path: Optional[str] = None  # default repo to analyze (overridden by CLI arg)
    name: Optional[str] = None  # project display name for reports
    languages: List[str] = field(default_factory=list)  # restrict to specific languages
    exclude_dirs: List[str] = field(default_factory=list)  # additional dirs to exclude from analysis
    exclude_patterns: List[str] = field(default_factory=list)  # regex patterns to exclude files


@dataclass
class ReportConfig:
    level: str = "detailed"  # "summary" | "detailed"
    output_dir: str = "codepulse-report"  # directory for report files
    files_per_page: int = 100  # max files per detail page in detailed mode


@dataclass
class AnalyzerConfig:
    enabled: bool = True
    weight: float = 1.0
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    coding_standards: CodingStandardsConfig = field(default_factory=CodingStandardsConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    analyzers: Dict[str, AnalyzerConfig] = field(default_factory=dict)
    output_path: Optional[str] = None
    trend_store_path: Optional[str] = ".codepulse-trend.jsonl"
    ci_threshold: Optional[float] = None


# Analyzer Result Models
@dataclass
class AnalyzerResult:
    analyzer_name: str
    dimension: str
    normalized_score: float  # 0-100
    per_file_scores: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    violations: List[Any] = field(default_factory=list)  # StandardViolation list


# Scoring Models
@dataclass
class CodePulseScore:
    final_score: float
    tier: Tier
    recommendation: Recommendation
    per_file_scores: Dict[str, float] = field(default_factory=dict)
    dimension_scores: Dict[str, float] = field(default_factory=dict)


# Trend Models
@dataclass
class TrendEntry:
    timestamp: str  # ISO 8601
    score: float
    tier: Tier


@dataclass
class TrendData:
    entries: List[TrendEntry] = field(default_factory=list)
    direction: Literal["improving", "stable", "degrading"] = "stable"


# Cost Estimation Models
@dataclass
class CostEstimate:
    current_tier: Tier
    target_tier: Tier
    estimated_person_days: float
    breakdown: Dict[str, float] = field(default_factory=dict)


# Ownership Models
@dataclass
class AuthorStats:
    author: str
    file_count: int
    average_score: float
    hotspot_count: int


@dataclass
class OwnershipData:
    authors: List[AuthorStats] = field(default_factory=list)
    file_to_author: Dict[str, str] = field(default_factory=dict)


# Coding Standards Models
@dataclass
class CodingStandard:
    name: str
    content: str
    languages: List[str] = field(default_factory=list)  # empty = all languages
    source: str = "system"  # "system" | "predefined" | "custom"


@dataclass
class StandardViolation:
    standard_name: str
    description: str
    file_path: str
    line_range: Optional[str] = None


# Report Context
@dataclass
class ReportContext:
    score: CodePulseScore
    results: List[AnalyzerResult]
    trend: Optional[TrendData] = None
    cost: Optional[CostEstimate] = None
    ownership: Optional[OwnershipData] = None
    per_language_scores: Dict[str, float] = field(default_factory=dict)
