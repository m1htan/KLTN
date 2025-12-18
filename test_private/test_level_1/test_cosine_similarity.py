from langchain_community.vectorstores import FAISS
from DocsGPT.application.vectorstore.base import EmbeddingsWrapper

emb = EmbeddingsWrapper("intfloat/multilingual-e5-base")

db = FAISS.load_local(
    "/DocsGPT/application/indexes/local-folder",
    emb,
    allow_dangerous_deserialization=True
)

docs = db.similarity_search("quy trình thanh toán", k=3)
for d in docs:
    print("----")
    print(d.page_content[:300])
    print(d.metadata)

