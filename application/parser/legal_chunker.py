import os
import re
from typing import List
from application.parser.schema.base import Document
from application.utils import num_tokens_from_string
from application.parser.legal_vn_parser import Article

MAX_TOKENS_ARTICLE = 1200

LAW_FILE_RE = re.compile(
    r"(Luật|Bộ luật)-(\d+)-(\d{4})-(QH\d+)",
    re.IGNORECASE
)

def parse_law_info(source_file: str) -> dict:
    name = os.path.basename(source_file)
    m = LAW_FILE_RE.search(name)
    if not m:
        return {
            "law_type": None,
            "law_number": None,
            "law_year": None,
            "law_code": None,
        }
    return {
        "law_type": m.group(1),
        "law_number": m.group(2),
        "law_year": int(m.group(3)),
        "law_code": m.group(4),
    }

def chunk_articles(
    articles: List[Article],
    law_meta: dict,
    source_file: str,
) -> List[Document]:

    chunks = []
    law_info = parse_law_info(source_file)

    for art in articles:
        token_count = num_tokens_from_string(art.raw_text)

        base_meta = {
            **law_meta,
            **law_info,
            "chapter": art.chapter,
            "chapter_title": art.chapter_title,
            "article": f"Điều {art.number}",
            "article_number": art.number,
            "article_title": art.title,
            "source_file": source_file,
            "language": "vi",
            "jurisdiction": "VN",
        }

        # --- 1 Điều = 1 chunk ---
        if token_count <= MAX_TOKENS_ARTICLE:
            chunks.append(
                Document(
                    text=art.raw_text,
                    extra_info={
                        **base_meta,
                        "chunk_type": "article",
                        "clause": None,
                        "clause_number": None,
                    },
                )
            )
        else:
            # --- fallback theo Khoản ---
            for clause in art.clauses:
                clause_text = (
                    f"{law_info.get('law_type')} số {law_info.get('law_number')}/{law_info.get('law_year')}\n"
                    f"{art.chapter} – {art.chapter_title}\n\n"
                    f"Điều {art.number}. {art.title}\n"
                    f"Khoản {clause.number}.\n"
                    f"{clause.text}"
                )
                chunks.append(
                    Document(
                        text=clause_text,
                        extra_info={
                            **base_meta,
                            "chunk_type": "article_clause",
                            "clause": f"Khoản {clause.number}",
                            "clause_number": clause.number,
                        },
                    )
                )

    return chunks
