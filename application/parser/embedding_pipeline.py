import os
import logging
from typing import List, Any
from retry import retry
from tqdm import tqdm
import numpy as np

from langchain_community.vectorstores import FAISS
from langchain_community.docstore import InMemoryDocstore

from application.core.settings import settings
from application.vectorstore.vector_creator import VectorCreator


def sanitize_content(content: str) -> str:
    """
    Remove NUL characters that can cause vector store ingestion to fail.

    Args:
        content (str): Raw content that may contain NUL characters

    Returns:
        str: Sanitized content with NUL characters removed
    """
    if not content:
        return content
    return content.replace('\x00', '')

def _is_sentence_transformer(embeddings: Any) -> bool:
    return hasattr(embeddings, "encode") and not hasattr(embeddings, "embed_documents")

def _get_embedding_dim(embeddings: Any) -> int:
    """
    Supports:
    - sentence-transformers SentenceTransformer (encode)
    - LangChain embeddings (embed_query)
    """
    if _is_sentence_transformer(embeddings):
        v = embeddings.encode(["dimension_check"], convert_to_numpy=True, show_progress_bar=False)
        return int(v.shape[1])
    # LangChain embeddings
    return len(embeddings.embed_query("dimension_check"))

def _embed_texts(embeddings: Any, texts: List[str], st_batch_size: int = 64) -> "np.ndarray":
    """
    Returns np.ndarray shape (n, dim), dtype float32
    """
    if _is_sentence_transformer(embeddings):
        vecs = embeddings.encode(
            texts,
            batch_size=st_batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.asarray(vecs, dtype=np.float32)

    # LangChain fallback
    vecs = embeddings.embed_documents(texts)
    return np.asarray(vecs, dtype=np.float32)


@retry(tries=10, delay=60)
def add_text_to_store_with_retry(store: Any, doc: Any, source_id: str) -> None:
    """Add a document's text and metadata to the vector store with retry logic.

    Args:
        store: The vector store object.
        doc: The document to be added.
        source_id: Unique identifier for the source.

    Raises:
        Exception: If document addition fails after all retry attempts.
    """
    try:
        # Sanitize content to remove NUL characters that cause ingestion failures
        doc.page_content = sanitize_content(doc.page_content)

        doc.metadata["source_id"] = str(source_id)
        store.add_texts([doc.page_content], metadatas=[doc.metadata])
    except Exception as e:
        logging.error(f"Failed to add document with retry: {e}", exc_info=True)
        raise


def embed_and_store_documents(
    docs: List[Any],
    folder_name: str,
    source_id: str,
    task_status: Any,
    embeddings: Any
) -> None:

    if not docs:
        logging.warning("[EMBED] No valid documents to embed. Skipping.")
        return

    if embeddings is None:
        from application.core.model_settings import ModelRegistry
        embeddings = ModelRegistry.get_default_embeddings()

    os.makedirs(folder_name, exist_ok=True)

    store = None

    if settings.VECTOR_STORE == "faiss":
        index_path = os.path.join(folder_name, "index.faiss")

        if os.path.exists(index_path):
            logging.info("[EMBED] Existing FAISS index found, attempting to load")

            store = FAISS.load_local(
                folder_name,
                embeddings,
                allow_dangerous_deserialization=True
            )

            # ==== AUDIT & SELF-HEAL ====
            if not hasattr(store.docstore, "_dict"):
                logging.error(
                    "[EMBED] Legacy / incompatible FAISS index detected "
                    f"(docstore type={type(store.docstore)}). Rebuilding index."
                )

                # backup
                backup_dir = folder_name + "_legacy_backup"
                os.makedirs(backup_dir, exist_ok=True)
                for f in os.listdir(folder_name):
                    os.rename(
                        os.path.join(folder_name, f),
                        os.path.join(backup_dir, f),
                    )

                store = None

        if store is None:
            import faiss

            dim = len(embeddings.embed_query("dimension_check"))
            index = faiss.IndexFlatL2(dim)

            store = FAISS(
                embedding_function=embeddings,
                index=index,
                docstore=InMemoryDocstore({}),
                index_to_docstore_id={}
            )

    total = len(docs)
    success = 0
    failed = 0

    for idx, doc in tqdm(
        enumerate(docs),
        total=total,
        desc="Embedding",
        unit="doc",
    ):
        try:
            progress = int(((idx + 1) / total) * 100)
            task_status.update_state(state="PROGRESS", meta={"current": progress})

            doc.page_content = sanitize_content(doc.page_content)
            if not doc.page_content or not doc.page_content.strip():
                failed += 1
                continue

            doc.metadata["source_id"] = str(source_id)
            store.add_texts([doc.page_content], metadatas=[doc.metadata])
            success += 1

        except Exception as e:
            failed += 1
            logging.error(f"[EMBED] Failed doc {idx}: {e}", exc_info=True)

    logging.info(
        f"[EMBED AUDIT] Batch summary | total={total} | success={success} | failed={failed}"
    )

    vector_count = store.index.ntotal
    docstore_size = len(store.docstore._dict)

    logging.info(
        f"[EMBED AUDIT] Final index | vectors={vector_count} | docstore={docstore_size}"
    )

    if vector_count == 0:
        raise RuntimeError("[EMBED] FAISS index empty after embedding, aborting save")

    store.save_local(folder_name)
    logging.info("[EMBED] FAISS index saved successfully")


def embed_and_store_documents_batched(
    docs: List[Any],
    folder_name: str,
    source_id: str,
    embeddings: Any,
    batch_size: int = 128,
    task_status: Any = None,
) -> None:
    """
    Embed documents in batches and save FAISS index incrementally.
    Safe for large corpora (30k+ chunks).
    """

    if not docs:
        logging.warning("[EMBED-BATCH] No documents to embed.")
        return

    os.makedirs(folder_name, exist_ok=True)

    store = None
    index_path = os.path.join(folder_name, "index.faiss")

    # Load existing index if exists
    if os.path.exists(index_path):
        logging.info("[EMBED-BATCH] Loading existing FAISS index")
        store = FAISS.load_local(
            folder_name,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    else:
        import faiss
        dim = len(embeddings.embed_query("dimension_check"))
        index = faiss.IndexFlatL2(dim)
        store = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=InMemoryDocstore({}),
            index_to_docstore_id={},
        )

    total = len(docs)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = docs[start:end]

        texts = []
        metas = []

        for doc in batch:
            content = sanitize_content(doc.page_content)
            if not content.strip():
                continue

            meta = doc.metadata or {}
            meta["source_id"] = str(source_id)

            texts.append(content)
            metas.append(meta)

        if not texts:
            continue

        logging.info(
            f"[EMBED-BATCH] Embedding batch {start // batch_size + 1} "
            f"({start} → {end})"
        )

        # 1) Embed batch (GPU nếu là SentenceTransformer)
        vectors = _embed_texts(embeddings, texts, st_batch_size=min(64, len(texts)))

        # 2) Add vectors to FAISS index (CPU FAISS, OK)
        store.index.add(vectors)

        # 3) Update docstore + mapping (giữ tương thích FAISS.load_local/save_local)
        for meta, text in zip(metas, texts):
            # tạo doc_id mới theo số lượng mapping hiện tại
            new_idx = len(store.index_to_docstore_id)
            doc_id = str(new_idx)
            store.index_to_docstore_id[new_idx] = doc_id

            # docstore lưu Document (đúng chuẩn LangChain), không chỉ meta
            from langchain_core.documents import Document
            store.docstore._dict[doc_id] = Document(page_content=text, metadata=meta)

        # 4) SAVE sau mỗi batch (GIỮ yêu cầu của bạn)
        store.save_local(folder_name)

        if task_status:
            progress = int((end / total) * 100)
            task_status.update_state(
                state="PROGRESS",
                meta={"current": progress},
            )

        logging.info(
            f"[EMBED-BATCH] Saved FAISS | vectors={store.index.ntotal}"
        )

    logging.info("[EMBED-BATCH] Completed all batches successfully")
