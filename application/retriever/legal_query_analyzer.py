import re
from typing import Dict, Optional, Any

_RE_ARTICLE = re.compile(r"(?i)\bđiều\s+(\d+[a-z]?)\b")
_RE_CLAUSE  = re.compile(r"(?i)\bkhoản\s+(\d+)\b")
_RE_POINT   = re.compile(r"(?i)\bđiểm\s+([a-z])\b")
_RE_EXCEPTION = re.compile(r"(?i)\b(trừ|ngoại lệ|không áp dụng)\b")

def _to_int_safe(x: Optional[str]) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(re.sub(r"[^0-9]", "", x))
    except Exception:
        return None

def analyze_legal_query(q: str) -> Dict[str, Any]:
    """
    Parse tối thiểu cho truy vấn pháp luật VN:
      - "Điểm a Khoản 2 Điều 14 ..."
      - "Khoản 2 Điều 14 ..."
      - "Điều 14 ..."
    """
    if not q or not q.strip():
        return {"article_no": None, "clause_no": None, "point_label": None, "ask_exception": False}

    m_a = _RE_ARTICLE.search(q)
    m_c = _RE_CLAUSE.search(q)
    m_p = _RE_POINT.search(q)
    m_e = _RE_EXCEPTION.search(q)

    article_raw = m_a.group(1) if m_a else None
    article_no = _to_int_safe(article_raw)
    clause_no = _to_int_safe(m_c.group(1)) if m_c else None
    point_label = (m_p.group(1).lower() if m_p else None)

    has_structured_ref = bool(article_no or clause_no or point_label)

    return {
        "article_no": article_no,
        "clause_no": clause_no,
        "point_label": point_label,
        "ask_exception": bool(m_e),
        "has_structured_ref": has_structured_ref,
    }
