import os
import re
import logging
import pandas as pd
import pdfplumber
from docx import Document

# CONFIG
BASE_DIR = "D:/Github/KLTN/application/inputs/full_law"
OUTPUT_CSV = "D:/Github/KLTN/data/law_metadata.csv"
LOG_FILE = "D:/Github/KLTN/data/extract.log"

SUPPORTED_EXT = [".pdf", ".docx", ".txt"]


# ENSURE DIRECTORIES
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# LOGGING
logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
logging.getLogger().addHandler(console)


# TEXT EXTRACTORS
def read_pdf(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:3]:  # chỉ đọc 3 trang đầu
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def read_docx(path: str) -> str:
    doc = Document(path)
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(lines[:50])  # giới hạn đoạn đầu


def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read(5000)


def extract_text(path: str, ext: str) -> str:
    if ext == ".pdf":
        return read_pdf(path)
    if ext == ".docx":
        return read_docx(path)
    if ext == ".txt":
        return read_txt(path)
    return ""


# LAW NAME EXTRACTION (FROM CONTENT ONLY)
def normalize_law_name(name: str) -> str:
    """
    Chuẩn hóa tên luật:
    - bỏ năm
    - bỏ 'và các văn bản ...'
    - chuẩn hóa khoảng trắng
    """
    name = re.sub(r"\b(19|20)\d{2}\b", "", name)
    name = re.sub(r"và các.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name)
    return name.strip().title()


def extract_law_name_from_text(text: str) -> str | None:
    """
    Trích tên luật từ nội dung văn bản luật Việt Nam.
    KHÔNG dựa vào filename.
    """
    if not text:
        return None

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for i, line in enumerate(lines):
        upper = line.upper()

        # Case 1: LUẬT / BỘ LUẬT đứng riêng 1 dòng
        if upper in ["LUẬT", "BỘ LUẬT"]:
            if i + 1 < len(lines):
                candidate = f"{upper} {lines[i + 1]}"
                return normalize_law_name(candidate)

        # Case 2: LUẬT XYZ / BỘ LUẬT XYZ cùng dòng
        if upper.startswith("LUẬT ") or upper.startswith("BỘ LUẬT "):
            return normalize_law_name(line)

    return None

# MAIN PIPELINE
def main():
    rows = []
    counter = 0

    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in SUPPORTED_EXT:
                continue

            counter += 1
            path = os.path.join(root, file)

            logging.info(f"Processing: {path}")

            try:
                text = extract_text(path, ext)

                if not text.strip():
                    logging.warning(f"Empty content | {file}")

                law_name = extract_law_name_from_text(text)

                if not law_name:
                    logging.warning(f"Cannot extract law_name | {file}")

                row = {
                    "No.": counter,
                    "file_name": file,
                    "law_name": law_name,
                    "file_path": path,
                    "file_type": ext,
                    "notes": "law_name_from_text"
                }

                rows.append(row)

            except Exception as e:
                logging.error(f"Failed processing {file} | {str(e)}")

    df = pd.DataFrame(
        rows,
        columns=[
            "No.",
            "file_name",
            "law_name",
            "file_path",
            "file_type",
            "notes"
        ]
    )

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    logging.info(f"Done. Total files processed: {counter}")
    logging.info(f"Output saved to {OUTPUT_CSV}")

# ENTRY POINT
if __name__ == "__main__":
    main()
