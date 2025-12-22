from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from application.knowledge_graph import schema as S
from application.knowledge_graph.extractors.reference import extract_references
from application.knowledge_graph.extractors.exception import extract_exception_cues


# Detect "point" lines inside a clause text.
# Common formats:
#   a) ...
#   b) ...
#   a. ...
#   b. ...
RE_POINT_LINE = re.compile(r"(?mi)^\s*([a-z])\s*[\)\.]\s+(.*)$")


@dataclass
class BuildResult:
    laws: List[Dict[str, Any]]
    articles: List[Dict[str, Any]]
    clauses: List[Dict[str, Any]]
    points: List[Dict[str, Any]]
    edges_has_article: List[Dict[str, Any]]
    edges_has_clause: List[Dict[str, Any]]
    edges_has_point: List[Dict[str, Any]]
    edges_refers_to: List[Dict[str, Any]]
    edges_exception_of: List[Dict[str, Any]]


class LegalGraphBuilder:
    """
    Build graph MVP from a list of docs/chunks (LangChain Document-like dicts).

    Expected minimum metadata (based on what bạn đã in ra từ FAISS):
    - doc_type='law'
    - law_id
    - article_no
    - clause_no (optional)
    - source_file / source
    - chunk_type: 'article' or 'article_clause' (optional)
    """

    def build_from_retrieved_docs(self, docs: List[Dict[str, Any]]) -> BuildResult:
        laws: Dict[str, Dict[str, Any]] = {}
        articles: Dict[str, Dict[str, Any]] = {}
        clauses: Dict[str, Dict[str, Any]] = {}
        points: Dict[str, Dict[str, Any]] = {}

        edges_has_article: List[Dict[str, Any]] = []
        edges_has_clause: List[Dict[str, Any]] = []
        edges_has_point: List[Dict[str, Any]] = []
        edges_refers_to: List[Dict[str, Any]] = []
        edges_exception_of: List[Dict[str, Any]] = []

        for d in docs:
            meta = (d.get("metadata") or {})
            text = d.get("text") or ""

            if meta.get("doc_type") != "law":
                continue

            law_id = meta.get("law_id")
            article_no = meta.get("article_no")
            clause_no = meta.get("clause_no")

            if not law_id or not article_no:
                # Skip if not enough info to anchor structure
                continue

            law_node = self._ensure_law(laws, meta)
            article_node = self._ensure_article(articles, meta, text=text if (meta.get("chunk_type") == "article") else None)

            edges_has_article.append({
                "from": law_node["id"],
                "to": article_node["id"],
                "props": {}
            })

            # Clause node if clause_no exists
            clause_node_id: Optional[str] = None
            if isinstance(clause_no, int):
                clause_node = self._ensure_clause(clauses, meta, text=text if (meta.get("chunk_type") == "article_clause") else None)
                clause_node_id = clause_node["id"]
                edges_has_clause.append({
                    "from": article_node["id"],
                    "to": clause_node["id"],
                    "props": {}
                })

                # Extract points inside clause text (node-level, không chunk)
                for p_label, p_text in self._extract_points_from_text(text):
                    p_node = self._ensure_point(points, meta, point_label=p_label, text=p_text)
                    edges_has_point.append({
                        "from": clause_node["id"],
                        "to": p_node["id"],
                        "props": {}
                    })

            # REFERS_TO edges (from current node -> referenced Article/Clause/Point as available in MVP)
            # MVP resolution:
            # - If text says "Điều X": link current node -> Article(X) (same law unknown: keep cross-law unresolved now)
            current_from_id = clause_node_id or article_node["id"]
            for ref in extract_references(text):
                # MVP: assume same law_id when linking
                ref_article_id = S.article_node_id(law_id, ref.article_no)
                edges_refers_to.append({
                    "from": current_from_id,
                    "to": ref_article_id,
                    "props": {
                        "raw": ref.raw,
                        "ref_article_no": ref.article_no,
                        "ref_clause_no": ref.clause_no,
                        "ref_point": ref.point_label,
                    }
                })

            # EXCEPTION cues (attach as relationship to referenced node if possible; else self-mark)
            # MVP logic:
            # - If exception cue exists and there is a reference hit => EXCEPTION_OF current -> referenced Article
            # - Else: attach property on current node via relationship to itself (still queryable)
            cues = extract_exception_cues(text)
            if cues:
                refs = extract_references(text)
                if refs:
                    for ref in refs:
                        edges_exception_of.append({
                            "from": current_from_id,
                            "to": S.article_node_id(law_id, ref.article_no),
                            "props": {
                                "cue": cues[0].cue,
                                "raw": cues[0].raw,
                            }
                        })
                else:
                    edges_exception_of.append({
                        "from": current_from_id,
                        "to": current_from_id,
                        "props": {
                            "cue": cues[0].cue,
                            "raw": cues[0].raw,
                            "note": "unresolved_target"
                        }
                    })

        return BuildResult(
            laws=list(laws.values()),
            articles=list(articles.values()),
            clauses=list(clauses.values()),
            points=list(points.values()),
            edges_has_article=edges_has_article,
            edges_has_clause=edges_has_clause,
            edges_has_point=edges_has_point,
            edges_refers_to=edges_refers_to,
            edges_exception_of=edges_exception_of,
        )

    def _ensure_law(self, laws: Dict[str, Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
        law_id = meta["law_id"]
        nid = S.law_node_id(law_id)
        if nid in laws:
            return laws[nid]
        laws[nid] = {
            "id": nid,
            "law_id": law_id,
            "law_type": meta.get("law_type"),
            "law_number": meta.get("law_number"),
            "law_year": meta.get("law_year"),
            "law_code": meta.get("law_code"),
            "source_file": meta.get("source_file") or meta.get("source"),
            "jurisdiction": meta.get("jurisdiction"),
            "language": meta.get("language"),
        }
        return laws[nid]

    def _ensure_article(self, articles: Dict[str, Dict[str, Any]], meta: Dict[str, Any], text: Optional[str]) -> Dict[str, Any]:
        law_id = meta["law_id"]
        article_no = int(meta["article_no"])
        nid = S.article_node_id(law_id, article_no)
        if nid in articles:
            # Only fill text if missing and new text is provided
            if text and not articles[nid].get("text"):
                articles[nid]["text"] = text
            return articles[nid]

        articles[nid] = {
            "id": nid,
            "law_id": law_id,
            "article_no": article_no,
            "article_label": meta.get("article_label"),
            "chapter": meta.get("chapter"),
            "chapter_title": meta.get("chapter_title"),
            "source_file": meta.get("source_file") or meta.get("source"),
            "text": text,
        }
        return articles[nid]

    def _ensure_clause(self, clauses: Dict[str, Dict[str, Any]], meta: Dict[str, Any], text: Optional[str]) -> Dict[str, Any]:
        law_id = meta["law_id"]
        article_no = int(meta["article_no"])
        clause_no = int(meta["clause_no"])
        nid = S.clause_node_id(law_id, article_no, clause_no)
        if nid in clauses:
            if text and not clauses[nid].get("text"):
                clauses[nid]["text"] = text
            return clauses[nid]
        clauses[nid] = {
            "id": nid,
            "law_id": law_id,
            "article_no": article_no,
            "clause_no": clause_no,
            "clause_label": meta.get("clause_label"),
            "text": text,
        }
        return clauses[nid]

    def _ensure_point(
        self,
        points: Dict[str, Dict[str, Any]],
        meta: Dict[str, Any],
        point_label: str,
        text: Optional[str],
    ) -> Dict[str, Any]:
        law_id = meta["law_id"]
        article_no = int(meta["article_no"])
        clause_no = int(meta["clause_no"])
        nid = S.point_node_id(law_id, article_no, clause_no, point_label)
        if nid in points:
            if text and not points[nid].get("text"):
                points[nid]["text"] = text
            return points[nid]

        points[nid] = {
            "id": nid,
            "law_id": law_id,
            "article_no": article_no,
            "clause_no": clause_no,
            "point_label": point_label.lower(),
            "text": text,
        }
        return points[nid]

    def _extract_points_from_text(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract point lines inside clause text without turning them into vector chunks.
        Returns list of (point_label, point_text).
        """
        if not text:
            return []
        hits = []
        for m in RE_POINT_LINE.finditer(text):
            label = m.group(1).lower()
            ptext = (m.group(2) or "").strip()
            if label and ptext:
                hits.append((label, ptext))
        return hits
