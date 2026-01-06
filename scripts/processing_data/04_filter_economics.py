from __future__ import annotations

import shutil
from pathlib import Path
import pandas as pd


# ====== CẤU HÌNH ======
METADATA_CSV = r"D:/Github/KLTN/data/metadata.csv"
SOURCE_DIR = Path(r"D:/Github/KLTN/application/inputs/full_law")
DEST_DIR = Path(r"D:/Github/KLTN/application/inputs/local")

NO_COL = "No."
FIELD_COL = "lĩnh_vực"
SRC_PATH_COL = "file_path"
NAME_COL = "file_name"
TARGET_FIELD = "economics"
EXPECTED_EXT = ".docx"


def safe_copy_with_suffix(src: Path, dest_dir: Path) -> tuple[Path, bool]:
    """
    Copy file sang dest_dir.
    Nếu trùng tên → thêm suffix _dup{n}
    Trả về (đường dẫn đích, có bị đổi tên không)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / src.name
    if not dest.exists():
        shutil.copy2(src, dest)
        return dest, False

    stem, ext = src.stem, src.suffix
    n = 1
    while True:
        candidate = dest_dir / f"{stem}_dup{n}{ext}"
        if not candidate.exists():
            shutil.copy2(src, candidate)
            return candidate, True
        n += 1


def main():
    df = pd.read_csv(METADATA_CSV, encoding="utf-8-sig")

    required_cols = {NO_COL, FIELD_COL, SRC_PATH_COL, NAME_COL}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Thiếu cột trong metadata: {missing}")

    # Lọc lĩnh_vực = economics
    mask = df[FIELD_COL].astype(str).str.strip().str.lower() == TARGET_FIELD
    df_econ = df[mask].copy()

    print(f"Tổng dòng metadata: {len(df):,}")
    print(f"Số dòng lĩnh_vực = '{TARGET_FIELD}': {len(df_econ):,}")
    print("-" * 90)

    copied = renamed = missing_files = skipped_ext = 0

    for _, row in df_econ.iterrows():
        no = row[NO_COL]
        file_name = str(row[NAME_COL]).strip()
        file_path_raw = str(row[SRC_PATH_COL]).strip()

        src = Path(file_path_raw) if file_path_raw and file_path_raw.lower() != "nan" else SOURCE_DIR / file_name
        if not src.is_absolute():
            src = SOURCE_DIR / src

        # Kiểm tra extension
        if src.suffix.lower() != EXPECTED_EXT:
            candidate = src.with_suffix(EXPECTED_EXT)
            if candidate.exists():
                src = candidate
            else:
                print(f"[SKIP_EXT][No={no}] {src}")
                skipped_ext += 1
                continue

        if not src.exists():
            print(f"[WARN_MISSING][No={no}] {src}")
            missing_files += 1
            continue

        dest_path, was_renamed = safe_copy_with_suffix(src, DEST_DIR)
        copied += 1

        if was_renamed:
            renamed += 1
            print(
                f"[COPIED_RENAMED][No={no}] "
                f"{src.name} -> {dest_path.name}"
            )
        else:
            print(
                f"[COPIED][No={no}] "
                f"{src.name}"
            )

    print("-" * 90)
    print("TÓM TẮT")
    print(f"Copied: {copied:,}")
    print(f"Renamed (duplicate): {renamed:,}")
    print(f"Missing files: {missing_files:,}")
    print(f"Skipped (not .docx): {skipped_ext:,}")


if __name__ == "__main__":
    main()
