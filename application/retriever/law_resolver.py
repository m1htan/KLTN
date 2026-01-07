from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

def _default_metadata_path() -> Path:
    """
    Ưu tiên:
    1) ENV METADATA_CSV (cho Docker)
    2) <repo_root>/data/metadata.csv (chạy trong container /app)
    3) fallback: working dir hiện tại
    """
    env = os.getenv("METADATA_CSV")
    if env:
        return Path(env)

    repo_root = Path(__file__).resolve().parents[2]  # application/.. -> repo root
    p = repo_root / "data" / "metadata.csv"
    return p


METADATA_CSV = _default_metadata_path()


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _norm_text(s: str) -> str:
    s = _strip_accents(s or "").lower().strip()
    # giữ chữ và số, thay phần còn lại bằng space
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_text(s: str) -> str:
    return _norm_text(s)

def _norm_so_hieu(so_hieu: str) -> str:
    # ví dụ: 59/2020/QH14 -> 59/2020/QH14 (uppercase, gọn)
    s = (so_hieu or "").strip().upper()
    s = re.sub(r"\s+", "", s)
    return s


def _law_id_from_file_name(file_name: str) -> str:
    """
    file_name: 'Luật-59-2020-QH14' -> 'luat_59_2020_qh14'
              'Bộ luật-100-2015-QH13' -> 'bo_luat_100_2015_qh13'
    """
    s = (file_name or "").strip()
    s_norm = _norm_text(s).replace(" ", "_")  # 'luat_59_2020_qh14'
    return s_norm


@dataclass(frozen=True)
class LawMeta:
    file_name: str
    law_name: str
    so_hieu: str
    law_id: str
    sua_doi_bo_sung: str

    @property
    def law_name_norm(self) -> str:
        return _norm_text(self.law_name)

    @property
    def file_name_norm(self) -> str:
        return _norm_text(self.file_name)

    @property
    def so_hieu_norm(self) -> str:
        return _norm_so_hieu(self.so_hieu)

class MetadataLawIndex:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.items: list[LawMeta] = []
        self.by_so_hieu: dict[str, LawMeta] = {}

        self._load()

    def _load(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"metadata.csv not found at: {self.csv_path}. "
                f"Set env METADATA_CSV or mount ./data/metadata.csv into the container."
            )

        df = None
        for sep in [",", "\t", ";", "|"]:
            try:
                tmp = pd.read_csv(self.csv_path, dtype=str, sep=sep, engine="python")
                # chọn parse nào có nhiều cột nhất (để tránh đọc nhầm 1 cột)
                if df is None or tmp.shape[1] > df.shape[1]:
                    df = tmp
            except Exception:
                continue

        if df is None or df.shape[1] <= 1:
            raise ValueError(
                f"Cannot parse metadata file (delimiter issue): {self.csv_path}. "
                f"Detected columns={0 if df is None else df.shape[1]}"
            )

        df = df.fillna("")

        items: list[LawMeta] = []
        by_so_hieu: dict[str, LawMeta] = {}

        for _, r in df.iterrows():
            file_name = r.get("file_name", "").strip()
            law_name = r.get("law_name", "").strip()
            so_hieu = r.get("Số hiệu", "").strip()
            sua = r.get("SỬA ĐỔI, BỔ SUNG", "").strip()

            if not file_name:
                continue

            law_id = _law_id_from_file_name(file_name)

            m = LawMeta(
                file_name=file_name,
                law_name=law_name,
                so_hieu=so_hieu,
                law_id=law_id,
                sua_doi_bo_sung=sua,
            )
            items.append(m)

            if so_hieu:
                by_so_hieu[m.so_hieu_norm] = m

        self.items = items
        self.by_so_hieu = by_so_hieu

    def resolve(self, query: str) -> LawMeta | None:
        """
        Ưu tiên:
        1) Nếu query có số hiệu dạng 59/2020/QH14 -> match chính xác
        2) Nếu query nhắc rõ tên luật -> match theo law_name (ưu tiên tên đúng, ngắn, không phải luật sửa đổi)
        """
        q_raw = query or ""
        q_norm = _norm_text(q_raw)

        # 1) match theo số hiệu
        m = re.search(r"(\d+/\d{4}/qh\d+)", q_raw, flags=re.IGNORECASE)
        if m:
            so = _norm_so_hieu(m.group(1))
            hit = self.by_so_hieu.get(so)
            if hit:
                return hit

        candidates: list[LawMeta] = []
        for it in self.items:
            name_norm = it.law_name_norm
            if not name_norm:
                continue

            # Match hai chiều:
            # - tên luật nằm trong câu hỏi (phổ biến nhất)
            # - hoặc câu hỏi là đúng tên luật (trường hợp user chỉ gõ "luật doanh nghiệp")
            if (name_norm in q_norm) or (q_norm in name_norm):
                candidates.append(it)

        if not candidates:
            return None

        # Ranking: ưu tiên tên chính xác, tên ngắn, không phải "sửa đổi, bổ sung"
        def score(it: LawMeta) -> tuple:
            name = it.law_name_norm
            exact = 1 if name == q_norm else 0
            is_amend = 1 if _norm_text(it.sua_doi_bo_sung) == _norm_text("SỬA ĐỔI, BỔ SUNG") else 0
            # càng ngắn càng tốt
            length = len(name.split())
            return (exact, -is_amend, -1 / max(1, length))

        candidates.sort(key=score, reverse=True)
        return candidates[0]

# singleton index (lazy load để Celery không crash khi import)
_METADATA_INDEX: MetadataLawIndex | None = None

def _get_index() -> MetadataLawIndex:
    global _METADATA_INDEX
    if _METADATA_INDEX is None:
        _METADATA_INDEX = MetadataLawIndex(METADATA_CSV)
    return _METADATA_INDEX

def resolve_law_meta(user_text: str) -> LawMeta | None:
    return _get_index().resolve(user_text)


def resolve_law_id(user_text: str) -> str | None:
    hit = _get_index().resolve(user_text)
    return hit.law_id if hit else None
