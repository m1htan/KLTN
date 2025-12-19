import re
from docx import Document

LAW_FILE = "D:/Github/KLTN/application/inputs/local/Bộ luật-45-2019-QH14.docx"

doc = Document(LAW_FILE)

# Ghép toàn bộ paragraph thành text
text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

print(text[:1000])  # debug trước


patterns = {
    "chapter": re.findall(
        r"^Chương\s+[IVXLC]+.*",
        text,
        flags=re.MULTILINE | re.IGNORECASE
    ),
    "article": re.findall(
        r"^Điều\s+\d+[a-zA-Z]?\s*[\.:].*",
        text,
        flags=re.MULTILINE
    ),
    "clause_numeric": re.findall(
        r"^\s*\d+\.\s+.+",
        text,
        flags=re.MULTILINE
    ),
    "clause_named": re.findall(
        r"^\s*Khoản\s+\d+.*",
        text,
        flags=re.MULTILINE | re.IGNORECASE
    ),
}

print("=== STRUCTURE SCAN RESULT ===")
for k, v in patterns.items():
    print(f"{k}: {len(v)} samples")
    for line in v[:5]:
        print("  ", line)
    print()
