from DocsGPT.application.parser.legal_vn_parser import parse_law_text
from DocsGPT.application.parser.file.docs_parser import DocxParser
from pathlib import Path

parser = DocxParser()
file = Path("D:/Github/KLTN/DocsGPT/application/inputs/local/Bộ luật-45-2019-QH14.docx")

text = parser.parse_file(file)
articles = parse_law_text(text)

# --- TEST 1: Điều tồn tại ---
art3 = next(a for a in articles if a.number == "3")

assert art3.title.startswith("Giải thích"), "Sai tiêu đề Điều 3"

# --- TEST 2: Số lượng khoản ---
assert len(art3.clauses) >= 9, "Thiếu khoản trong Điều 3"

# --- TEST 3: Khoản nhiều dòng ---
khoan1 = art3.clauses[0]
assert "\n" in khoan1.text, "Khoản 1 phải có nhiều dòng"

# --- TEST 4: Khoản không nuốt sang Điều khác ---
assert "Điều 4" not in khoan1.text, "Khoản bị ăn sang Điều khác"

print("PARSER LEGAL VN: PASS")
