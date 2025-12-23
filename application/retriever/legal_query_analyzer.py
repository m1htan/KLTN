import re
from typing import Dict, Optional

_RE_LAW = re.compile(r"(luật|bộ luật)\s+([^\d,\n]+)", re.IGNORECASE)
_RE_ARTICLE = re.compile(r"điều\s+(\d+[a-z]?)", re.IGNORECASE)
_RE_CLAUSE = re.compile(r"khoản\s+(\d+)", re.IGNORECASE)
_RE_POINT = re.compile(r"điểm\s+([a-z])", re.IGNORECASE)
_RE_EXCEPTION = re.compile(r"(trừ|ngoại lệ|không áp dụng)", re.IGNORECASE)


def analyze_legal_query(q: str) -> Dict[str, Optional[str]]:
    if not q:
        return {}

    m_law = _RE_LAW.search(q)
    m_a = _RE_ARTICLE.search(q)
    m_c = _RE_CLAUSE.search(q)
    m_p = _RE_POINT.search(q)
    m_e = _RE_EXCEPTION.search(q)

    return {
        "law_hint": m_law.group(2).strip() if m_law else None,
        "article_no": int(m_a.group(1)) if m_a else None,
        "clause_no": int(m_c.group(1)) if m_c else None,
        "point_label": m_p.group(1).lower() if m_p else None,
        "ask_exception": bool(m_e),
    }
