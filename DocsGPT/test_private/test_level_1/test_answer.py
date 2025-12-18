from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-base"
)

db = FAISS.load_local(
    "/DocsGPT/application/indexes/local-folder",
    embeddings,
    allow_dangerous_deserialization=True
)

query = "Luật kế toán quy định về nội dung công tác kế toán"
docs = db.similarity_search(query, k=3)

for i, d in enumerate(docs):
    print(f"\n--- RESULT {i} ---")
    print(d.page_content[:400])
    print(d.metadata)

for i, d in enumerate(docs):
    print(i, d.metadata)
