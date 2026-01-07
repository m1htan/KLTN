import logging
from celery import shared_task
import re
import os
import torch

from langchain_community.embeddings import HuggingFaceEmbeddings

from application.parser.file.bulk import SimpleDirectoryReader
from application.parser.legal_vn_parser import parse_law_text
from application.parser.legal_chunker import chunk_articles
from application.utils import count_tokens_docs
from application.parser.embedding_pipeline import embed_and_store_documents_batched

from application.knowledge_graph.graph_builder import LegalGraphBuilder
from application.knowledge_graph.graph_writer import GraphWriter
from application.knowledge_graph.neo4j_client import (
    Neo4jClient,
    load_neo4j_config_from_env
)
from application.knowledge_graph import schema as S


# CONFIG
LOCAL_DATA_DIR = "/app/application/inputs/local"
VECTOR_FOLDER = "/app/indexes/local-folder"
SOURCE_ID = "local-folder"

@shared_task(bind=True, name="auto_ingest_local")
def auto_ingest_local(self):
    """
    Auto ingest LAW documents from local folder.
    All files in LOCAL_DATA_DIR are treated as LAW documents.
    """
    try:
        logging.info("[AUTO-INGEST-LAW] Starting local law auto ingest")

        device = "cuda" if torch.cuda.is_available() else "cpu"

        embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-base",
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": False},
        )

        all_chunks = []

        for filename in os.listdir(LOCAL_DATA_DIR):
            file_path = os.path.join(LOCAL_DATA_DIR, filename)

            if not os.path.isfile(file_path):
                continue

            if not filename.lower().endswith((".txt", ".docx", ".pdf")):
                continue

            logging.info(f"[AUTO-INGEST-LAW] Processing file: {filename}")

            # 1. Read raw text
            reader = SimpleDirectoryReader(
                input_files=[file_path],
                recursive=False
            )
            raw_docs = reader.load_data()
            if not raw_docs:
                logging.warning(f"[AUTO-INGEST-LAW] Empty file: {filename}")
                continue

            full_text = "\n".join(d.text for d in raw_docs if d.text)

            # LAW IDENTITY (MVP: derive from filename, later from header text)
            law_code = os.path.splitext(filename)[0]
            law_name = law_code

            articles = parse_law_text(
                full_text,
                law_code=law_code,
                law_name=law_name,
            )

            if not articles:
                logging.warning(f"[AUTO-INGEST-LAW] No articles parsed: {filename}")
                continue

            # 3. Law-level metadata
            law_meta = {
                "source": filename,
                "ingest_type": "local_law",
            }

            # 4. Chunk theo Điều / Khoản (đã chuẩn hoá ở STEP 2)
            chunks = chunk_articles(
                articles=articles,
                law_meta=law_meta,
                source_file=filename,
            )

            all_chunks.extend(chunks)

        if not all_chunks:
            logging.warning("[AUTO-INGEST-LAW] No law chunks generated")
            return

        docs = [
            d.to_langchain_format()
            for d in all_chunks
            if d.extra_info.get("chunk_type") == "article"
        ]
        total_tokens = count_tokens_docs(docs)

        logging.info(
            f"[AUTO-INGEST-LAW] Total chunks: {len(docs)} | Total tokens: {total_tokens}"
        )

        # ===== BUILD KNOWLEDGE GRAPH (MVP) =====
        logging.info("[GRAPH] Start building graph_docs")
        graph_docs = []
        for d in all_chunks:
            graph_docs.append({
                "text": d.text,
                "metadata": d.extra_info
            })
        logging.info(f"[GRAPH] graph_docs ready | size={len(graph_docs)}")

        logging.info("[GRAPH] Initializing LegalGraphBuilder")
        builder = LegalGraphBuilder()

        logging.info("[GRAPH] Calling build_from_retrieved_docs")
        result = builder.build_from_retrieved_docs(graph_docs)
        logging.info("[GRAPH] build_from_retrieved_docs DONE")

        logging.info("[GRAPH] Connecting Neo4j")
        client = Neo4jClient(load_neo4j_config_from_env())
        writer = GraphWriter(client)

        logging.info("[GRAPH] ensure_constraints")
        writer.ensure_constraints()
        logging.info("[GRAPH] ensure_constraints DONE")

        logging.info(f"[GRAPH] upsert_nodes LAW={len(result.laws)}")
        writer.upsert_nodes(S.LABEL_LAW, result.laws)

        logging.info(f"[GRAPH] upsert_nodes ARTICLE={len(result.articles)}")
        writer.upsert_nodes(S.LABEL_ARTICLE, result.articles)

        logging.info(f"[GRAPH] upsert_nodes CLAUSE={len(result.clauses)}")
        writer.upsert_nodes(S.LABEL_CLAUSE, result.clauses)

        logging.info(f"[GRAPH] upsert_nodes POINT={len(result.points)}")
        writer.upsert_nodes(S.LABEL_POINT, result.points)

        logging.info("[GRAPH] upsert_edges HAS_ARTICLE")
        writer.upsert_edges(S.REL_HAS_ARTICLE, result.edges_has_article)

        logging.info("[GRAPH] upsert_edges HAS_CLAUSE")
        writer.upsert_edges(S.REL_HAS_CLAUSE, result.edges_has_clause)

        logging.info("[GRAPH] upsert_edges HAS_POINT")
        writer.upsert_edges(S.REL_HAS_POINT, result.edges_has_point)

        logging.info("[GRAPH] upsert_edges REFERS_TO")
        writer.upsert_edges(S.REL_REFERS_TO, result.edges_refers_to)

        logging.info("[GRAPH] upsert_edges EXCEPTION_OF")
        writer.upsert_edges(S.REL_EXCEPTION_OF, result.edges_exception_of)

        client.close()
        logging.info("[GRAPH] Neo4j closed")

        # 5. Embed & store
        embed_and_store_documents_batched(
            docs=docs,
            folder_name=VECTOR_FOLDER,
            source_id=SOURCE_ID,
            embeddings=embeddings,
            batch_size=128,
            task_status=self,
        )

        logging.info("[AUTO-INGEST-LAW] Completed successfully")

    except Exception as e:
        logging.error("[AUTO-INGEST-LAW] FAILED", exc_info=True)
        raise