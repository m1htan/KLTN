from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ReferenceHit:
    """
    A reference mention inside a text, e.g. "theo Điều 35", "khoản 2 Điều 8", ...
    MVP: only normalize to (article_no, clause_no optional, point optional).
    """
    article_no: int
    clause_no: Optional[int] = None
    point_label: Optional[str] = None
    raw: str = ""


# Common VN legal reference patterns
RE_ARTICLE = re.compile(r"\bĐiều\s+(\d+)\b", flags=re.IGNORECASE)
RE_CLAUSE_ARTICLE = re.compile(r"\bkhoản\s+(\d+)\s+Điều\s+(\d+)\b", flags=re.IGNORECASE)
RE_POINT_CLAUSE_ARTICLE = re.compile(
    r"\bđiểm\s+([a-z])\s+khoản\s+(\d+)\s+Điều\s+(\d+)\b",
    flags=re.IGNORECASE
)


def extract_references(text: str) -> List[ReferenceHit]:
    if not text:
        return []

    hits: List[ReferenceHit] = []

    # Most specific first
    for m in RE_POINT_CLAUSE_ARTICLE.finditer(text):
        hits.append(ReferenceHit(
            point_label=m.group(1).lower(),
            clause_no=int(m.group(2)),
            article_no=int(m.group(3)),
            raw=m.group(0)
        ))

    for m in RE_CLAUSE_ARTICLE.finditer(text):
        hits.append(ReferenceHit(
            clause_no=int(m.group(1)),
            article_no=int(m.group(2)),
            raw=m.group(0)
        ))

    # Article-only mentions (avoid duplicates already captured)
    captured_articles = {(h.article_no, h.clause_no, h.point_label) for h in hits}
    for m in RE_ARTICLE.finditer(text):
        key = (int(m.group(1)), None, None)
        if key not in captured_articles:
            hits.append(ReferenceHit(
                article_no=int(m.group(1)),
                raw=m.group(0)
            ))

    return hits
