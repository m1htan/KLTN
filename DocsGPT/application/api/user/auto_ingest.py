import os
import logging
import gc

from application.celery_init import celery
from application.parser.file.bulk import load_files_bulk
from application.parser.embedding_pipeline import embed_and_store_documents
from application.vectorstore.vector_creator import get_vector_store
from application.core.model_settings import get_embedding_model

logger = logging.getLogger(__name__)

LOCAL_DATA_DIR = os.getenv(
    "LOCAL_DATA_DIR", "/app/application/inputs/local"
)
SOURCE_ID = "local-folder"
BATCH_SIZE = int(os.getenv("LOCAL_INGEST_BATCH_SIZE", "20"))


@celery.task(name="auto_ingest_local")
def auto_ingest_local():
    """
    Auto ingest toàn bộ file trong thư mục LOCAL_DATA_DIR
    - Support: PDF, DOCX, HTML, TXT, MD (theo parser có sẵn)
    - Chạy theo batch
    - Gắn vào source_id = local-folder
    """

    if not os.path.exists(LOCAL_DATA_DIR):
        logger.warning(
            "[AUTO-INGEST] Folder not found: %s", LOCAL_DATA_DIR
        )
        return "LOCAL_DATA_DIR not found"

    all_files = []
    for root, _, files in os.walk(LOCAL_DATA_DIR):
        for f in files:
            if f.lower().endswith(
                (".pdf", ".docx", ".html", ".htm", ".txt", ".md")
            ):
                all_files.append(os.path.join(root, f))

    total = len(all_files)
    logger.info("[AUTO-INGEST] Found %d files", total)

    if total == 0:
        return "No files to ingest"

    embedding_model = get_embedding_model()
    vector_store = get_vector_store(source_id=SOURCE_ID)

    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(batches):
        batch_files = all_files[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]

        logger.info(
            "[AUTO-INGEST] Batch %d/%d (%d files)",
            i + 1, batches, len(batch_files)
        )

        try:
            documents = load_files_bulk(batch_files)
            if not documents:
                logger.warning(
                    "[AUTO-INGEST] Batch %d: no documents parsed",
                    i + 1
                )
                continue

            embed_and_store_documents(
                documents=documents,
                source_id=SOURCE_ID,
                metadata={"origin": "local-folder"},
                embedding_model=embedding_model,
                vector_store=vector_store,
            )

            logger.info(
                "[AUTO-INGEST] Batch %d completed (%d docs)",
                i + 1, len(documents)
            )

        except Exception as e:
            logger.exception(
                "[AUTO-INGEST] Batch %d failed: %s",
                i + 1, e
            )

        finally:
            documents = None
            gc.collect()

    logger.info("[AUTO-INGEST] DONE")
    return "DONE"