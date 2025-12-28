import logging
from typing import List, Dict, Any, Optional

from application.retriever.base import BaseRetriever
from application.vectorstore.vector_creator import VectorCreator
from application.core.settings import settings

from application.knowledge_graph.neo4j_client import (
    Neo4jClient,
    load_neo4j_config_from_env,
)
from application.utils import num_tokens_from_string
from application.retriever.legal_query_analyzer import analyze_legal_query


class GraphRAG(BaseRetriever):
    def __init__(
            self,
            source,
            chat_history=None,
            prompt="",
            chunks=2,
            doc_token_limit=50000,
            model_id="docsgpt-local",
            user_api_key=None,
            llm_name=settings.LLM_PROVIDER,
            api_key=settings.API_KEY,
            decoded_token=None,
    ):

        # ---- copy contract từ ClassicRAG ----
        self.original_question = source.get("question", "")
        self.chat_history = chat_history if chat_history is not None else []
        self.prompt = prompt
        self.chunks = int(chunks) if isinstance(chunks, (int, str)) else 2
        self.doc_token_limit = doc_token_limit

        self.model_id = model_id
        self.user_api_key = user_api_key
        self.llm_name = llm_name
        self.api_key = api_key
        self.decoded_token = decoded_token

        if "active_docs" in source and source["active_docs"] is not None:
            self.vectorstores = (
                source["active_docs"]
                if isinstance(source["active_docs"], list)
                else [source["active_docs"]]
            )
        else:
            self.vectorstores = []

        self.question = self.original_question

        # ---- Neo4j ----
        self.neo4j = Neo4jClient(load_neo4j_config_from_env())

    def close(self) -> None:
        try:
            if getattr(self, "neo4j", None):
                self.neo4j.close()
        except Exception:
            pass

    def _query_graph_clause_first(self, query: str) -> list[dict]:
        """
        Clause-first graph retrieval (chuẩn cho luật VN)

        Flow:
        - Parse query → clause_no / article_no / point_label
        - Ưu tiên match Clause
        - Resolve lên Article
        - Lấy Point nếu có
        """

        q = self._normalize_query(query)
        analysis = analyze_legal_query(q)

        clause_no = analysis.get("clause_no")
        article_no = analysis.get("article_no")
        point_label = analysis.get("point_label")

        # ===== Case 1: Có Khoản → Clause-first =====
        if clause_no is not None:
            # ⚠️ QUAN TRỌNG: Cần match cả Article để không lấy nhầm Khoản của Điều khác
            cypher = """
            MATCH (a:Article)-[:HAS_CLAUSE]->(c:Clause {clause_no: $clause_no})
            WHERE ($article_no IS NULL OR a.article_no = $article_no)

            OPTIONAL MATCH (c)-[:HAS_POINT]->(p:Point)
            WHERE $point_label IS NULL OR p.point_label = $point_label

            RETURN
                a,
                c,
                collect(DISTINCT p) AS points

            """

            rows = self.neo4j.run_read(
                cypher,
                {
                    "article_no": article_no,  # Đã thêm tham số này
                    "clause_no": clause_no,
                    "point_label": point_label,
                },
            )
            return [r.data() for r in rows]

        # ===== Case 2: Không có Khoản → fallback Article =====
        if article_no is not None:
            cypher = """
            MATCH (a:Article {article_no: $article_no})
            OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(c:Clause)
            OPTIONAL MATCH (c)-[:HAS_POINT]->(p:Point)
            RETURN
                a,
                collect(DISTINCT c) AS clauses,
                collect(DISTINCT p) AS points
            """

            rows = self.neo4j.run_read(
                cypher,
                {"article_no": article_no},
            )
            return [r.data() for r in rows]

        return []

    def _normalize_query(self, query) -> str:
        """
        Normalize query input to string for legal analysis.
        """
        if query is None:
            return ""
        if isinstance(query, str):
            return query
        if isinstance(query, dict):
            # ưu tiên question nếu có
            return (
                    query.get("question")
                    or query.get("original_question")
                    or ""
            )
        return str(query)

    # -------------------------
    # MAIN ENTRY
    # -------------------------
    def search(self, query: str = "") -> List[Dict[str, Any]]:
        qtext = query or self.question
        analysis = analyze_legal_query(qtext)

        if not analysis.get("article_no"):
            logging.info("[GraphRAG] No article detected → return empty")
            return []

        # 1) Clause-first graph retrieval: truyền STRING query, không truyền dict
        graph_hits = self._query_graph_clause_first(qtext)

        # 2) Nếu Graph không có dữ liệu -> Fallback Vector
        if not graph_hits:
            logging.info("[GraphRAG] Graph returned 0 nodes → fallback vector")
            return self._fallback_vector_only(analysis)

        # 3) Tổng hợp context từ Graph
        context = self._assemble_context(analysis, graph_hits)

        # 4) (Tuỳ chọn) Kèm article text từ Vector
        article_text = self._fetch_article_text_from_vector(analysis)
        if article_text:
            context = f"{article_text}\n\n---\n\n{context}"

        return [{
            "title": self._make_title(analysis),
            "text": context,
            "source": "neo4j",
            "metadata": {
                "doc_type": "law",
                "chunk_type": "graph_context",
                "article_no": analysis.get("article_no"),
                "clause_no": analysis.get("clause_no"),
                "point_label": analysis.get("point_label"),
            }
        }]

    # -------------------------
    # GRAPH QUERY (CLAUSE-FIRST)
    # -------------------------
    def _query_graph(self, analysis: dict) -> list[dict]:
        if not analysis.get("clause_no"):
            return []

        cypher = """
        MATCH (c:Clause)
        WHERE c.clause_no = $clause_no
        MATCH (a:Article)-[:HAS_CLAUSE]->(c)
        OPTIONAL MATCH (c)-[:HAS_POINT]->(p:Point)
        RETURN
            a.law_id AS law_id,
            a.article_no AS article_no,
            c.clause_no AS clause_no,
            collect(DISTINCT p.point_label) AS points
        """
        rows = self.neo4j.run_read(
            cypher,
            {"clause_no": analysis["clause_no"]},
        )
        return [r.data() for r in rows]

    # -------------------------
    # CONTEXT ASSEMBLY
    # -------------------------
    def _make_title(self, q: dict) -> str:
        t = f"Điều {q.get('article_no')}"
        if q.get("clause_no") is not None:
            t = f"Khoản {q.get('clause_no')} {t}"
        if q.get("point_label"):
            t = f"Điểm {q.get('point_label')} {t}"
        return t

    def _assemble_context(self, q: dict, hits: List[dict]) -> str:
        out: List[str] = []

        for h in hits:
            a = h.get("a")
            if not a:
                continue

            # ===== Article =====
            out.append(f"[ARTICLE] Điều {a.get('article_no')}")
            if a.get("text"):
                out.append(a["text"].strip())

            # ===== Clause-first =====
            c = h.get("c")
            if c:
                out.append(f"[CLAUSE] Khoản {c.get('clause_no')}")
                if c.get("text"):
                    out.append(c["text"].strip())

                points = h.get("points") or []
                if points:
                    out.append("[POINTS]")
                    for p in points:
                        if not p:
                            continue
                        label = p.get("point_label")
                        text = (p.get("text") or "").strip()
                        if label and text:
                            out.append(f"- Điểm {label}: {text}")

            # ===== Article-only =====
            else:
                clauses = h.get("clauses") or []
                if clauses:
                    out.append("[CLAUSES]")
                    for cc in clauses:
                        if not cc:
                            continue
                        out.append(f"- Khoản {cc.get('clause_no')}: {(cc.get('text') or '').strip()}")

        return "\n".join(x for x in out if x.strip())

    # -------------------------
    # VECTOR SUPPORT (OPTIONAL)
    # -------------------------
    def _fetch_article_text_from_vector(self, q: dict) -> Optional[str]:
        """
        Lấy full text Điều từ vector (k=1). Chỉ dùng để bổ sung context.
        """
        if not self.vectorstores:
            return None

        article_no = q.get("article_no")
        if not article_no:
            return None

        token_budget = int(self.doc_token_limit * 0.5)
        for vs_id in self.vectorstores:
            store = VectorCreator.create_vectorstore(
                settings.VECTOR_STORE,
                vs_id,
                settings.EMBEDDINGS_KEY,
            )

            f = {
                "doc_type": "law",
                "chunk_type": "article",
                "article_no": article_no,
            }

            docs = store.search(f"Điều {article_no}", k=1, filter=f)
            for d in docs:
                txt = d.page_content or ""
                if num_tokens_from_string(txt) <= token_budget:
                    return f"[ARTICLE_TEXT]\n{txt.strip()}"
        return None

    def _fallback_vector_only(self, q: dict) -> List[Dict[str, Any]]:
        """
        Fallback trong trường hợp graph không có node (tránh trả rỗng).
        """
        if not self.vectorstores:
            return []
        article_no = q.get("article_no")
        if not article_no:
            return []

        results: List[Dict[str, Any]] = []
        for vs_id in self.vectorstores:
            store = VectorCreator.create_vectorstore(
                settings.VECTOR_STORE,
                vs_id,
                settings.EMBEDDINGS_KEY,
            )
            f = {"doc_type": "law", "chunk_type": "article", "article_no": article_no}
            docs = store.search(f"Điều {article_no}", k=1, filter=f)
            for d in docs:
                results.append({
                    "title": f"Điều {article_no}",
                    "text": (d.page_content or ""),
                    "source": d.metadata.get("source_file") or d.metadata.get("source"),
                    "metadata": d.metadata,
                })
        return results