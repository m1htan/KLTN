import logging
import os

from application.celery_init import celery
from application.parser.embedding_pipeline import embed_and_store_documents
from application.parser.file.bulk import SimpleDirectoryReader

LOCAL_DATA_DIR = "/app/application/inputs/local"
SOURCE_ID = "local-folder"


def auto_ingest_local(task):
    """Embed every document inside ``LOCAL_DATA_DIR`` into the default index."""

    if not os.path.exists(LOCAL_DATA_DIR):
        logging.warning(f"[AUTO-INGEST] Directory not found: {LOCAL_DATA_DIR}")
        return {"success": False}

    reader = SimpleDirectoryReader(input_dir=LOCAL_DATA_DIR, recursive=True)
    docs = reader.load_data()

    if not docs:
        logging.info("[AUTO-INGEST] No documents found.")
        return {"success": False}

    logging.info(f"[AUTO-INGEST] Loaded {len(docs)} docs. Embedding...")

    output_folder = f"/app/indexes/{SOURCE_ID}"

    try:
        embed_and_store_documents(
            docs=docs,
            folder_name=output_folder,
            source_id=SOURCE_ID,
            task_status=task,
        )
        logging.info("[AUTO-INGEST] DONE.")
        return {"success": True}
    except Exception as e:
        logging.error(f"[AUTO-INGEST] ERROR: {e}", exc_info=True)
        return {"success": False}


@celery.task(bind=True, name="auto_ingest_local")
def auto_ingest_local_task(self):
    """Celery wrapper to make ``auto_ingest_local`` schedulable."""

    return auto_ingest_local(self)
