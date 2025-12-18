from langchain_community.vectorstores import FAISS
from DocsGPT.application.vectorstore.base import EmbeddingsWrapper
from collections import defaultdict
import re

# ====== CONFIG ======
INDEX_PATH = "/DocsGPT/application/indexes/local-folder"
EMBED_MODEL = "intfloat/multilingual-e5-base"

# ====== LOAD INDEX ======
emb = EmbeddingsWrapper(EMBED_MODEL)
db = FAISS.load_local(
    INDEX_PATH,
    emb,
    allow_dangerous_deserialization=True
)

docstore = db.docstore._dict
index = db.index

print("=== GLOBAL STATS ===")
print("Total vectors in FAISS:", index.ntotal)
print("Total documents in docstore:", len(docstore))
print()

# ====== GROUP CHUNKS BY SOURCE ======
by_source = defaultdict(list)

for doc in docstore.values():
    source = doc.metadata.get("source", "UNKNOWN")
    by_source[source].append(doc.page_content)

print("=== CHUNK COUNT BY SOURCE ===")
for src, chunks in by_source.items():
    print(f"{src}: {len(chunks)} chunks")

print("\n")

# ====== FUNCTION: CHECK EDGE CONTENT ======
def check_edge_presence(chunks, edge_text, window=200):
    edge = edge_text[:window]
    for c in chunks:
        if edge in c:
            return True
    return False

# ====== AUDIT EACH SOURCE ======
print("=== EDGE CONTENT AUDIT ===")

for src, chunks in by_source.items():
    full_text = "\n".join(chunks)

    # normalize whitespace
    full_text = re.sub(r"\s+", " ", full_text).strip()

    start_ok = check_edge_presence(chunks, full_text[:300])
    end_ok = check_edge_presence(chunks, full_text[-300:])

    print(f"[{src}]")
    print("  Has beginning content:", start_ok)
    print("  Has ending content   :", end_ok)

    if not start_ok or not end_ok:
        print("  >>> WARNING: Possible content loss")
    print()


########################################################################################################################
from langchain_community.vectorstores import FAISS
from DocsGPT.application.vectorstore.base import EmbeddingsWrapper

INDEX_PATH = "/DocsGPT/application/indexes/local-folder"
EMBED_MODEL = "intfloat/multilingual-e5-base"

emb = EmbeddingsWrapper(EMBED_MODEL)
db = FAISS.load_local(
    INDEX_PATH,
    emb,
    allow_dangerous_deserialization=True
)

docstore = db.docstore._dict

print("=== CHUNK SIZE AUDIT ===")

for i, doc in enumerate(docstore.values()):
    text = doc.page_content
    print(f"\n--- CHUNK {i} ---")
    print("Length (chars):", len(text))
    print("Preview start :", text[:200].replace("\n", " "))
    print("Preview end   :", text[-200:].replace("\n", " "))
