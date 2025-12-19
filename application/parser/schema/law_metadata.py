from typing import Optional, Literal, Dict, Any
import re

LAW_SCHEMA_VERSION = "law_meta_v1"


def normalize_law_id(law_number: str) -> str:
    """
    45/2019/QH14 -> vn_law_45_2019_qh14
    """
    s = law_number.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return f"vn_law_{s}".strip("_")


def normalize_law_metadata(
    raw_meta: Dict[str, Any],
    *,
    law_name: str,
    law_number: str,
    law_year: int,
    unit_type: Literal["article", "clause"],
    article_no: int,
    clause_no: Optional[int] = None,
    point: Optional[str] = None,
    source_file: Optional[str] = None,
    source_path: Optional[str] = None,
    ingest_pipeline: str = "upload",
) -> Dict[str, Any]:
    """
    Enforce metadata contract law_meta_v1
    """

    meta: Dict[str, Any] = {}

    # ===== Contract =====
    meta["schema_version"] = LAW_SCHEMA_VERSION
    meta["doc_type"] = "law"

    # ===== Law identity =====
    meta["law_name"] = law_name
    meta["law_number"] = law_number
    meta["law_year"] = int(law_year)
    meta["law_id"] = normalize_law_id(law_number)

    # ===== Hierarchy =====
    meta["unit_type"] = unit_type
    meta["article_no"] = int(article_no)

    if unit_type == "clause":
        if clause_no is None:
            raise ValueError("clause_no is required when unit_type='clause'")
        meta["clause_no"] = int(clause_no)

    if point:
        meta["point"] = str(point).lower()

    # ===== Provenance =====
    meta["source_file"] = source_file
    meta["source_path"] = source_path
    meta["ingest_pipeline"] = ingest_pipeline

    # ===== Noise control =====
    meta["text_scope"] = "normative"
    meta["is_boilerplate"] = False

    # ===== Preserve allowed legacy fields =====
    # (tránh làm gãy code khác)
    for k in ("source", "source_id"):
        if k in raw_meta:
            meta[k] = raw_meta[k]

    return meta
