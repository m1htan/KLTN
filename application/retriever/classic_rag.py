import logging
import os
import re

from application.core.settings import settings
from application.llm.llm_creator import LLMCreator
from application.retriever.base import BaseRetriever
from application.utils import num_tokens_from_string
from application.vectorstore.vector_creator import VectorCreator


class ClassicRAG(BaseRetriever):
    def __init__(
        self,
        source,
        chat_history=None,
        prompt="",
        chunks=2,
        doc_token_limit=50000,
        model_id="docsgpt-local",
        user_api_key=None,
        llm_name=settings.LLM_PROVIDER,
        api_key=settings.API_KEY,
        decoded_token=None,
    ):
        self.original_question = source.get("question", "")
        self.chat_history = chat_history if chat_history is not None else []
        self.prompt = prompt
        if isinstance(chunks, str):
            try:
                self.chunks = int(chunks)
            except ValueError:
                logging.warning(
                    f"Invalid chunks value '{chunks}', using default value 2"
                )
                self.chunks = 2
        else:
            self.chunks = chunks
        user_identifier = user_api_key if user_api_key else "default"
        logging.info(
            f"ClassicRAG initialized with chunks={self.chunks}, user_api_key={user_identifier}, "
            f"sources={'active_docs' in source and source['active_docs'] is not None}"
        )
        self.model_id = model_id
        self.doc_token_limit = doc_token_limit
        self.user_api_key = user_api_key
        self.llm_name = llm_name
        self.api_key = api_key
        self.llm = LLMCreator.create_llm(
            self.llm_name,
            api_key=self.api_key,
            user_api_key=self.user_api_key,
            decoded_token=decoded_token,
        )

        if "active_docs" in source and source["active_docs"] is not None:
            if isinstance(source["active_docs"], list):
                self.vectorstores = source["active_docs"]
            else:
                self.vectorstores = [source["active_docs"]]
        else:
            self.vectorstores = []
        self.question = self._rephrase_query()
        self.decoded_token = decoded_token
        self._validate_vectorstore_config()

    def _validate_vectorstore_config(self):
        """Validate vectorstore IDs and remove any empty/invalid entries"""
        if not self.vectorstores:
            logging.warning("No vectorstores configured for retrieval")
            return
        invalid_ids = [
            vs_id for vs_id in self.vectorstores if not vs_id or not vs_id.strip()
        ]
        if invalid_ids:
            logging.warning(f"Found invalid vectorstore IDs: {invalid_ids}")
            self.vectorstores = [
                vs_id for vs_id in self.vectorstores if vs_id and vs_id.strip()
            ]

    def _rephrase_query(self):
        """Rephrase user query with chat history context for better retrieval"""
        if (
            not self.original_question
            or not self.chat_history
            or self.chat_history == []
            or self.chunks == 0
            or not self.vectorstores
        ):
            return self.original_question
        prompt = (
            "Given the following conversation history:\n"
            f"{self.chat_history}\n\n"
            "Rephrase the following user question to be a standalone search query "
            "that captures all relevant context from the conversation:\n"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": self.original_question},
        ]

        try:
            rephrased_query = self.llm.gen(model=self.model_id, messages=messages)
            print(f"Rephrased query: {rephrased_query}")
            return rephrased_query if rephrased_query else self.original_question
        except Exception as e:
            logging.error(f"Error rephrasing query: {e}", exc_info=True)
            return self.original_question

    def _get_data(self):
        if self.chunks == 0 or not self.vectorstores:
            logging.info(
                f"ClassicRAG._get_data: Skipping retrieval - chunks={self.chunks}, "
                f"vectorstores_count={len(self.vectorstores) if self.vectorstores else 0}"
            )
            return []

        all_docs = []
        candidates = []

        chunks_per_source = max(1, self.chunks // len(self.vectorstores))
        token_budget = max(int(self.doc_token_limit * 0.9), 100)
        cumulative_tokens = 0

        for vectorstore_id in self.vectorstores:
            if vectorstore_id:
                try:
                    docsearch = VectorCreator.create_vectorstore(
                        settings.VECTOR_STORE, vectorstore_id, settings.EMBEDDINGS_KEY
                    )
                    analysis = analyze_legal_query(self.question)

                    search_kwargs = {
                        "k": max(chunks_per_source * 2, 20)
                    }

                    # ===== HARD METADATA FILTER (STEP 5) =====
                    if analysis["has_structure"]:
                        metadata_filter = {
                            "doc_type": "law",
                            "article_no": analysis["article_no"],
                        }

                        if analysis["clause_no"] is not None:
                            metadata_filter["clause_no"] = analysis["clause_no"]

                        search_kwargs["filter"] = metadata_filter
                        logging.info(
                            f"[LEGAL-ROUTING] Applying metadata filter: {metadata_filter}"
                        )

                    docs_temp = docsearch.search(
                        self.question,
                        **search_kwargs
                    )

                    for doc in docs_temp:
                        if cumulative_tokens >= token_budget:
                            break

                        if hasattr(doc, "page_content") and hasattr(doc, "metadata"):
                            page_content = doc.page_content
                            metadata = doc.metadata
                        else:
                            page_content = doc.get("text", doc.get("page_content", ""))
                            metadata = doc.get("metadata", {})

                        title = metadata.get(
                            "title", metadata.get("post_title", page_content)
                        )
                        if not isinstance(title, str):
                            title = str(title)
                        title = title.split("/")[-1]

                        filename = (
                            metadata.get("filename")
                            or metadata.get("file_name")
                            or metadata.get("source")
                        )
                        if isinstance(filename, str):
                            filename = os.path.basename(filename) or filename
                        else:
                            filename = title
                        if not filename:
                            filename = title
                        source_path = metadata.get("source") or vectorstore_id

                        doc_text_with_header = f"{filename}\n{page_content}"
                        doc_tokens = num_tokens_from_string(doc_text_with_header)

                        if cumulative_tokens + doc_tokens < token_budget:
                            candidates.append(
                                {
                                    "title": title,
                                    "text": page_content,
                                    "source": source_path,
                                    "filename": filename,
                                    "metadata": metadata or {},
                                }
                            )

                            cumulative_tokens += doc_tokens

                    if cumulative_tokens >= token_budget:
                        break

                except Exception as e:
                    logging.error(
                        f"Error searching vectorstore {vectorstore_id}: {e}",
                        exc_info=True,
                    )
                    continue

        logging.info(
            f"ClassicRAG._get_data: Retrieval complete - retrieved {len(candidates)} documents "
            f"(requested chunks={self.chunks}, chunks_per_source={chunks_per_source}, "
            f"cumulative_tokens={cumulative_tokens}/{token_budget})"
        )

        # === LEGAL RERANK ===
        candidates.sort(
            key=lambda d: legal_chunk_score(d, self.question),
            reverse=True
        )

        all_docs = []
        cumulative_tokens = 0

        for d in candidates:
            doc_text = f"{d['filename']}\n{d['text']}"
            tokens = num_tokens_from_string(doc_text)

            if cumulative_tokens + tokens > token_budget:
                break

            all_docs.append(d)
            cumulative_tokens += tokens

        return all_docs

    def search(self, query: str = ""):
        """Search for documents using optional query override"""
        if query:
            self.original_question = query
            self.question = self._rephrase_query()
        return self._get_data()

def analyze_legal_query(question: str) -> dict:
    """
    Phân tích câu hỏi pháp luật: Điều / Khoản
    """
    q = question.lower()

    article_no = None
    clause_no = None

    m_article = re.search(r"điều\s+(\d+)", q)
    if m_article:
        article_no = int(m_article.group(1))

    m_clause = re.search(r"khoản\s+(\d+)", q)
    if m_clause:
        clause_no = int(m_clause.group(1))

    return {
        "article_no": article_no,
        "clause_no": clause_no,
        "has_structure": article_no is not None,
    }


def legal_chunk_score(doc, question: str):
    """
    Rerank nhẹ sau khi đã filter cứng
    """
    meta = doc.get("metadata", {}) or {}
    score = 0

    chunk_type = meta.get("chunk_type")
    if chunk_type == "article":
        score += 100
    elif chunk_type == "article_clause":
        score += 50

    analysis = analyze_legal_query(question)

    if analysis["article_no"] is not None:
        if meta.get("article_no") == analysis["article_no"]:
            score += 50

    if analysis["clause_no"] is not None:
        if meta.get("clause_no") == analysis["clause_no"]:
            score += 30

    return score