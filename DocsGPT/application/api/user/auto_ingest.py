import os
import logging
from application.parser.file.bulk import SimpleDirectoryReader
from application.parser.embedding_pipeline import embed_and_store_documents

LOCAL_DATA_DIR = "/app/application/inputs/local"
SOURCE_ID = "local-folder"


def auto_ingest_local(task):
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