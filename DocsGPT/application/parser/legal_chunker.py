from typing import List
from application.parser.schema.base import Document
from application.utils import num_tokens_from_string
from application.parser.legal_vn_parser import Article


MAX_TOKENS_ARTICLE = 1200


def chunk_articles(
    articles: List[Article],
    law_meta: dict,
    source_file: str,
) -> List[Document]:

    chunks = []

    for art in articles:
        token_count = num_tokens_from_string(art.raw_text)

        base_meta = {
            **law_meta,
            "chapter": art.chapter,
            "chapter_title": art.chapter_title,
            "article": f"Điều {art.number}",
            "article_title": art.title,
            "parent_article_id": f"{law_meta['law_number']}-D{art.number}",
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
                    },
                )
            )
        else:
            # --- fallback theo Khoản ---
            for clause in art.clauses:
                clause_text = f"Điều {art.number}. {art.title}\n{clause.number}. {clause.text}"
                chunks.append(
                    Document(
                        text=clause_text,
                        extra_info={
                            **base_meta,
                            "chunk_type": "article_clause",
                            "clause": f"Khoản {clause.number}",
                        },
                    )
                )

    return chunks
