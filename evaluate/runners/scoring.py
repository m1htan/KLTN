from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ScoreResult:
    score: float
    max_score: float
    passed: bool
    details: Dict[str, Any]


_RE_HAS_DIEU = re.compile(r"\bĐiều\s+\d+", re.IGNORECASE)
_RE_HAS_KHOAN = re.compile(r"\bKhoản\s+\d+", re.IGNORECASE)
_RE_HAS_POINT = re.compile(r"\bĐiểm\s+[a-zđ]\b", re.IGNORECASE)

# Dấu hiệu “bịa số điều” kiểu rất lớn hoặc vô lý hay gặp khi hallucination
_RE_SUS_HALLU_DIEU = re.compile(r"\bĐiều\s+([5-9]\d{2,}|\d{4,})\b", re.IGNORECASE)


def _match_any(text: str, patterns: List[str]) -> Tuple[int, List[str]]:
    hits = []
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE | re.MULTILINE):
            hits.append(p)
    return len(hits), hits


def score_answer(answer: str, expected: Dict[str, Any]) -> ScoreResult:
    """
    Chấm theo heuristics:
    - Must include / must not include (hard constraints)
    - Có căn cứ: Điều/Khoản/Điểm hoặc ít nhất nhắc luật + đề nghị đối chiếu
    - Nếu expected yêu cầu hỏi lại: check có câu hỏi '?' hoặc các từ khóa hỏi lại
    """
    max_score = 10.0
    score = 0.0
    details: Dict[str, Any] = {}

    behavior = (expected.get("behavior") or {})
    must_include = expected.get("must_include") or []
    must_not_include = expected.get("must_not_include") or []
    relevant_laws = expected.get("relevant_laws") or []

    # 0) hard fail nếu có dấu hiệu bịa điều khoản cực đoan hoặc vi phạm must_not
    bad_count, bad_hits = _match_any(answer, must_not_include)
    sus_hallu = bool(_RE_SUS_HALLU_DIEU.search(answer))
    details["must_not_hits"] = bad_hits
    details["sus_hallucinated_article_number"] = sus_hallu
    if bad_count > 0:
        return ScoreResult(0.0, max_score, False, {**details, "reason": "must_not_include violated"})
    if behavior.get("should_refuse_hallucination", False) and sus_hallu:
        return ScoreResult(0.0, max_score, False, {**details, "reason": "hallucinated article number"})

    # 1) Định hướng đúng luật liên quan (0-3): đo bằng số luật kỳ vọng được nhắc
    law_hits = 0
    law_hit_list = []
    for lw in relevant_laws:
        if lw and re.search(re.escape(lw), answer, flags=re.IGNORECASE):
            law_hits += 1
            law_hit_list.append(lw)
    details["relevant_law_hits"] = law_hit_list
    if len(relevant_laws) == 0:
        score += 2.0  # không đặt kỳ vọng luật cụ thể thì cho điểm nền
    else:
        ratio = law_hits / max(1, len(relevant_laws))
        if ratio >= 0.67:
            score += 3.0
        elif ratio >= 0.34:
            score += 2.0
        elif ratio > 0:
            score += 1.0

    # 2) Căn cứ pháp lý và cấu trúc (0-3)
    has_basis = bool(_RE_HAS_DIEU.search(answer) or _RE_HAS_KHOAN.search(answer) or _RE_HAS_POINT.search(answer))
    details["has_dieu"] = bool(_RE_HAS_DIEU.search(answer))
    details["has_khoan"] = bool(_RE_HAS_KHOAN.search(answer))
    if has_basis:
        score += 3.0
    else:
        # nếu không có Điều/Khoản thì vẫn có thể được điểm nếu có “đề nghị đối chiếu văn bản”
        soft_basis = bool(re.search(r"đối chiếu|tra cứu|văn bản gốc|trích dẫn", answer, flags=re.IGNORECASE))
        details["soft_basis"] = soft_basis
        # Trường hợp chỉ hỏi lại để lấy ngữ cảnh (clarifying) là hành vi đúng,
        # không nên bị phạt quá nặng vì chưa kịp đưa căn cứ.
        score += 2.0 if soft_basis else 1.0

    # 3) Xử lý thiếu ngữ cảnh (0-2)
    should_ask = bool(behavior.get("should_ask_clarifying", False))
    asked = bool("?" in answer or re.search(r"bạn cho mình biết|bạn cung cấp|mình cần bạn|làm rõ", answer, flags=re.IGNORECASE))
    details["should_ask_clarifying"] = should_ask
    details["asked_clarifying"] = asked
    if should_ask:
        score += 2.0 if asked else 0.0
    else:
        score += 1.0 if asked else 2.0  # hỏi thêm vẫn ok, nhưng không bắt buộc

    # 4) Must include (0-2) như checklist chất lượng
    good_count, good_hits = _match_any(answer, must_include)
    details["must_include_hits"] = good_hits
    if len(must_include) == 0:
        score += 2.0
    else:
        ratio = good_count / max(1, len(must_include))
        if ratio >= 0.67:
            score += 2.0
        elif ratio >= 0.34:
            score += 1.0

    passed = score >= 7.0
    return ScoreResult(score=score, max_score=max_score, passed=passed, details=details)
