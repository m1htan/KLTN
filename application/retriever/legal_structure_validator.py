from typing import Optional

from application.retriever.legal_query_analyzer import analyze_legal_query
from application.knowledge_graph.neo4j_client import Neo4jClient
from application.knowledge_graph import schema as S


def _node_exists(neo4j: Neo4jClient, node_id: str) -> bool:
    cypher = """
    MATCH (n {id: $id})
    RETURN n LIMIT 1
    """
    records = neo4j.run_read(cypher, {"id": node_id})
    return bool(records)


def validate_legal_structure(
    *,
    neo4j: Neo4jClient,
    question: str,
    law_id: Optional[str] = None,
) -> Optional[str]:
    """
    Validate existence of Article / Clause / Point using Knowledge Graph IDs.

    Return:
      - error message (string) if structure does NOT exist
      - None if structure is valid or not enough info to validate
    """

    parts = analyze_legal_query(question)

    article_no = parts.get("article_no")
    clause_no = parts.get("clause_no")
    point = parts.get("point_label")

    # Không có Điều → không validate
    if not article_no:
        return None

    # Nếu không có law_id (user không nêu rõ luật) → không kết luận sai
    if not law_id:
        return None

    # ---------- CHECK ARTICLE ----------
    article_id = S.article_node_id(law_id, article_no)
    if not _node_exists(neo4j, article_id):
        return f"Trong dữ liệu pháp luật hiện có, không tồn tại Điều {article_no} của văn bản này."

    # ---------- CHECK CLAUSE ----------
    if clause_no is not None:
        clause_id = S.clause_node_id(law_id, article_no, clause_no)
        if not _node_exists(neo4j, clause_id):
            return f"Điều {article_no} không có Khoản {clause_no}."

    # ---------- CHECK POINT ----------
    if clause_no is not None and point:
        point_id = S.point_node_id(law_id, article_no, clause_no, point)
        if not _node_exists(neo4j, point_id):
            return f"Khoản {clause_no} Điều {article_no} không có Điểm {point}."

    return None
