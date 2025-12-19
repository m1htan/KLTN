from langchain_community.vectorstores import FAISS
from application.vectorstore.base import EmbeddingsWrapper

emb = EmbeddingsWrapper("intfloat/multilingual-e5-base")
db = FAISS.load_local(
    "application/indexes/local-folder",
    emb,
    allow_dangerous_deserialization=True
)

docs = db.docstore._dict.values()

# --- TEST 1: không có XML ---
for d in docs:
    assert not d.page_content.strip().startswith("<?xml"), "Ingest XML rác"

# --- TEST 2: chunk size hợp lý ---
for d in docs:
    assert len(d.page_content) < 8000, "Chunk quá lớn, sai logic luật"

# --- TEST 3: metadata pháp lý ---
for d in docs:
    meta = d.metadata
    assert "article" in meta
    assert "chunk_type" in meta

print("VECTORSTORE AUDIT: PASS")
