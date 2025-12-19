from langchain_community.vectorstores import FAISS
from application.vectorstore.base import EmbeddingsWrapper

emb = EmbeddingsWrapper("intfloat/multilingual-e5-base")

db = FAISS.load_local(
    "D:/Github/KLTN/application/indexes/local-folder",
    emb,
    allow_dangerous_deserialization=True
)

results = db.similarity_search_with_score(
    "quy trình thanh toán",
    k=5
)

for doc, score in results:
    print("SCORE:", score)
    print("META :", doc.metadata)
    print(doc.page_content[:300])
    print("------")


q_vec = emb.embed_query("quy trình thanh toán")
print(len(q_vec))  # thường là 768 với e5-base
index = db.index
print(index.ntotal)  # số vector trong index

import numpy as np

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

q = emb.embed_query("quy trình thanh toán")

docs = list(db.docstore._dict.values())

for d in docs[:5]:
    v = emb.embed_query(d.page_content[:500])
    sim = cosine_sim(q, v)
    print(sim, d.metadata)

scores = [score for _, score in results]
print("Min:", min(scores))
print("Max:", max(scores))
print("Avg:", sum(scores)/len(scores))
