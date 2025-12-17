from DocsGPT.application.parser.legal_chunker import chunk_articles
from DocsGPT.application.parser.legal_vn_parser import parse_law_text
from DocsGPT.application.parser.file.docs_parser import DocxParser
from pathlib import Path

parser = DocxParser()
file = Path("D:/Github/KLTN/DocsGPT/application/inputs/local/Bộ luật-45-2019-QH14.docx")

text = parser.parse_file(file)
articles = parse_law_text(text)

chunks = chunk_articles(
    articles=articles,
    law_meta={"source": "local-folder"},
    source_file=str(file)
)

# --- TEST 1: Có chunk Điều ---
assert any(c.extra_info["chunk_type"] == "article" for c in chunks)

# --- TEST 2: Có chunk Khoản ---
assert any(c.extra_info["chunk_type"] == "article_clause" for c in chunks)

# --- TEST 3: Chunk Khoản có nội dung đầy đủ ---
clause_chunks = [c for c in chunks if c.extra_info["chunk_type"] == "article_clause"]
sample = clause_chunks[0].text

assert "Khoản" in sample
assert "Điều" in sample
assert len(sample) > 200, "Chunk Khoản quá ngắn → thiếu nội dung"

print("LEGAL CHUNKER: PASS")
