"""Trend store — persists and retrieves historical CodePulse scores."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from code_pulse.core.models import TrendData, TrendEntry

_TOLERANCE = 0.5


def _compute_direction(
    entries: list[TrendEntry],
) -> Literal["improving", "stable", "degrading"]:
    """Compare the latest two entries to determine trend direction."""
    if len(entries) < 2:
        return "stable"
    latest = entries[-1].score
    previous = entries[-2].score
    diff = latest - previous
    if diff > _TOLERANCE:
        return "improving"
    if diff < -_TOLERANCE:
        return "degrading"
    return "stable"


class TrendStore:
    """Persists TrendEntry objects as JSON lines and loads them back."""

    @staticmethod
    def save(entry: TrendEntry, path: Path = Path(".codepulse-trend.jsonl")) -> None:
        """Append a single TrendEntry as a JSON line."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    @staticmethod
    def load(path: Path = Path(".codepulse-trend.jsonl")) -> TrendData:
        """Read all entries from the JSONL file and compute direction."""
        entries: list[TrendEntry] = []
        if not path.exists():
            return TrendData(entries=entries, direction="stable")

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                entries.append(
                    TrendEntry(
                        timestamp=data["timestamp"],
                        score=data["score"],
                        tier=data["tier"],
                    )
                )

        return TrendData(entries=entries, direction=_compute_direction(entries))
