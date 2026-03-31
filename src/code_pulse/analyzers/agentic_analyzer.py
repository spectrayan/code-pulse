"""Multi-LLM semantic scoring analyzer implemented as a LangGraph sub-graph."""

import json
import logging
import re
import statistics
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from code_pulse.analyzers.base import Analyzer
from code_pulse.core.discovery import EXTENSION_TO_LANGUAGE, FileDiscovery
from code_pulse.core.models import AnalyzerResult, StandardViolation
from code_pulse.analyzers.standards_loader import CodingStandardsLoader

logger = logging.getLogger(__name__)

_LLM_PROMPT_TEMPLATE = """\
You are a code quality analyst. Evaluate the following source file(s) against the provided coding standards.

## Coding Standards
{standards_text}

## Source Files
{files_block}

For EACH file, respond with a JSON array (one object per file). Each object must contain:
{{
  "file_path": "<path>",
  "readability_score": <0-100>,
  "architecture_score": <0-100>,
  "design_smell_score": <0-100>,
  "standards_compliance_score": <0-100>,
  "overall_score": <0-100>,
  "violations": [
    {{"standard_name": "<name>", "description": "<description>"}}
  ],
  "refactor_suggestions": ["<suggestion1>"]
}}

Respond with ONLY the JSON array (no markdown fencing, no extra text).
If you cannot evaluate the file, still return the JSON object with scores set to 50 and a violation explaining why.
Score meanings: 0 = worst quality, 100 = best quality.
"""


class AgenticState(TypedDict):
    """State for the agentic analyzer LangGraph sub-graph."""

    files: List[Dict[str, str]]  # list of {path, content, language}
    coding_standards: List[str]  # loaded standards documents
    llm_results: List[Dict[str, Any]]  # results from each LLM provider
    aggregation_strategy: str


def _create_openai(model: str, api_key: str, **_kwargs) -> Optional[Any]:
    from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]
    return ChatOpenAI(model=model, api_key=api_key)


def _create_anthropic(model: str, api_key: str, **_kwargs) -> Optional[Any]:
    from langchain_anthropic import ChatAnthropic  # type: ignore[import-untyped]
    return ChatAnthropic(model=model, api_key=api_key)


def _create_google_genai(model: str, api_key: str, **_kwargs) -> Optional[Any]:
    from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import-untyped]
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key)


def _create_ollama(model: str, api_key: str, **kwargs) -> Optional[Any]:
    from langchain_ollama import ChatOllama  # type: ignore[import-untyped]
    base_url = kwargs.get("base_url", "http://localhost:11434")
    return ChatOllama(model=model, base_url=base_url)


# Registry mapping provider names to their factory callables.
# To add a new provider, simply add an entry here.
_LLM_PROVIDER_REGISTRY: Dict[str, Callable[..., Optional[Any]]] = {
    "openai": _create_openai,
    "anthropic": _create_anthropic,
    "google_genai": _create_google_genai,
    "google": _create_google_genai,
    "gemini": _create_google_genai,
    "ollama": _create_ollama,
}


def _get_llm_provider(provider_config: Dict[str, Any]):
    """Factory: instantiate a LangChain chat model for the given provider.

    Returns None if the required package is not installed.
    """
    provider_name = provider_config.get("name", "").lower()
    model = provider_config.get("model", "")
    api_key = provider_config.get("api_key", "")

    factory = _LLM_PROVIDER_REGISTRY.get(provider_name)
    if factory is None:
        logger.warning("Unknown LLM provider '%s'. Skipping.", provider_name)
        return None

    try:
        extra = {k: v for k, v in provider_config.items() if k not in ("name", "model", "api_key")}
        return factory(model=model, api_key=api_key, **extra)
    except ImportError:
        logger.warning(
            "Required package for provider '%s' is not installed. Skipping.",
            provider_name,
        )
        return None


