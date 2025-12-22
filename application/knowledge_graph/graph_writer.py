from __future__ import annotations

from typing import Iterable, Dict, Any
import logging

from application.knowledge_graph.neo4j_client import Neo4jClient
from application.knowledge_graph import schema as S


class GraphWriter:
    """
    Idempotent writer (MERGE-based) for Neo4j.

    Assumption:
    - every node has property `id` as stable unique id.
    """

    def __init__(self, client: Neo4jClient):
        self.client = client

    def ensure_constraints(self) -> None:
        # Neo4j 5 supports `IF NOT EXISTS`
        self.client.run_write(f"CREATE CONSTRAINT law_id IF NOT EXISTS FOR (n:{S.LABEL_LAW}) REQUIRE n.id IS UNIQUE")
        self.client.run_write(f"CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:{S.LABEL_ARTICLE}) REQUIRE n.id IS UNIQUE")
        self.client.run_write(f"CREATE CONSTRAINT clause_id IF NOT EXISTS FOR (n:{S.LABEL_CLAUSE}) REQUIRE n.id IS UNIQUE")
        self.client.run_write(f"CREATE CONSTRAINT point_id IF NOT EXISTS FOR (n:{S.LABEL_POINT}) REQUIRE n.id IS UNIQUE")

    def upsert_nodes(self, label: str, nodes: Iterable[Dict[str, Any]]) -> None:
        cypher = f"""
        UNWIND $rows AS row
        MERGE (n:{label} {{id: row.id}})
        SET n += row.props
        """
        rows = [{"id": n["id"], "props": {k: v for k, v in n.items() if k != "id"}} for n in nodes]
        if rows:
            self.client.run_write(cypher, {"rows": rows})

    def upsert_edges(
            self,
            rel_type: str,
            edges: Iterable[Dict[str, Any]],
            batch_size: int = 2000,
    ) -> None:
        """
        Batch upsert edges, using labels so Neo4j can use label-scoped unique constraints/indexes.
        """

        def _labels_for_rel(rt: str) -> Tuple[str, str]:
            if rt == S.REL_HAS_ARTICLE:
                return S.LABEL_LAW, S.LABEL_ARTICLE
            if rt == S.REL_HAS_CLAUSE:
                return S.LABEL_ARTICLE, S.LABEL_CLAUSE
            if rt == S.REL_HAS_POINT:
                return S.LABEL_CLAUSE, S.LABEL_POINT
            if rt == S.REL_REFERS_TO:
                # from: Article or Clause, to: Article (per current builder)
                return "Article|Clause", S.LABEL_ARTICLE
            if rt == S.REL_EXCEPTION_OF:
                # can be from Article or Clause; to can be Article or Clause (self-loop unresolved)
                return "Article|Clause", "Article|Clause"
            raise ValueError(f"Unknown rel_type: {rt}")

        from_labels, to_labels = _labels_for_rel(rel_type)

        cypher = f"""
        UNWIND $rows AS row
        MATCH (a:{from_labels} {{id: row.from}})
        MATCH (b:{to_labels} {{id: row.to}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += row.props
        """

        rows = []
        for e in edges:
            if "from" not in e or "to" not in e:
                raise ValueError(f"Edge missing 'from' or 'to': {e}")
            rows.append({
                "from": e["from"],
                "to": e["to"],
                "props": e.get("props", {}) or {},
            })

        total = len(rows)
        if total == 0:
            logging.info(f"[GRAPH] upsert_edges {rel_type}: 0 rows (skip)")
            return

        logging.info(f"[GRAPH] upsert_edges {rel_type}: total={total}, batch_size={batch_size}")

        for i in range(0, total, batch_size):
            batch = rows[i: i + batch_size]
            self.client.run_write(cypher, {"rows": batch})
            logging.info(f"[GRAPH] upsert_edges {rel_type}: {i + len(batch)}/{total}")
