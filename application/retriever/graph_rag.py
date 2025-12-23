import logging
import re
from typing import List, Dict, Any

from application.retriever.base import BaseRetriever
from application.vectorstore.vector_creator import VectorCreator
from application.core.settings import settings

from application.knowledge_graph.neo4j_client import (
    Neo4jClient,
    load_neo4j_config_from_env,
)
from application.knowledge_graph import schema as S
from application.utils import num_tokens_from_string

# -------------------------
# QUERY ANALYZER (MVP)
# -------------------------
_RE_ARTICLE = re.compile(r"(?i)\bđiều\s+(\d+)")
_RE_CLAUSE  = re.compile(r"(?i)\bkhoản\s+(\d+)")
_RE_POINT   = re.compile(r"(?i)\bđiểm\s+([a-z])\b")


def analyze_legal_query(q: str) -> Dict[str, Any]:
    """
    MVP parser cho query pháp luật:
    - "Điều 14"
    - "Khoản 2 Điều 14"
    - "Điểm a Khoản 2 Điều 14"
    """
    if not q:
        return {"article_no": None, "clause_no": None, "point_label": None}

    m_a = _RE_ARTICLE.search(q)
    m_c = _RE_CLAUSE.search(q)
    m_p = _RE_POINT.search(q)

    return {
        "article_no": int(m_a.group(1)) if m_a else None,
        "clause_no": int(m_c.group(1)) if m_c else None,
        "point_label": m_p.group(1).lower() if m_p else None,
    }


class GraphRAG(BaseRetriever):
    """
    Graph-first RAG:
    1. Parse question → article_no / clause_no / point
    2. Query Neo4j to resolve structure
    3. Fetch ARTICLE text from vector store
    4. Return context (Article + relevant clauses/points)
    """

    def __init__(
        self,
        source,
        chat_history=None,
        prompt="",
        chunks=2,
        doc_token_limit=50000,
        **kwargs,
    ):
        self.question = source.get("question", "")
        self.doc_token_limit = doc_token_limit
        self.chunks = chunks

        if "active_docs" in source and source["active_docs"]:
            self.vectorstores = (
                source["active_docs"]
                if isinstance(source["active_docs"], list)
                else [source["active_docs"]]
            )
        else:
            self.vectorstores = []

        self.neo4j = Neo4jClient(load_neo4j_config_from_env())

    # -------------------------
    # MAIN ENTRY
    # -------------------------
    def close(self) -> None:
        if getattr(self, "neo4j", None):
            self.neo4j.close()

    def search(self, query: str = "") -> List[Dict[str, Any]]:
        q = query or self.question
        analysis = analyze_legal_query(q)

        if not analysis["article_no"]:
            logging.info("[GraphRAG] No article detected → return empty")
            return []

        try:
            graph_hits = self._query_graph(analysis)
            if not graph_hits:
                logging.info("[GraphRAG] Graph returned 0 nodes")
                return []
            return self._fetch_articles_from_vector(graph_hits)
        finally:
            self.close()

    # -------------------------
    # GRAPH QUERY
    # -------------------------
    def _query_graph(self, analysis: dict) -> List[dict]:
        """
        Resolve Article / Clause / Point via Neo4j
        """
        article_no = analysis["article_no"]
        clause_no = analysis.get("clause_no")

        cypher = """
        MATCH (a:Article)
        WHERE a.article_no = $article_no
        OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(c:Clause)
        WHERE $clause_no IS NULL OR c.clause_no = $clause_no
        OPTIONAL MATCH (c)-[:HAS_POINT]->(p:Point)
        WHERE $point_label IS NULL OR p.point_label = $point_label
        RETURN a.id AS article_id,
               a.law_id AS law_id,
               a.article_no AS article_no,
               collect(DISTINCT c.clause_no) AS clauses,
               collect(DISTINCT p.point_label) AS points
        """

        rows = self.neo4j.run_read(
            cypher,
            {
                "article_no": article_no,
                "clause_no": clause_no,
            },
        )

        return [r.data() for r in rows]

    # -------------------------
    # VECTOR FETCH
    # -------------------------
    def _fetch_articles_from_vector(self, graph_hits: List[dict]) -> List[Dict[str, Any]]:
        """
        Fetch ARTICLE text only (vectorized level)
        """
        if not self.vectorstores:
            return []

        results = []
        token_budget = int(self.doc_token_limit * 0.9)
        used = 0

        for vs_id in self.vectorstores:
            store = VectorCreator.create_vectorstore(
                settings.VECTOR_STORE,
                vs_id,
                settings.EMBEDDINGS_KEY,
            )

            for hit in graph_hits:
                f = {
                    "doc_type": "law",
                    "chunk_type": "article",
                    "law_id": hit["law_id"],
                    "article_no": hit["article_no"],
                }

                docs = store.similarity_search(
                    f"Điều {hit['article_no']}",
                    k=1,
                    filter=f,
                )

                for d in docs:
                    tokens = num_tokens_from_string(d.page_content)
                    if used + tokens > token_budget:
                        break

                    results.append(
                        {
                            "title": f"Điều {hit['article_no']}",
                            "text": d.page_content,
                            "source": d.metadata.get("source_file"),
                            "metadata": {
                                **d.metadata,
                                "graph_clauses": hit.get("clauses"),
                                "graph_points": hit.get("points"),
                            },
                        }
                    )
                    used += tokens

        return results
