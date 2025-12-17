import re
from dataclasses import dataclass
from typing import List


@dataclass
class Point:
    letter: str
    text: str

@dataclass
class Clause:
    number: str
    text: str
    points: List[Point]

@dataclass
class Article:
    number: str
    title: str
    chapter: str
    chapter_title: str
    clauses: List[Clause]
    raw_text: str

CHAPTER_RE = re.compile(r"^Chương\s+[IVXLC]+$", re.IGNORECASE)
ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-zA-Z]?)\.\s*(.+)$")
CLAUSE_RE  = re.compile(r"^\s*(\d+)\.\s+(.+)")
POINT_RE = re.compile(r"^\s*([a-z])\)\s+(.+)")


def parse_law_text(text: str) -> List[Article]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    articles: List[Article] = []

    current_chapter = None
    current_chapter_title = None
    current_article = None
    current_clauses: List[Clause] = []
    buffer = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # --- CHƯƠNG ---
        if CHAPTER_RE.match(line):
            current_chapter = line
            current_chapter_title = lines[i + 1] if i + 1 < len(lines) else ""
            i += 2
            continue

        # --- ĐIỀU ---
        m_article = ARTICLE_RE.match(line)
        if m_article:
            # flush article cũ
            if current_article:
                articles.append(
                    Article(
                        number=current_article["number"],
                        title=current_article["title"],
                        chapter=current_chapter,
                        chapter_title=current_chapter_title,
                        clauses=current_clauses,
                        raw_text="\n".join(buffer),
                    )
                )

            current_article = {
                "number": m_article.group(1),
                "title": m_article.group(2),
            }
            current_clauses = []
            buffer = [line]
            i += 1
            continue

        # --- KHOẢN ---
        m_clause = CLAUSE_RE.match(line)
        if m_clause and current_article:
            clause_no = m_clause.group(1)
            clause_text = m_clause.group(2)
            current_clauses.append(
                Clause(
                    number=clause_no,
                    text=clause_text,
                    points=[]
                )
            )

            buffer.append(line)
            i += 1
            continue

        m_point = POINT_RE.match(line)
        if m_point and current_clauses:
            current_clauses[-1].points.append(
                Point(
                    letter=m_point.group(1),
                    text=m_point.group(2)
                )
            )
            buffer.append(line)
            i += 1
            continue

        # --- TEXT THƯỜNG ---
        if current_article:
            buffer.append(line)

        i += 1

    # flush cuối
    if current_article:
        articles.append(
            Article(
                number=current_article["number"],
                title=current_article["title"],
                chapter=current_chapter,
                chapter_title=current_chapter_title,
                clauses=current_clauses,
                raw_text="\n".join(buffer),
            )
        )

    return articles