from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class GoldenCase:
    id: str
    category: str
    question: str
    persona: str = "general"
    active_docs: Optional[str] = None
    expected: Dict[str, Any] = None


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_golden_cases(path: str | Path) -> List[GoldenCase]:
    path = Path(path)
    data = load_yaml(path)
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"Golden set YAML must be a dict with key 'cases': {path}")

    cases_raw = data["cases"]
    if not isinstance(cases_raw, list) or len(cases_raw) == 0:
        raise ValueError(f"'cases' must be a non-empty list: {path}")

    out: List[GoldenCase] = []
    for c in cases_raw:
        if not isinstance(c, dict):
            raise ValueError(f"Each case must be an object: {c}")
        out.append(
            GoldenCase(
                id=str(c["id"]),
                category=str(c.get("category", "uncategorized")),
                question=str(c["question"]),
                persona=str(c.get("persona", "general")),
                active_docs=c.get("active_docs", None),
                expected=c.get("expected", {}) or {},
            )
        )
    return out


def dump_jsonl(rows: List[Dict[str, Any]], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
