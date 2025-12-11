import logging
import os
import docx2txt

from application.celery_init import celery
from application.parser.embedding_pipeline import embed_and_store_documents

LOCAL_DATA_DIR = "/app/application/inputs/local"
SOURCE_ID = "local-folder"


def load_docx(path):
    try:
        text = docx2txt.process(path)
        return [{"text": text, "file_name": os.path.basename(path)}]
    except Exception as e:
        logging.error(f"[AUTO-INGEST] DOCX parse error {path}: {e}")
        return []


def load_text_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return [{"text": text, "file_name": os.path.basename(path)}]
    except Exception as e:
        logging.error(f"[AUTO-INGEST] TEXT parse error {path}: {e}")
        return []


def auto_ingest_local(task):
    if not os.path.exists(LOCAL_DATA_DIR):
        logging.warning(f"[AUTO-INGEST] Directory not found: {LOCAL_DATA_DIR}")
        return {"success": False}

    docs = []

    # Manually walk the folder
    for root, _, files in os.walk(LOCAL_DATA_DIR):
        for fname in files:
            full_path = os.path.join(root, fname)

            if fname.lower().endswith(".docx"):
                logging.info(f"[AUTO-INGEST] Loading DOCX: {full_path}")
                docs.extend(load_docx(full_path))

            elif fname.lower().endswith((".txt", ".md")):
                logging.info(f"[AUTO-INGEST] Loading TEXT: {full_path}")
                docs.extend(load_text_file(full_path))

            else:
                logging.info(f"[AUTO-INGEST] Ignoring unsupported file: {full_path}")

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
    return auto_ingest_local(self)