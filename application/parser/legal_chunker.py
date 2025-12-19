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

    for art in articles:
        token_count = num_tokens_from_string(art.raw_text)

        law_id = build_law_id(law_info)

        base_meta = {
            # contract
            "schema_version": "law_meta_v1",
            "doc_type": "law",

            # law identity
            "law_id": law_id,
            "law_type": law_info.get("law_type"),
            "law_number": law_info.get("law_number"),
            "law_year": law_info.get("law_year"),
            "law_code": law_info.get("law_code"),

            # structure
            "chapter": art.chapter,
            "chapter_title": art.chapter_title,

            "article_label": f"Điều {art.number}",
            "article_no": int(re.sub(r"\D", "", art.number)),

            # system
            "source_file": source_file,
            "language": "vi",
            "jurisdiction": "VN",

            # preserve upstream
            **law_meta,
        }

        # --- 1 Điều = 1 chunk ---
        if token_count <= MAX_TOKENS_ARTICLE:
            chunks.append(
                Document(
                    text=art.raw_text,
                    extra_info={
                        **base_meta,
                        "chunk_type": "article",
                        "clause_label": None,
                        "clause_no": None,
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
                            "clause_label": f"Khoản {clause.number}",
                            "clause_no": int(clause.number),
                        },
                    )
                )

    return chunks
