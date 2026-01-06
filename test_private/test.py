from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

emb = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-base",
    encode_kwargs={"normalize_embeddings": True},
)

store = FAISS.load_local("D:/Github/KLTN/application/indexes/local-folder", emb, allow_dangerous_deserialization=True)

print("dim:", store.index.d)
print("ntotal:", store.index.ntotal)

first_id = list(store.docstore._dict.keys())[0]
doc = store.docstore._dict[first_id]
print("first_id:", first_id)
print("metadata:", doc.metadata)
print("text_head:", doc.page_content[:300])
