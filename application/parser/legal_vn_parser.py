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
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]

    articles: List[Article] = []

    current_chapter = None
    current_chapter_title = None

    current_article = None
    current_clauses: List[Clause] = []
    current_clause: Clause | None = None

    article_buffer = []

    def flush_article():
        if current_article:
            articles.append(
                Article(
                    number=current_article["number"],
                    title=current_article["title"],
                    chapter=current_chapter,
                    chapter_title=current_chapter_title,
                    clauses=current_clauses,
                    raw_text="\n".join(article_buffer),
                )
            )

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
            flush_article()

            current_article = {
                "number": m_article.group(1),
                "title": m_article.group(2),
            }
            current_clauses = []
            current_clause = None
            article_buffer = [line]
            i += 1
            continue

        # --- KHOẢN ---
        m_clause = CLAUSE_RE.match(line)
        if m_clause and current_article:
            current_clause = Clause(
                number=m_clause.group(1),
                text=m_clause.group(2),
                points=[]
            )
            current_clauses.append(current_clause)
            article_buffer.append(line)
            i += 1
            continue

        # --- ĐIỂM ---
        m_point = POINT_RE.match(line)
        if m_point and current_clause:
            point = Point(
                letter=m_point.group(1),
                text=m_point.group(2)
            )
            current_clause.points.append(point)
            # gộp luôn vào text khoản
            current_clause.text += f"\n{point.letter}) {point.text}"
            article_buffer.append(line)
            i += 1
            continue

        # --- DÒNG KÉO DÀI CỦA KHOẢN ---
        if current_clause:
            current_clause.text += f"\n{line}"
            article_buffer.append(line)
            i += 1
            continue

        # --- TEXT THƯỜNG ---
        if current_article:
            article_buffer.append(line)

        i += 1

    flush_article()
    return articles
