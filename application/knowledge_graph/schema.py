from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------
# Node Labels
# ---------------------------

LABEL_LAW = "Law"
LABEL_ARTICLE = "Article"
LABEL_CLAUSE = "Clause"
LABEL_POINT = "Point"


# ---------------------------
# Relationship Types
# ---------------------------

REL_HAS_ARTICLE = "HAS_ARTICLE"
REL_HAS_CLAUSE = "HAS_CLAUSE"
REL_HAS_POINT = "HAS_POINT"
REL_REFERS_TO = "REFERS_TO"
REL_EXCEPTION_OF = "EXCEPTION_OF"


# ---------------------------
# Stable ID helpers
# ---------------------------

def law_node_id(law_id: str) -> str:
    return f"law::{law_id}"


def article_node_id(law_id: str, article_no: int) -> str:
    return f"article::{law_id}::{article_no}"


def clause_node_id(law_id: str, article_no: int, clause_no: int) -> str:
    return f"clause::{law_id}::{article_no}::{clause_no}"


def point_node_id(law_id: str, article_no: int, clause_no: int, point_label: str) -> str:
    p = (point_label or "").strip().lower()
    return f"point::{law_id}::{article_no}::{clause_no}::{p}"


# ---------------------------
# DTOs (optional, for clarity)
# ---------------------------

@dataclass
class LawDTO:
    law_id: str
    law_type: Optional[str] = None
    law_number: Optional[str] = None
    law_year: Optional[int] = None
    law_code: Optional[str] = None
    title: Optional[str] = None
    source_file: Optional[str] = None
    jurisdiction: Optional[str] = "VN"
    language: Optional[str] = "vi"


@dataclass
class ArticleDTO:
    law_id: str
    article_no: int
    article_label: Optional[str] = None
    chapter: Optional[str] = None
    chapter_title: Optional[str] = None
    text: Optional[str] = None
    source_file: Optional[str] = None


@dataclass
class ClauseDTO:
    law_id: str
    article_no: int
    clause_no: int
    clause_label: Optional[str] = None
    text: Optional[str] = None


@dataclass
class PointDTO:
    law_id: str
    article_no: int
    clause_no: int
    point_label: str  # a, b, c...
    text: Optional[str] = None
