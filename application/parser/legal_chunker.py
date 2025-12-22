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

def build_law_id(law_info: dict) -> str | None:
    if not law_info.get("law_number") or not law_info.get("law_year") or not law_info.get("law_code"):
        return None
    return f"luat_{law_info['law_number']}_{law_info['law_year']}_{law_info['law_code'].lower()}"

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
    law_id = build_law_id(law_info)

    for art in articles:
        token_count = num_tokens_from_string(art.raw_text)

        base_meta = {
            "schema_version": "law_meta_v1",
            "doc_type": "law",

            "law_id": law_id,
            "law_type": law_info.get("law_type"),
            "law_number": law_info.get("law_number"),
            "law_year": law_info.get("law_year"),
            "law_code": law_info.get("law_code"),

            "chapter": art.chapter,
            "chapter_title": art.chapter_title,

            "article_label": f"Điều {art.number}",
            "article_no": int(re.sub(r"\D", "", art.number)),

            "source_file": source_file,
            "language": "vi",
            "jurisdiction": "VN",

            **law_meta,
        }

        # ===============================
        # 1. ARTICLE – vector + graph
        # ===============================
        chunks.append(
            Document(
                text=art.raw_text,
                extra_info={
                    **base_meta,
                    "chunk_type": "article",
                    "for_vector": True,
                    "for_graph": True,
                    "clause_label": None,
                    "clause_no": None,
                    "point_label": None,
                },
            )
        )

        # ===============================
        # 2. CLAUSE – graph only
        # ===============================
        for clause in art.clauses:
            clause_meta = {
                **base_meta,
                "chunk_type": "clause",
                "for_vector": False,
                "for_graph": True,
                "clause_label": f"Khoản {clause.number}",
                "clause_no": int(clause.number),
                "point_label": None,
            }

            chunks.append(
                Document(
                    text=clause.text,
                    extra_info=clause_meta,
                )
            )

            # ===============================
            # 3. POINT – graph only
            # ===============================
            for point in getattr(clause, "points", []):
                chunks.append(
                    Document(
                        text=point.text,
                        extra_info={
                            **clause_meta,
                            "chunk_type": "point",
                            "point_label": point.letter
                        },
                    )
                )

    return chunks
