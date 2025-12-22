from application.knowledge_graph.neo4j_client import (
    Neo4jClient,
    load_neo4j_config_from_env,
)
from application.knowledge_graph.graph_writer import GraphWriter
from application.knowledge_graph.graph_builder import LegalGraphBuilder

# Lấy dữ liệu thật từ FAISS (bạn đã test trước đó)
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

emb = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-base",
    model_kwargs={"device": "cpu"},
)

store = FAISS.load_local(
    "/app/application/indexes/local-folder",
    emb,
    allow_dangerous_deserialization=True,
)

# Lấy một tập nhỏ docs để test (10–20 doc)
docs = []
for d in list(store.docstore._dict.values())[:20]:
    docs.append({
        "text": d.page_content,
        "metadata": d.metadata,
    })

print("Loaded docs:", len(docs))

# Build graph
client = Neo4jClient(load_neo4j_config_from_env())
writer = GraphWriter(client)
writer.ensure_constraints()

builder = LegalGraphBuilder()
result = builder.build_from_retrieved_docs(docs)

print("Nodes:")
print(" Laws:", len(result.laws))
print(" Articles:", len(result.articles))
print(" Clauses:", len(result.clauses))
print(" Points:", len(result.points))

print("Edges:")
print(" HAS_ARTICLE:", len(result.edges_has_article))
print(" HAS_CLAUSE:", len(result.edges_has_clause))
print(" HAS_POINT:", len(result.edges_has_point))
print(" REFERS_TO:", len(result.edges_refers_to))
print(" EXCEPTION_OF:", len(result.edges_exception_of))

# Ghi vào Neo4j
writer.upsert_nodes("Law", result.laws)
writer.upsert_nodes("Article", result.articles)
writer.upsert_nodes("Clause", result.clauses)
writer.upsert_nodes("Point", result.points)

writer.upsert_edges("HAS_ARTICLE", result.edges_has_article)
writer.upsert_edges("HAS_CLAUSE", result.edges_has_clause)
writer.upsert_edges("HAS_POINT", result.edges_has_point)
writer.upsert_edges("REFERS_TO", result.edges_refers_to)
writer.upsert_edges("EXCEPTION_OF", result.edges_exception_of)

client.close()

print("DONE")
