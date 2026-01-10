from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import requests

from .loaders import GoldenCase, load_golden_cases, dump_jsonl
from .scoring import score_answer


def call_chatbot_http(
    base_url: str,
    question: str,
    active_docs: Optional[str] = None,
    timeout: int = 60,
) -> str:
    """
    Mặc định bám theo format phổ biến bạn từng dùng:
    POST {base_url} với JSON: { "question": "...", "active_docs": "local-folder" }

    Nếu hệ thống bạn khác format, sửa chỗ này là xong.
    """
    payload: Dict[str, Any] = {"question": question}
    if active_docs:
        payload["active_docs"] = active_docs

    r = requests.post(base_url, json=payload, timeout=timeout)
    r.raise_for_status()

    # Chấp nhận 2 kiểu:
    # - { "answer": "..." }
    # - plain text
    try:
        data = r.json()
        if isinstance(data, dict) and "answer" in data:
            return str(data["answer"])
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return r.text


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--golden", required=True, help="Path tới YAML golden set")
    p.add_argument("--endpoint", default="http://localhost:7091/api/answer", help="HTTP endpoint chatbot")
    p.add_argument("--out", default="evaluate/_runs/latest.jsonl", help="Output JSONL")
    p.add_argument("--timeout", type=int, default=60)
    args = p.parse_args(argv)

    cases = load_golden_cases(args.golden)
    rows: List[Dict[str, Any]] = []

    pass_n = 0
    for c in cases:
        answer = call_chatbot_http(
            base_url=args.endpoint,
            question=c.question,
            active_docs=c.active_docs,
            timeout=args.timeout,
        )
        s = score_answer(answer, c.expected)
        rows.append(
            {
                "case": asdict(c),
                "answer": answer,
                "score": s.score,
                "max_score": s.max_score,
                "passed": s.passed,
                "details": s.details,
            }
        )
        pass_n += 1 if s.passed else 0

    dump_jsonl(rows, args.out)
    total = len(cases)
    print(f"Ran {total} cases. Passed: {pass_n}/{total}. Output: {args.out}")
    # exit code non-zero nếu pass rate thấp
    if total > 0 and (pass_n / total) < 0.8:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
