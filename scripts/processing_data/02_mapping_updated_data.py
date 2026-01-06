import re
import pandas as pd

# ========= GAN CUNG DUONG DAN =========
AUTHORITATIVE_PATH = "D:/Github/KLTN/data/authoritative_286_laws.csv"
METADATA_PATH = "D:/Github/KLTN/data/metadata.csv"

OUT_FINAL = "D:/Github/KLTN/data/mapping_metadata/metadata_final_reconciled.csv"
# =====================================


def read_csv_flexible(path: str) -> pd.DataFrame:
    seps = [",", ";", "\t", "|"]
    best_df = None
    best_cols = -1

    for sep in seps:
        try:
            df = pd.read_csv(path, sep=sep, engine="python", dtype=str)
            if df.shape[1] > best_cols:
                best_df = df
                best_cols = df.shape[1]
        except Exception:
            continue

    if best_df is None or best_cols <= 1:
        raise ValueError(f"Khong the doc file CSV: {path}")

    return best_df


def normalize_so_hieu(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    s = s.upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("\\", "/")
    return s


def to_int_series_safe(s: pd.Series) -> pd.Series:
    """Chuyen series sang int an toan (NaN -> -1)"""
    return pd.to_numeric(s, errors="coerce").fillna(-1).astype(int)

def pick_first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Tra ve ten cot dau tien ton tai trong df (case-sensitive)."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def main():
    auth = read_csv_flexible(AUTHORITATIVE_PATH)
    meta = read_csv_flexible(METADATA_PATH)

    if "Số hiệu" not in auth.columns:
        raise KeyError("authoritative khong co cot 'Số hiệu'")
    if "Số hiệu" not in meta.columns:
        raise KeyError("metadata khong co cot 'Số hiệu'")

    # Luu thu tu cot goc de giu nguyen (new cols se append cuoi)
    original_cols = meta.columns.tolist()

    # Dam bao co cot No. de lam index
    if "No." not in meta.columns:
        meta.insert(0, "No.", range(1, len(meta) + 1))
    else:
        # Neu No. bi rong/khong phai so: tu dong dien lai theo thu tu dong
        no_int = to_int_series_safe(meta["No."])
        if (no_int < 1).any():
            meta["No."] = range(1, len(meta) + 1)
        else:
            meta["No."] = no_int.astype(str)

    # Tao key
    auth["_so_hieu_key"] = auth["Số hiệu"].map(normalize_so_hieu)
    meta["_so_hieu_key"] = meta["Số hiệu"].map(normalize_so_hieu)

    auth_valid = (
        auth.dropna(subset=["_so_hieu_key"])
            .drop_duplicates(subset=["_so_hieu_key"], keep="first")
            .copy()
    )
    meta_valid = (
        meta.dropna(subset=["_so_hieu_key"])
            .drop_duplicates(subset=["_so_hieu_key"], keep="first")
            .copy()
    )

    auth_keys = set(auth_valid["_so_hieu_key"].tolist())
    meta_keys = set(meta_valid["_so_hieu_key"].tolist())

    # ====== MAP STATUS TU AUTHORITATIVE SANG METADATA ======
    auth_status_col = pick_first_existing_col(auth_valid, ["Status", "status", "STATUS"])
    meta_status_col = pick_first_existing_col(meta, ["Status", "status", "STATUS"])

    status_map = None
    if auth_status_col is not None:
        status_map = (
            auth_valid.set_index("_so_hieu_key")[auth_status_col]
            .fillna("")
            .to_dict()
        )

    # ====== PHAN A: GIU NGUYEN METADATA, THEM COT CHECK (APPEND CUOI) ======
    meta_out = meta.copy()

    # 4 cot moi: de o CUOI
    meta_out["CHECK_META_IN_AUTH"] = meta_out["_so_hieu_key"].isin(auth_keys).map(
        lambda x: "OK" if x else "NOT_IN_AUTHORITATIVE"
    )
    meta_out["CHECK_AUTH_IN_META"] = ""  # dong metadata de trong
    meta_out["RECORD_TYPE"] = "METADATA_ROW"
    meta_out["IN_AUTHORITATIVE"] = meta_out["_so_hieu_key"].isin(auth_keys).astype(bool)  # phuc vu filter nhanh

    # MAP STATUS
    if status_map is not None and meta_status_col is not None:
        meta_out[meta_status_col] = meta_out[meta_status_col].fillna("").astype(str)
        mask_blank = (
                meta_out[meta_status_col].str.strip().eq("") |
                meta_out[meta_status_col].str.lower().eq("nan")
        )
        meta_out.loc[mask_blank, meta_status_col] = (
            meta_out.loc[mask_blank, "_so_hieu_key"].map(status_map).fillna("")
        )

    # ====== PHAN B: APPEND CAC DONG AUTHORITATIVE-ONLY ======
    missing_in_meta_keys = sorted(list(auth_keys - meta_keys))
    auth_only_rows = pd.DataFrame(columns=meta_out.columns)  # default 0 dong

    if missing_in_meta_keys:
        auth_only = auth_valid[auth_valid["_so_hieu_key"].isin(missing_in_meta_keys)].copy()
        n = len(auth_only)

        # Tao n dong rong theo schema meta_out
        auth_only_rows = pd.DataFrame("", index=range(n), columns=meta_out.columns)

        # Gan No. tiep theo
        current_max_no = to_int_series_safe(meta_out["No."]).max()
        auth_only_rows["No."] = [str(i) for i in range(current_max_no + 1, current_max_no + n + 1)]

        # Dien So hieu + key
        auth_only_rows["Số hiệu"] = auth_only["Số hiệu"].values
        auth_only_rows["_so_hieu_key"] = auth_only["_so_hieu_key"].values

        # Danh dau
        auth_only_rows["CHECK_META_IN_AUTH"] = ""  # dong auth-only de trong
        auth_only_rows["CHECK_AUTH_IN_META"] = "NOT_IN_METADATA"
        auth_only_rows["RECORD_TYPE"] = "AUTHORITATIVE_ONLY"
        auth_only_rows["IN_AUTHORITATIVE"] = True

        # Neu metadata co cac cot nay, va authoritative co, thi copy sang (khong bat buoc)
        for c in ["Tên VB", "law_type", "year"]:
            if c in auth_only.columns and c in auth_only_rows.columns:
                auth_only_rows[c] = auth_only[c].fillna("").values

        # Dien Status cho dong AUTHORITATIVE_ONLY
        if auth_status_col is not None and meta_status_col is not None:
            if meta_status_col in auth_only_rows.columns:
                auth_only_rows[meta_status_col] = auth_only[auth_status_col].fillna("").values

    # ====== OUTPUT CUOI: 1 FILE DUY NHAT ======
    final_df = pd.concat([meta_out, auth_only_rows], ignore_index=True)

    # Yeu cau: cac cot moi o CUOI -> giu nguyen thu tu cot goc + _so_hieu_key + 4 cot moi
    new_cols = ["_so_hieu_key", "CHECK_META_IN_AUTH", "CHECK_AUTH_IN_META", "RECORD_TYPE", "IN_AUTHORITATIVE"]
    base_cols = [c for c in original_cols if c in final_df.columns]  # thu tu cot goc
    # dam bao No. luon o dau (neu original_cols khong co No.)
    if "No." not in base_cols and "No." in final_df.columns:
        base_cols = ["No."] + [c for c in base_cols if c != "No."]

    # them cac cot bo sung neu chua co trong base_cols
    remaining = [c for c in final_df.columns if c not in base_cols]
    # sap xep remaining: dua new_cols ve cuoi cung (giu dung yeu cau)
    remaining_non_new = [c for c in remaining if c not in new_cols]
    remaining_new = [c for c in new_cols if c in final_df.columns and c not in base_cols and c not in remaining_non_new]
    final_df = final_df[base_cols + remaining_non_new + remaining_new]

    # Dat index = No. (No. se khong con la cot du lieu)
    final_df = final_df.set_index("No.", drop=True)

    # Ghi file (giu index)
    final_df.to_csv(OUT_FINAL, index=True, encoding="utf-8-sig")

    print("Hoan tat")
    print(f"Output duy nhat: {OUT_FINAL}")
    print(f"Authoritative-only (thieu ben metadata): {len(missing_in_meta_keys)} dong")
    print(f"Metadata-but-missing-in-authoritative: {(meta_out['CHECK_META_IN_AUTH'] == 'NOT_IN_AUTHORITATIVE').sum()} dong")


if __name__ == "__main__":
    main()