def _parse_llm_response(text: str) -> Optional[List[Dict[str, Any]]]:
    """Parse the JSON response from an LLM. Returns a list of per-file result dicts.

    Handles both a JSON array and a single JSON object (wraps in list).
    Tolerates markdown fencing and extra conversational text.
    Ensures that returned items are dictionaries.
    """
    cleaned = text.strip()

    def _validate_parsed(data: Any) -> Optional[List[Dict[str, Any]]]:
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            # Only keep dicts to avoid 'int' object has no attribute 'get' errors later
            valid = [item for item in data if isinstance(item, dict)]
            return valid if valid else None
        return None

    # 1. Try direct JSON parsing first
    try:
        parsed = json.loads(cleaned)
        validated = _validate_parsed(parsed)
        if validated:
            return validated
    except json.JSONDecodeError:
        pass

    # 2. Try to find JSON inside markdown blocks
    # We look for ```json ... ``` or just ``` ... ```
    md_json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if md_json_match:
        try:
            content = md_json_match.group(1).strip()
            parsed = json.loads(content)
            validated = _validate_parsed(parsed)
            if validated:
                return validated
        except json.JSONDecodeError:
            pass

    # 3. Fallback: Try to find anything that looks like a JSON array or object
    # This is more aggressive and might catch JSON even if surrounded by text.
    # We look for the first '[' and last ']' OR first '{' and last '}'
    # greedily to capture the outermost structure.
    array_match = re.search(r"(\[[\s\S]*\])", cleaned)
    if array_match:
        content = array_match.group(1)
        # Try to find the last ']' from the end to be sure we get the full array if there's trailing text
        # re.search with [\s\S]* is greedy by default, so it should already find the last one.
        try:
            parsed = json.loads(content)
            validated = _validate_parsed(parsed)
            if validated:
                return validated
        except json.JSONDecodeError:
            # If greedy failed, try non-greedy and step by step if needed?
            # Actually, if greedy failed it might be because of extra text after the last ]
            # that was somehow captured or nested.
            pass

    object_match = re.search(r"(\{[\s\S]*\})", cleaned)
    if object_match:
        try:
            parsed = json.loads(object_match.group(1))
            validated = _validate_parsed(parsed)
            if validated:
                return validated
        except json.JSONDecodeError:
            pass

    # 4. Final effort: Try to recover if it's a list of items that look like JSON but are comma-separated without outer brackets
    # This sometimes happens if the LLM starts with [{...}, {...}] but gets cut off or omits the brackets.
    if "{" in cleaned and "}" in cleaned:
        try:
            # Try to find all objects
            potential_objects = re.findall(r"(\{[\s\S]*?\})", cleaned)
            parsed_objects = []
            for obj_str in potential_objects:
                try:
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict):
                        parsed_objects.append(obj)
                except json.JSONDecodeError:
                    continue
            if parsed_objects:
                return parsed_objects
        except Exception:
            pass

    logger.warning("Failed to parse LLM response as JSON or it was not a dictionary: %.500s", cleaned)
    return None


