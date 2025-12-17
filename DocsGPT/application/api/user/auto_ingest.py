import logging
from pathlib import Path
from celery import shared_task

from langchain.schema import Document as LCDocument
from langchain_community.embeddings import HuggingFaceEmbeddings

from application.parser.file.bulk import SimpleDirectoryReader
from application.parser.embedding_pipeline import embed_and_store_documents

# ===== CONFIG =====
LOCAL_DATA_DIR = "/app/application/inputs/local"
VECTOR_FOLDER = "/app/application/indexes/local-folder"
SOURCE_ID = "local-folder"
BATCH_SIZE = 16
# ==================


@shared_task(bind=True, name="auto_ingest_local")
def auto_ingest_local(self):
    """
    Auto ingest documents from local folder using SimpleDirectoryReader
    and embed them in batches to avoid OOM.
    """
    try:
        logging.info("[AUTO-INGEST] Starting local auto ingest")

        # 1. Load documents bằng parser CHUẨN của hệ thống
        reader = SimpleDirectoryReader(
            input_dir=LOCAL_DATA_DIR,
            recursive=True
        )

        def to_lc_document(d):
            # 1) Lấy content
            content = None
            if hasattr(d, "text") and d.text is not None:
                content = d.text
            elif hasattr(d, "page_content") and d.page_content is not None:
                content = d.page_content
            elif hasattr(d, "get_text"):
                content = d.get_text()
            else:
                content = str(d)

            # 2) Lấy metadata (nhiều lib dùng extra_info thay vì metadata)
            meta = {}
            if hasattr(d, "metadata") and d.metadata:
                meta = d.metadata
            elif hasattr(d, "extra_info") and d.extra_info:
                meta = d.extra_info
            elif hasattr(d, "meta") and d.meta:
                meta = d.meta
            elif hasattr(d, "dict"):
                try:
                    dd = d.dict()
                    meta = dd.get("metadata") or dd.get("extra_info") or {}
                except Exception:
                    meta = {}

            meta.setdefault("source", SOURCE_ID)
            meta.setdefault("ingest_type", "local")

            return LCDocument(page_content=content, metadata=meta)

        raw_docs = reader.load_data()
        documents = [to_lc_document(d) for d in raw_docs]

        total_docs = len(documents)

        if total_docs == 0:
            logging.warning("[AUTO-INGEST] No documents found")
            return

        logging.info(f"[AUTO-INGEST] Total documents loaded: {total_docs}")

        embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base", model_kwargs={"device": "cpu"})

        # 2. Batch embed
        for start in range(0, total_docs, BATCH_SIZE):
            end = start + BATCH_SIZE
            batch_docs = documents[start:end]

            logging.info(
                f"[AUTO-INGEST] Embedding batch {start // BATCH_SIZE + 1} "
                f"({start} → {min(end, total_docs)})"
            )

            embed_and_store_documents(
                docs=batch_docs,
                folder_name=VECTOR_FOLDER,
                source_id=SOURCE_ID,
                task_status=self,
                embeddings=embeddings,
            )

        logging.info("[AUTO-INGEST] Completed all batches successfully")

    except Exception as e:
        logging.error("[AUTO-INGEST] FAILED", exc_info=True)
        raise