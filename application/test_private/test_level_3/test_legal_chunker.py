from application.parser.legal_vn_parser import parse_law_text
from application.parser.legal_chunker import chunk_articles

LAW_FILE = "application/inputs/local/Bộ luật-100-2015-QH13.docx"

with open(LAW_FILE, "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

articles = parse_law_text(text)

chunks = chunk_articles(
    articles=articles,
    law_meta={"source_id": "local-folder"},
    source_file=LAW_FILE
)

# Thống kê
from collections import Counter
types = Counter(c.extra_info["chunk_type"] for c in chunks)
vectors = Counter(c.extra_info["for_vector"] for c in chunks)
graphs = Counter(c.extra_info["for_graph"] for c in chunks)

print("CHUNK TYPES:", types)
print("FOR VECTOR:", vectors)
print("FOR GRAPH:", graphs)

# In thử 3 clause + 3 point
for c in chunks:
    if c.extra_info["chunk_type"] in ("clause", "point"):
        print(c.extra_info)
        break