def _clamp_score(value: Any) -> float:
    """Clamp a value to [0, 100], defaulting to 50 on bad input."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 50.0
    return max(0.0, min(100.0, score))


class AgenticAnalyzer(Analyzer):
    """Multi-LLM semantic analyzer implemented as a LangGraph sub-graph.

    Sends source code along with coding standards context to one or more
    LLM providers in parallel, then aggregates their scores using a
    configurable strategy (median, average, or conservative min).
    """

    def name(self) -> str:
        return "agentic"

    def dimension(self) -> str:
        return "semantic"

    def analyze(self, repo_path: Path, settings: Dict[str, Any]) -> AnalyzerResult:
        """Run multi-LLM semantic analysis on discovered source files.

        Settings:
            max_files: Maximum number of files to analyze (default: 5)
            batch_size: Number of files to send per LLM call (default: 3)
            aggregation_strategy: median | average | conservative
            providers: list of LLM provider configs
        """
        # --- Load coding standards ---
        cs_config = settings.get("_coding_standards_config")
        if cs_config is not None:
            loader = CodingStandardsLoader(
                predefined_overrides=getattr(cs_config, "predefined_overrides", {})
            )
            all_standards = loader.load(standards_config=cs_config)
        else:
            loader = CodingStandardsLoader()
            all_standards = loader.load(settings)

        # --- Discover files ---
        discovered = FileDiscovery.discover(repo_path)
        if not discovered:
            logger.warning("No source files found in %s", repo_path)
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=["No source files found"],
            )

        # --- Read LLM provider configs ---
        providers: List[Dict[str, Any]] = settings.get("providers", [])
        if not providers:
            logger.warning("No LLM providers configured for agentic analyzer")
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=50.0,
                warnings=["No LLM providers configured"],
            )

        strategy = settings.get("aggregation_strategy", "median")
        max_files = settings.get("max_files", 5)
        batch_size = settings.get("batch_size", 3)

        # --- Prepare file list with language-filtered standards ---
        file_entries: List[Dict[str, str]] = []
        for language, paths in discovered.items():
            lang_standards = CodingStandardsLoader.filter_by_language(
                all_standards, language
            )
            standards_text = "\n\n---\n\n".join(
                f"### {s.name}\n{s.content}" for s in lang_standards
            ) or "No specific coding standards loaded."

            for file_path in paths:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    logger.warning("Cannot read file %s: %s", file_path, exc)
                    continue
                file_entries.append(
                    {
                        "path": str(file_path),
                        "content": content,
                        "language": language,
                        "standards_text": standards_text,
                    }
                )

        if not file_entries:
            logger.warning("No readable source files found")
            return AnalyzerResult(
                analyzer_name=self.name(),
                dimension=self.dimension(),
                normalized_score=100.0,
                warnings=["No readable source files found"],
            )

        # --- Limit files and log ---
        total_found = len(file_entries)
        if max_files and len(file_entries) > max_files:
            # Prioritize: sort by file size (larger files more interesting) and take top N
            file_entries.sort(key=lambda e: len(e["content"]), reverse=True)
            file_entries = file_entries[:max_files]
            logger.info(
                "Limiting agentic analysis to %d/%d files (max_files=%d)",
                len(file_entries), total_found, max_files,
            )

        # --- Build the sub-graph once and reuse ---
        per_file_scores: Dict[str, float] = {}
        all_violations: List[StandardViolation] = []
        all_suggestions: Dict[str, List[str]] = {}
        per_file_llm_details: Dict[str, List[Dict[str, Any]]] = {}  # file -> list of provider results
        warnings: List[str] = []
        if total_found > max_files:
            warnings.append(f"Analyzed {max_files}/{total_found} files (max_files limit)")

        graph = self._build_subgraph(providers)

        # --- Process in batches ---
        for batch_start in range(0, len(file_entries), batch_size):
            batch = file_entries[batch_start:batch_start + batch_size]
            logger.info(
                "Agentic batch %d-%d of %d files",
                batch_start + 1, batch_start + len(batch), len(file_entries),
            )
            try:
                initial_state: AgenticState = {
                    "files": batch,
                    "coding_standards": [batch[0]["standards_text"]],
                    "llm_results": [],
                    "aggregation_strategy": strategy,
                }
                final_state = graph.invoke(initial_state)

                llm_results = final_state.get("llm_results", [])
                if not llm_results:
                    for entry in batch:
                        warnings.append(f"No LLM results for {entry['path']}")
                    continue

                # Group results by file path
                for result in llm_results:
                    if not isinstance(result, dict):
                        logger.warning("Skipping non-dictionary LLM result: %s", result)
                        continue
                    fp = result.get("file_path", "")
                    if fp:
                        agg = self._aggregate_scores([result], strategy)
                        per_file_scores[fp] = agg["overall_score"]

                        # Store full provider detail for the report
                        per_file_llm_details.setdefault(fp, []).append({
                            "provider": result.get("provider", "unknown"),
                            "readability_score": result.get("readability_score", 50),
                            "architecture_score": result.get("architecture_score", 50),
                            "design_smell_score": result.get("design_smell_score", 50),
                            "standards_compliance_score": result.get("standards_compliance_score", 50),
                            "overall_score": result.get("overall_score", 50),
                        })

                        for v in result.get("violations", []):
                            all_violations.append(
                                StandardViolation(
                                    standard_name=v.get("standard_name", "unknown"),
                                    description=v.get("description", ""),
                                    file_path=fp,
                                )
                            )
                        suggs = result.get("refactor_suggestions", [])
                        if suggs:
                            all_suggestions.setdefault(fp, []).extend(suggs)

            except Exception as exc:
                paths_str = ", ".join(e["path"].split("/")[-1] for e in batch)
                logger.error("Agentic batch failed for [%s]: %s", paths_str, exc)
                warnings.append(f"Batch analysis failed: {exc}")

        if per_file_scores:
            normalized_score = sum(per_file_scores.values()) / len(per_file_scores)
        else:
            normalized_score = 50.0
            warnings.append("No files were successfully scored by LLMs")

        return AnalyzerResult(
            analyzer_name=self.name(),
            dimension=self.dimension(),
            normalized_score=round(normalized_score, 2),
            per_file_scores=per_file_scores,
            details={
                "file_count": len(per_file_scores),
                "refactor_suggestions": all_suggestions,
                "per_file_llm_details": per_file_llm_details,
                "aggregation_strategy": strategy,
            },
            warnings=warnings,
            violations=all_violations,
        )

    def _build_subgraph(
        self, llm_configs: List[Dict[str, Any]]
    ) -> "StateGraph":
        """Create a LangGraph StateGraph with parallel LLM nodes and an aggregator.

        Each LLM provider config becomes a node that runs in parallel.
        An aggregator node combines results after all LLM nodes complete.
        """
        builder = StateGraph(AgenticState)

        valid_provider_names: List[str] = []

        for i, config in enumerate(llm_configs):
            provider_name = config.get("name", f"llm_{i}")
            node_name = f"llm_{provider_name}_{i}"
            node_fn = self._create_llm_node(config)
            if node_fn is not None:
                builder.add_node(node_name, node_fn)
                valid_provider_names.append(node_name)

        if not valid_provider_names:
            # No valid providers — build a minimal graph that does nothing
            def _noop(state: AgenticState) -> AgenticState:
                return state

            builder.add_node("noop", _noop)
            builder.set_entry_point("noop")
            builder.add_edge("noop", END)
            return builder.compile()

        # Add aggregator node
        def aggregator(state: AgenticState) -> AgenticState:
            return state  # results already collected by LLM nodes

        builder.add_node("aggregator", aggregator)

        # Wire parallel LLM nodes: all start from entry, all feed into aggregator
        # Use a fan-out / fan-in pattern
        if len(valid_provider_names) == 1:
            # Single provider — linear graph
            builder.set_entry_point(valid_provider_names[0])
            builder.add_edge(valid_provider_names[0], "aggregator")
        else:
            # Multiple providers — fan-out from a dispatcher, fan-in to aggregator
            def dispatcher(state: AgenticState) -> AgenticState:
                return state

            builder.add_node("dispatcher", dispatcher)
            builder.set_entry_point("dispatcher")

            for node_name in valid_provider_names:
                builder.add_edge("dispatcher", node_name)
                builder.add_edge(node_name, "aggregator")

        builder.add_edge("aggregator", END)
        return builder.compile()

    def _create_llm_node(
        self, provider_config: Dict[str, Any]
    ) -> Optional[Callable[[AgenticState], AgenticState]]:
        """Return a node function that calls a single LLM provider.

        The node sends code content + coding standards to the LLM API,
        parses the JSON response for scores and violations, and appends
        results to state['llm_results'].

        Returns None if the provider cannot be instantiated.
        """
        llm = _get_llm_provider(provider_config)
        if llm is None:
            return None

        max_retries = provider_config.get("max_retries", 3)
        provider_name = provider_config.get("name", "unknown")

        def llm_node(state: AgenticState) -> Dict[str, Any]:
            results = list(state.get("llm_results", []))
            standards_text = (
                state["coding_standards"][0]
                if state.get("coding_standards")
                else "No coding standards loaded."
            )

            files = state.get("files", [])
            if not files:
                return {"llm_results": results}

            # Build a single prompt with all files in the batch
            files_block_parts = []
            file_paths = []
            for file_info in files:
                fp = file_info["path"]
                content = file_info["content"][:6000]  # Truncate per file
                short_name = fp.split("/")[-1] if "/" in fp else fp
                files_block_parts.append(f"### {short_name} ({fp})\n```\n{content}\n```")
                file_paths.append(fp)

            files_block = "\n\n".join(files_block_parts)
            prompt = _LLM_PROMPT_TEMPLATE.format(
                standards_text=standards_text,
                files_block=files_block,
            )

            logger.info("Calling LLM provider '%s' (batch size: %d)", provider_name, len(files))
            parsed_list = None
            last_error = None
            for attempt in range(max_retries):
                try:
                    response = llm.invoke(prompt)
                    raw_content = response.content if hasattr(response, "content") else response
                    if isinstance(raw_content, list):
                        response_text = "".join(
                            part.get("text", str(part)) if isinstance(part, dict) else str(part)
                            for part in raw_content
                        )
                    else:
                        response_text = str(raw_content)
                    
                    logger.debug("Raw LLM %s response (attempt %d):\n%s", provider_name, attempt + 1, response_text)
                    
                    parsed_list = _parse_llm_response(response_text)
                    if parsed_list is not None:
                        logger.info("Successfully parsed response from LLM '%s'", provider_name)
                        break
                    
                    # If parsing failed, we might want to see more of the response even if not in debug mode
                    # but only if it's the last attempt or if we want to be noisy.
                    # Given the user's request, let's log a snippet at WARNING level.
                    logger.warning(
                        "LLM %s returned unparseable response (attempt %d). Snippet: %.500s",
                        provider_name, attempt + 1, response_text
                    )
                except Exception as exc:
                    last_error = exc
                    error_str = str(exc).lower()
                    if "rate" in error_str and "limit" in error_str:
                        wait_time = 2 ** attempt
                        logger.warning(
                            "Rate limit hit for %s, retrying in %ds (%d/%d)",
                            provider_name, wait_time, attempt + 1, max_retries,
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            "LLM %s error (attempt %d/%d): %s",
                            provider_name, attempt + 1, max_retries, exc,
                        )
                        if attempt < max_retries - 1:
                            time.sleep(1)

            if parsed_list is None:
                logger.error(
                    "LLM %s failed after %d retries: %s",
                    provider_name, max_retries, last_error,
                )
                return {"llm_results": results}

            # Map parsed results back to file paths
            for item in parsed_list:
                fp = item.get("file_path", "")
                # If LLM didn't return file_path, try to match by index
                if not fp and len(parsed_list) == len(file_paths):
                    idx = parsed_list.index(item)
                    fp = file_paths[idx]
                if not fp and len(file_paths) == 1:
                    fp = file_paths[0]
                results.append({
                    "provider": provider_name,
                    "file_path": fp,
                    "readability_score": _clamp_score(item.get("readability_score", 50)),
                    "architecture_score": _clamp_score(item.get("architecture_score", 50)),
                    "design_smell_score": _clamp_score(item.get("design_smell_score", 50)),
                    "standards_compliance_score": _clamp_score(item.get("standards_compliance_score", 50)),
                    "overall_score": _clamp_score(item.get("overall_score", 50)),
                    "violations": item.get("violations", []),
                    "refactor_suggestions": item.get("refactor_suggestions", []),
                })

            return {"llm_results": results}

        return llm_node

    @staticmethod
    def _aggregate_scores(
        llm_results: List[Dict[str, Any]], strategy: str
    ) -> Dict[str, float]:
        """Aggregate scores from multiple LLM providers.

        Strategies:
        - 'median': Use statistics.median across LLMs
        - 'average': Use arithmetic mean
        - 'conservative': Use minimum score (most pessimistic)

        Single LLM: return that score directly.
        """
        if not llm_results:
            return {"overall_score": 50.0}

        if len(llm_results) == 1:
            return {
                "readability_score": llm_results[0].get("readability_score", 50.0),
                "architecture_score": llm_results[0].get("architecture_score", 50.0),
                "design_smell_score": llm_results[0].get("design_smell_score", 50.0),
                "standards_compliance_score": llm_results[0].get(
                    "standards_compliance_score", 50.0
                ),
                "overall_score": llm_results[0].get("overall_score", 50.0),
            }

        score_keys = [
            "readability_score",
            "architecture_score",
            "design_smell_score",
            "standards_compliance_score",
            "overall_score",
        ]

        aggregated: Dict[str, float] = {}
        for key in score_keys:
            values = [r.get(key, 50.0) for r in llm_results]
            if strategy == "median":
                aggregated[key] = statistics.median(values)
            elif strategy == "average":
                aggregated[key] = sum(values) / len(values)
            elif strategy == "conservative":
                aggregated[key] = min(values)
            else:
                logger.warning(
                    "Unknown aggregation strategy '%s', defaulting to median",
                    strategy,
                )
                aggregated[key] = statistics.median(values)

        return aggregated
