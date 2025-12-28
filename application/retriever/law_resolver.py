import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

from application.knowledge_graph.neo4j_client import Neo4jClient, load_neo4j_config_from_env
from application.knowledge_graph import schema as S


@dataclass
class LawResolveResult:
    law_id: Optional[str]
    law_name: Optional[str]
    reason: str


# Alias “thực tế” cho các luật bạn hay gọi bằng tên rút gọn.
# Bạn có thể bổ sung dần, nhưng KHÔNG phải hard-code theo từng luật “ngẫu nhiên”;
# chỉ nên hard-code alias phổ biến như BLHS, BLTTHS, BLDS, ...
LAW_ALIASES = {
    # Bộ luật Hình sự
    "luật hình sự": "vn_law_100_2015_qh13",
    "bộ luật hình sự": "vn_law_100_2015_qh13",
    "blhs": "vn_law_100_2015_qh13",

    # Bạn có thể thêm:
    # "bộ luật tố tụng hình sự": "...",
    # "bltths": "...",
}


def extract_law_phrase(q: str) -> Optional[str]:
    """
    Trích cụm sau 'luật' hoặc 'bộ luật' để dùng match Neo4j.
    Ví dụ: 'điểm a khoản 2 điều 15 luật hình sự' -> 'hình sự'
    """
    if not q:
        return None
    s = q.strip().lower()

    # Ưu tiên match alias đầy đủ trước
    for k in LAW_ALIASES.keys():
        if k in s:
            return k

    # Thử bắt cụm 'bộ luật xxx' hoặc 'luật xxx'
    m = re.search(r"\b(bộ\s+luật|luật)\s+([^\.,;:\n]+)", s, flags=re.IGNORECASE)
    if not m:
        return None

    phrase = (m.group(0) or "").strip().lower()
    # phrase dạng "luật hình sự" hoặc "bộ luật hình sự"
    return phrase


def resolve_law_id(q: str) -> LawResolveResult:
    """
    Resolve law_id bằng:
    1) Alias map
    2) Query Neo4j Law nodes theo law_name/law_number chứa keyword
    """
    phrase = extract_law_phrase(q)
    if not phrase:
        return LawResolveResult(None, None, "no_law_phrase")

    # 1) Alias map (ổn định, đúng thực tế)
    if phrase in LAW_ALIASES:
        return LawResolveResult(LAW_ALIASES[phrase], phrase, "alias")

    # 2) Tìm trong Neo4j Law nodes
    # keyword: bỏ 'luật'/'bộ luật'
    keyword = phrase
    keyword = keyword.replace("bộ luật", "").replace("luật", "").strip()
    if not keyword:
        return LawResolveResult(None, None, "empty_keyword")

    neo = Neo4jClient(load_neo4j_config_from_env())
    try:
        cypher = f"""
        MATCH (l:{S.LABEL_LAW})
        WHERE l.law_name IS NOT NULL AND toLower(l.law_name) CONTAINS $kw
        RETURN l.law_id AS law_id, l.law_name AS law_name
        LIMIT 5
        """
        rows = neo.run_read(cypher, {"kw": keyword})
        if not rows:
            return LawResolveResult(None, None, "neo4j_no_match")

        # Chọn match tốt nhất (ưu tiên law_name chứa keyword dài)
        best = rows[0]
        return LawResolveResult(best.get("law_id"), best.get("law_name"), "neo4j_match")
    finally:
        neo.close()
