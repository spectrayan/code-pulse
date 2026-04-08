"""Prompt Security Scanner — detects dangerous patterns in prompts, instructions, and code.

Scans source files for embedded LLM prompts, system instructions, shell commands,
and other instruction-like strings, then identifies security vulnerabilities,
destructive commands, prompt injection vectors, credential leaks, and more.

Operates entirely offline using regex pattern matching — no LLM calls required.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.models import AnalyzerResult, PromptThreat

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity weights for scoring
# ---------------------------------------------------------------------------
_SEVERITY_WEIGHTS = {
    "critical": 25,
    "high": 15,
    "medium": 8,
    "low": 3,
}

# ---------------------------------------------------------------------------
# Default file extensions to scan (beyond standard source code)
# ---------------------------------------------------------------------------
_DEFAULT_EXTRA_EXTENSIONS: Set[str] = {
    ".yaml", ".yml", ".json", ".toml", ".env",
    ".txt", ".md", ".prompt", ".cfg", ".ini",
    ".dockerfile",
}

# Standard source extensions (always scanned)
_SOURCE_EXTENSIONS: Set[str] = {".py", ".java", ".js", ".ts"}

# Directories always excluded
_EXCLUDED_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", "build", "dist",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode",
}

# Max file size in bytes to scan (skip huge files)
_MAX_FILE_SIZE = 512 * 1024  # 512 KB


# ===========================================================================
# Detection Rules
# ===========================================================================
# Each rule is: (rule_id, category, severity, description, regex_pattern)

Rule = Tuple[str, str, str, str, "re.Pattern[str]"]


def _compile_rules() -> List[Rule]:
    """Compile all detection rules. Called once at module load time."""

    rules: List[Tuple[str, str, str, str, str, int]] = []

    # -----------------------------------------------------------------------
    # 1. PROMPT INJECTION  (PS-INJ-*)
    # -----------------------------------------------------------------------
    _inj = [
        ("PS-INJ-001", "prompt_injection", "critical",
         "Prompt override: 'ignore previous instructions'",
         r"ignore\s+(all\s+)?(previous|prior|above|earlier|preceding)\s+(instructions|rules|guidelines|directives|prompts|constraints)",
         re.IGNORECASE),
        ("PS-INJ-002", "prompt_injection", "critical",
         "Prompt override: 'disregard' directive",
         r"disregard\s+(?:all\s+)?(?:(?:your|my|the)\s+)?(?:previous|prior|above|earlier)?\s*(?:instructions|rules|guidelines|directives|prompts|training|programming)",
         re.IGNORECASE),
        ("PS-INJ-003", "prompt_injection", "high",
         "Role hijacking: 'you are now' / 'act as'",
         r"(?:you\s+are\s+now|act\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?|pretend\s+(?:to\s+be|you\s+are)|from\s+now\s+on\s+you\s+are)\s+\w",
         re.IGNORECASE),
        ("PS-INJ-004", "prompt_injection", "high",
         "Jailbreak attempt: 'DAN', 'developer mode', 'unrestricted'",
         r"(?:DAN\s+mode|developer\s+mode\s+(?:enabled|on|active)|jailbreak|unrestricted\s+mode|bypass\s+(?:all\s+)?(?:safety|content|filter|restriction))",
         re.IGNORECASE),
        ("PS-INJ-005", "prompt_injection", "medium",
         "System prompt extraction: 'reveal your system prompt'",
         r"(?:reveal|show|display|print|output|repeat|dump)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions|rules|guidelines|initial\s+instructions)",
         re.IGNORECASE),
        ("PS-INJ-006", "prompt_injection", "medium",
         "Prompt delimiter manipulation",
         r"(?:\[SYSTEM\]|\[INST\]|\<\|system\|\>|\<\|user\|\>|\<\|assistant\|\>|<<SYS>>|<</SYS>>|\[\/INST\])",
         0),
        ("PS-INJ-007", "prompt_injection", "high",
         "Instruction override via markdown/special tokens",
         r"(?:###\s*(?:NEW\s+)?INSTRUCTIONS?|---\s*(?:OVERRIDE|NEW\s+SYSTEM)|BEGIN\s+(?:NEW\s+)?(?:OVERRIDE|INJECTION|PAYLOAD))",
         re.IGNORECASE),
    ]

    # -----------------------------------------------------------------------
    # 2. DESTRUCTIVE COMMANDS  (PS-CMD-*)
    # -----------------------------------------------------------------------
    _cmd = [
        ("PS-CMD-001", "destructive_command", "critical",
         "File system wipe: 'rm -rf /'",
         r"rm\s+-[a-z]*r[a-z]*f[a-z]*\s+/(?:\s|$|;|\|)|rm\s+-[a-z]*f[a-z]*r[a-z]*\s+/(?:\s|$|;|\|)",
         0),
        ("PS-CMD-002", "destructive_command", "critical",
         "File system wipe: Windows /S /Q deletion",
         r"(?:del|rmdir|rd)\s+/[sS]\s+/[qQ]\s+[a-zA-Z]:\\",
         0),
        ("PS-CMD-003", "destructive_command", "critical",
         "Disk format command",
         r"(?:format|FORMAT)\s+[a-zA-Z]:\s*/[a-zA-Z]",
         0),
        ("PS-CMD-004", "destructive_command", "critical",
         "SQL data destruction: DROP/TRUNCATE",
         r"(?:DROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW)\s|TRUNCATE\s+TABLE\s)",
         re.IGNORECASE),
        ("PS-CMD-005", "destructive_command", "high",
         "SQL mass deletion: DELETE without WHERE",
         r"DELETE\s+FROM\s+\w+\s*;",
         re.IGNORECASE),
        ("PS-CMD-006", "destructive_command", "critical",
         "Fork bomb pattern",
         r":\(\)\{[:\s]*:\|:&\s*\}\s*;?\s*:",
         0),
        ("PS-CMD-007", "destructive_command", "high",
         "Recursive permission/ownership change on root",
         r"(?:chmod|chown)\s+-[a-zA-Z]*R[a-zA-Z]*\s+\S+\s+/(?:\s|$)",
         0),
        ("PS-CMD-008", "destructive_command", "high",
         "Registry destruction (Windows)",
         r"reg\s+delete\s+HK(?:LM|CU|CR|U|CC)\b",
         re.IGNORECASE),
        ("PS-CMD-009", "destructive_command", "high",
         "Disk overwrite: dd to block device",
         r"dd\s+.*\bof\s*=\s*/dev/(?:sda|hda|nvme|disk)",
         0),
        ("PS-CMD-010", "destructive_command", "medium",
         "Git history destruction: force push/reset",
         r"git\s+(?:push\s+--force(?:-with-lease)?|reset\s+--hard\s+(?:HEAD~|origin/))",
         0),
    ]

    # -----------------------------------------------------------------------
    # 3. DATA EXFILTRATION  (PS-EXF-*)
    # -----------------------------------------------------------------------
    _exf = [
        ("PS-EXF-001", "data_exfiltration", "critical",
         "Remote code execution: curl piped to shell",
         r"curl\s+[^\|;]*\|\s*(?:bash|sh|zsh|dash|ksh|python|perl|ruby|node|php)",
         0),
        ("PS-EXF-002", "data_exfiltration", "critical",
         "Remote code execution: wget piped to shell",
         r"wget\s+[^\|;]*\|\s*(?:bash|sh|zsh|dash|python|perl|ruby|node)",
         0),
        ("PS-EXF-003", "data_exfiltration", "high",
         "Environment variable exfiltration",
         r"(?:curl|wget|nc|ncat)\s+.*(?:\$\{?\w*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*\}?|env\b|\bprintenv\b)",
         re.IGNORECASE),
        ("PS-EXF-004", "data_exfiltration", "high",
         "Piping sensitive files to network utility",
         r"cat\s+(?:~\/|/(?:etc|home|root)/)\S*(?:\.env|password|shadow|credentials|\.ssh|\.aws|\.kube)\S*\s*\|\s*(?:curl|wget|nc|ncat|netcat)",
         re.IGNORECASE),
        ("PS-EXF-005", "data_exfiltration", "medium",
         "Base64 encoding of secrets for exfiltration",
         r"base64\s+(?:-[a-zA-Z]\s+)*(?:.*(?:key|secret|token|password|cred))",
         re.IGNORECASE),
        ("PS-EXF-006", "data_exfiltration", "high",
         "DNS/HTTP exfiltration pattern",
         r"(?:\$\(|`).*(?:curl|wget|dig|nslookup|host)\s+.*\$\{?\w*(?:KEY|SECRET|TOKEN|PASS)",
         re.IGNORECASE),
    ]

    # -----------------------------------------------------------------------
    # 4. CREDENTIAL EXPOSURE  (PS-CRD-*)
    # -----------------------------------------------------------------------
    _crd = [
        ("PS-CRD-001", "credential_exposure", "critical",
         "Hardcoded AWS access key",
         r"(?:AKIA|ASIA)[0-9A-Z]{16}",
         0),
        ("PS-CRD-002", "credential_exposure", "critical",
         "Hardcoded AWS secret key pattern",
         r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?",
         0),
        ("PS-CRD-003", "credential_exposure", "high",
         "Hardcoded password in assignment",
         r"(?:password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{4,}['\"]",
         re.IGNORECASE),
        ("PS-CRD-004", "credential_exposure", "high",
         "Hardcoded API key in assignment",
         r"(?:api[_-]?key|apikey|api[_-]?secret)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
         re.IGNORECASE),
        ("PS-CRD-005", "credential_exposure", "high",
         "Hardcoded private key block",
         r"-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE\s+KEY-----",
         0),
        ("PS-CRD-006", "credential_exposure", "high",
         "Hardcoded JWT token",
         r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+",
         0),
        ("PS-CRD-007", "credential_exposure", "high",
         "GitHub/GitLab personal access token",
         r"(?:ghp|gho|ghu|ghs|ghr|glpat)[_-][A-Za-z0-9]{20,}",
         0),
        ("PS-CRD-008", "credential_exposure", "medium",
         "Generic secret/token assignment",
         r"(?:secret|token|auth)\s*[=:]\s*['\"][A-Za-z0-9_\-/.+=]{16,}['\"]",
         re.IGNORECASE),
        ("PS-CRD-009", "credential_exposure", "critical",
         "Google Cloud service account key (JSON)",
         r"\"type\"\s*:\s*\"service_account\"",
         0),
        ("PS-CRD-010", "credential_exposure", "high",
         "Slack webhook/bot token",
         r"(?:xoxb|xoxp|xoxs|xoxa|xoxr)-[0-9]{10,}-[A-Za-z0-9]+",
         0),
    ]

    # -----------------------------------------------------------------------
    # 5. CODE EXECUTION  (PS-EXC-*)
    # -----------------------------------------------------------------------
    _exc = [
        ("PS-EXC-001", "code_execution", "critical",
         "Dynamic code execution: eval()",
         r"\beval\s*\(",
         0),
        ("PS-EXC-002", "code_execution", "critical",
         "Dynamic code execution: exec()",
         r"\bexec\s*\(",
         0),
        ("PS-EXC-003", "code_execution", "critical",
         "Shell command execution: os.system()",
         r"\bos\s*\.\s*system\s*\(",
         0),
        ("PS-EXC-004", "code_execution", "high",
         "Shell injection risk: subprocess with shell=True",
         r"subprocess\.(?:call|run|Popen|check_output|check_call)\s*\([^)]*shell\s*=\s*True",
         0),
        ("PS-EXC-005", "code_execution", "critical",
         "Unsafe deserialization: pickle.loads",
         r"pickle\.(?:loads?|Unpickler)\s*\(",
         0),
        ("PS-EXC-006", "code_execution", "critical",
         "Unsafe deserialization: yaml.load without SafeLoader",
         r"yaml\.load\s*\([^)]*(?!Loader\s*=\s*yaml\.SafeLoader|Loader\s*=\s*SafeLoader)",
         0),
        ("PS-EXC-007", "code_execution", "high",
         "Dynamic import from user input",
         r"__import__\s*\(\s*(?!['\"]\w+['\"])",
         0),
        ("PS-EXC-008", "code_execution", "high",
         "JavaScript: Function constructor (eval equivalent)",
         r"new\s+Function\s*\(",
         0),
        ("PS-EXC-009", "code_execution", "high",
         "Template injection: server-side template evaluation",
         r"(?:render_template_string|Template\s*\(\s*(?:request|user|input|data))",
         0),
        ("PS-EXC-010", "code_execution", "high",
         "SQL injection: string concatenation in query",
         r"(?:execute|cursor\.execute|query)\s*\(\s*['\"].*['\"\s]*\+\s*(?:request|user|input|params|args)",
         re.IGNORECASE),
    ]

    # -----------------------------------------------------------------------
    # 6. PRIVILEGE ESCALATION  (PS-PRV-*)
    # -----------------------------------------------------------------------
    _prv = [
        ("PS-PRV-001", "privilege_escalation", "high",
         "Sudo execution in code/prompt",
         r"\bsudo\s+(?!-l\b|--list\b)\S",
         0),
        ("PS-PRV-002", "privilege_escalation", "critical",
         "World-writable permissions: chmod 777",
         r"chmod\s+(?:-[a-zA-Z]\s+)*777\s",
         0),
        ("PS-PRV-003", "privilege_escalation", "high",
         "Setuid/setgid bit modification",
         r"chmod\s+[^&;|]*[24]?[0-7]{3}.*\b(?:u\+s|g\+s|\+s)\b|chmod\s+[^&;|]*[46][0-7]{3}\s",
         0),
        ("PS-PRV-004", "privilege_escalation", "high",
         "Docker privileged mode",
         r"--privileged(?:\s|$|=)|privileged:\s*true",
         re.IGNORECASE),
        ("PS-PRV-005", "privilege_escalation", "medium",
         "Running container as root",
         r"(?:USER\s+root|user:\s*['\"]?root['\"]?|--user\s+(?:0|root))",
         0),
        ("PS-PRV-006", "privilege_escalation", "high",
         "Kubernetes host namespace sharing",
         r"(?:hostNetwork|hostPID|hostIPC):\s*true",
         0),
    ]

    # -----------------------------------------------------------------------
    # 7. UNSAFE NETWORK  (PS-NET-*)
    # -----------------------------------------------------------------------
    _net = [
        ("PS-NET-001", "unsafe_network", "high",
         "Binding to all interfaces: 0.0.0.0",
         r"(?:host|bind|listen|address)\s*[=:]\s*['\"]?0\.0\.0\.0['\"]?",
         re.IGNORECASE),
        ("PS-NET-002", "unsafe_network", "high",
         "TLS/SSL verification disabled",
         r"verify\s*=\s*False|CERT_NONE|check_hostname\s*=\s*False|InsecureRequestWarning|ssl\._create_unverified_context|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0",
         0),
        ("PS-NET-003", "unsafe_network", "medium",
         "HTTP used instead of HTTPS for sensitive endpoint",
         r"http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]).*(?:api|auth|login|token|oauth|payment|admin)",
         re.IGNORECASE),
        ("PS-NET-004", "unsafe_network", "high",
         "CORS wildcard: Allow-Origin * or allow-all",
         r"(?:Access-Control-Allow-Origin|cors_allowed_origins)\s*[=:]\s*['\"]?\*['\"]?|CORS_ORIGIN_ALLOW_ALL\s*[=:]\s*['\"]?(?:True|true|1)['\"]?",
         re.IGNORECASE),
        ("PS-NET-005", "unsafe_network", "medium",
         "Debug mode enabled in production config",
         r"(?:DEBUG|debug)\s*[=:]\s*['\"]?(?:True|true|1|yes|on)['\"]?",
         0),
    ]

    # -----------------------------------------------------------------------
    # 8. SENSITIVE DATA  (PS-DAT-*)
    # -----------------------------------------------------------------------
    _dat = [
        ("PS-DAT-001", "sensitive_data", "high",
         "Social Security Number pattern",
         r"\b\d{3}-\d{2}-\d{4}\b",
         0),
        ("PS-DAT-002", "sensitive_data", "high",
         "Credit card number pattern (Visa/MC/Amex/Discover)",
         r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
         0),
        ("PS-DAT-003", "sensitive_data", "medium",
         "Email address in hardcoded string",
         r"['\"][^'\"]*[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^'\"]*['\"]",
         0),
        ("PS-DAT-004", "sensitive_data", "high",
         "IP address with sensitive port (SSH/DB/RDP)",
         r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:(?:22|3306|5432|1433|3389|6379|27017|9200)\b",
         0),
        ("PS-DAT-005", "sensitive_data", "medium",
         "Connection string with embedded credentials",
         r"(?:mysql|postgres|postgresql|mongodb|redis|amqp|mssql)://\w+:[^@\s]+@",
         re.IGNORECASE),
    ]

    # Combine all rule groups
    all_raw = _inj + _cmd + _exf + _crd + _exc + _prv + _net + _dat

    compiled: List[Rule] = []
    for rule_id, category, severity, description, pattern, flags in all_raw:
        try:
            compiled.append(
                (rule_id, category, severity, description, re.compile(pattern, flags))
            )
        except re.error as exc:
            logger.warning("Failed to compile rule %s: %s", rule_id, exc)

    return compiled


# Pre-compile all rules at import time
_ALL_RULES: List[Rule] = _compile_rules()

# Map category name → list of rules (for selective scanning)
_RULES_BY_CATEGORY: Dict[str, List[Rule]] = {}
for _r in _ALL_RULES:
    _RULES_BY_CATEGORY.setdefault(_r[1], []).append(_r)


# ===========================================================================
# Prompt Scanner Analyzer
# ===========================================================================

class PromptScanner(Analyzer):
    """Scans prompts, instructions, and code for security vulnerabilities.

    Detects prompt injection, destructive commands, data exfiltration,
    credential exposure, code execution risks, privilege escalation,
    unsafe network patterns, and sensitive data leaks.

    Operates entirely offline using regex pattern matching.
    """

    def name(self) -> str:
        return "prompt_scanner"

    def dimension(self) -> str:
        return "security"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run the prompt security scan on all relevant files.

        Settings:
            categories: list of category names to scan (default: all)
            min_severity: minimum severity to report (default: "low")
            extra_extensions: additional file extensions to scan
        """
        # --- Resolve settings ---
        enabled_categories: Optional[List[str]] = settings.get("categories")
        min_severity: str = settings.get("min_severity", "low")
        extra_exts_raw: List[str] = settings.get("extra_extensions", [])
        extra_exts = set(extra_exts_raw) if extra_exts_raw else _DEFAULT_EXTRA_EXTENSIONS

        # Build list of active rules
        active_rules = self._filter_rules(enabled_categories)

        # Severity ordering for filtering
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_sev_val = severity_order.get(min_severity, 0)

        # --- Discover files ---
        scan_extensions = _SOURCE_EXTENSIONS | extra_exts
        files_to_scan = self._discover_files(repo_path, scan_extensions, settings)
        logger.info(
            "Prompt scanner: found %d files to scan in %s",
            len(files_to_scan), repo_path,
        )

        if not files_to_scan:
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=["No files found to scan"],
            )

        # --- Scan files ---
        all_threats: List[PromptThreat] = []
        per_file_scores: Dict[str, float] = {}
        warnings: List[str] = []

        for filepath in files_to_scan:
            try:
                file_threats = self._scan_file(filepath, active_rules, repo_path)
            except Exception as exc:
                logger.warning("Failed to scan %s: %s", filepath, exc)
                warnings.append(f"Scan error: {filepath}: {exc}")
                continue

            # Filter by minimum severity
            file_threats = [
                t for t in file_threats
                if severity_order.get(t.severity, 0) >= min_sev_val
            ]

            all_threats.extend(file_threats)

            # Compute per-file score
            try:
                rel_path = str(filepath.relative_to(repo_path))
            except ValueError:
                rel_path = str(filepath)

            penalty = sum(
                _SEVERITY_WEIGHTS.get(t.severity, 3) for t in file_threats
            )
            per_file_scores[rel_path] = max(0.0, 100.0 - penalty)

        # --- Compute overall score ---
        if per_file_scores:
            # Average file scores, but weight more heavily toward worst files
            scores = sorted(per_file_scores.values())
            # Give extra influence to worst 20% of files
            worst_count = max(1, len(scores) // 5)
            worst_avg = sum(scores[:worst_count]) / worst_count
            overall_avg = sum(scores) / len(scores)
            # 60% overall average, 40% worst-file influence
            normalized_score = 0.6 * overall_avg + 0.4 * worst_avg
        else:
            normalized_score = 100.0

        normalized_score = max(0.0, min(100.0, round(normalized_score, 2)))

        # --- Build category summary ---
        category_summary: Dict[str, Dict[str, int]] = {}
        for t in all_threats:
            cs = category_summary.setdefault(t.category, {
                "critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0
            })
            cs[t.severity] += 1
            cs["total"] += 1

        severity_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for t in all_threats:
            severity_summary[t.severity] += 1

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=normalized_score,
            per_file_scores=per_file_scores,
            details={
                "total_threats": len(all_threats),
                "severity_summary": severity_summary,
                "category_summary": category_summary,
                "threats": [
                    {
                        "rule_id": t.rule_id,
                        "category": t.category,
                        "severity": t.severity,
                        "description": t.description,
                        "matched_text": t.matched_text[:200],
                        "file_path": t.file_path,
                        "line_number": t.line_number,
                    }
                    for t in all_threats
                ],
                "files_scanned": len(files_to_scan),
            },
            warnings=warnings,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _filter_rules(
        categories: Optional[List[str]],
    ) -> List[Rule]:
        """Return rules filtered by enabled categories (None = all)."""
        if categories is None:
            return list(_ALL_RULES)
        active: List[Rule] = []
        for cat in categories:
            active.extend(_RULES_BY_CATEGORY.get(cat, []))
        return active

    @staticmethod
    def _discover_files(
        repo_path: Path,
        extensions: Set[str],
        settings: Dict[str, Any],
    ) -> List[Path]:
        """Walk repo and return files matching target extensions."""
        extra_exclude = set(settings.get("exclude_dirs", []))
        excluded = _EXCLUDED_DIRS | extra_exclude
        files: List[Path] = []

        for dirpath, dirnames, filenames in os.walk(repo_path):
            # Prune excluded directories
            dirnames[:] = [d for d in dirnames if d not in excluded]

            for filename in filenames:
                fp = Path(dirpath) / filename
                ext = fp.suffix.lower()

                # Also match Dockerfile, Makefile, etc. by name
                basename_lower = filename.lower()
                is_special = basename_lower in {
                    "dockerfile", "makefile", "vagrantfile",
                    "jenkinsfile", ".env", ".env.example",
                    ".env.local", ".env.production",
                }

                if ext not in extensions and not is_special:
                    continue

                # Skip files that are too large
                try:
                    if fp.stat().st_size > _MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue

                files.append(fp)

        return files

    def _scan_file(
        self,
        filepath: Path,
        rules: List[Rule],
        repo_path: Path,
    ) -> List[PromptThreat]:
        """Scan a single file against all active rules."""
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", filepath, exc)
            return []

        try:
            rel_path = str(filepath.relative_to(repo_path))
        except ValueError:
            rel_path = str(filepath)

        lines = content.split("\n")
        threats: List[PromptThreat] = []
        seen: Set[Tuple[str, int]] = set()  # (rule_id, line_number) dedup

        for rule_id, category, severity, description, pattern in rules:
            for line_num, line in enumerate(lines, start=1):
                match = pattern.search(line)
                if match:
                    dedup_key = (rule_id, line_num)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    matched_text = match.group(0)

                    threats.append(PromptThreat(
                        category=category,
                        severity=severity,
                        description=description,
                        matched_text=matched_text,
                        file_path=rel_path,
                        line_number=line_num,
                        rule_id=rule_id,
                    ))

        return threats
