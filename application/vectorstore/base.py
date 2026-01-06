import logging
import os
from abc import ABC, abstractmethod
import torch

from langchain_openai import OpenAIEmbeddings
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings

from application.core.settings import settings


class EmbeddingsWrapper(Embeddings):
    def __init__(self, model_name, *args, **kwargs):
        logging.info(f"Initializing EmbeddingsWrapper with model: {model_name}")
        try:
            kwargs.setdefault("trust_remote_code", True)

            # Force device based on settings.USE_GPU (để worker/backend dùng GPU đúng)
            device = "cuda" if settings.USE_GPU else "cpu"
            kwargs.setdefault("device", device)

            self.model = SentenceTransformer(
                model_name,
                config_kwargs={"allow_dangerous_deserialization": True},
                model_kwargs={
                    "torch_dtype": torch.float16 if settings.USE_GPU else torch.float32,
                    "low_cpu_mem_usage": True,
                },
                *args,
                **kwargs,
            )

            if self.model is None or self.model._first_module() is None:
                raise ValueError(
                    f"SentenceTransformer model failed to load properly for: {model_name}"
                )

            self.dimension = self.model.get_sentence_embedding_dimension()
            logging.info(f"Successfully loaded model with dimension: {self.dimension}")
        except Exception as e:
            logging.error(
                f"Failed to initialize SentenceTransformer with model {model_name}: {str(e)}",
                exc_info=True,
            )
            raise

    def embed_query(self, query: str) -> list[float]:
        return self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return self.model.encode(
            documents,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    def __call__(self, text):
        if isinstance(text, str):
            return self.embed_query(text)
        elif isinstance(text, list):
            return self.embed_documents(text)
        else:
            raise ValueError("Input must be a string or a list of strings")


class EmbeddingsSingleton:
    _instances = {}

    @staticmethod
    def get_instance(embeddings_name, *args, **kwargs):
        if embeddings_name not in EmbeddingsSingleton._instances:
            EmbeddingsSingleton._instances[embeddings_name] = (
                EmbeddingsSingleton._create_instance(embeddings_name, *args, **kwargs)
            )
        return EmbeddingsSingleton._instances[embeddings_name]

    @staticmethod
    def _create_instance(embeddings_name, *args, **kwargs):
        embeddings_factory = {
            "openai_text-embedding-ada-002": OpenAIEmbeddings,
            "huggingface_sentence-transformers/all-mpnet-base-v2": lambda: EmbeddingsWrapper(
                "sentence-transformers/all-mpnet-base-v2"
            ),
            "huggingface_sentence-transformers-all-mpnet-base-v2": lambda: EmbeddingsWrapper(
                "sentence-transformers/all-mpnet-base-v2"
            ),
            "huggingface_hkunlp/instructor-large": lambda: EmbeddingsWrapper(
                "hkunlp/instructor-large"
            ),
        }

        if embeddings_name in embeddings_factory:
            return embeddings_factory[embeddings_name](*args, **kwargs)
        else:
            return EmbeddingsWrapper(embeddings_name, *args, **kwargs)


class BaseVectorStore(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def search(self, *args, **kwargs):
        """Search for similar documents/chunks in the vectorstore"""
        pass

    @abstractmethod
    def add_texts(self, texts, metadatas=None, *args, **kwargs):
        """Add texts with their embeddings to the vectorstore"""
        pass

    def delete_index(self, *args, **kwargs):
        """Delete the entire index/collection"""
        pass

    def save_local(self, *args, **kwargs):
        """Save vectorstore to local storage"""
        pass

    def get_chunks(self, *args, **kwargs):
        """Get all chunks from the vectorstore"""
        pass

    def add_chunk(self, text, metadata=None, *args, **kwargs):
        """Add a single chunk to the vectorstore"""
        pass

    def delete_chunk(self, chunk_id, *args, **kwargs):
        """Delete a specific chunk from the vectorstore"""
        pass

    def is_azure_configured(self):
        return (
            settings.OPENAI_API_BASE
            and settings.OPENAI_API_VERSION
            and settings.AZURE_DEPLOYMENT_NAME
        )

    def _get_embeddings(self, embeddings_name, embeddings_key=None):
        """
        Load embeddings model correctly including:
        - OpenAI
        - HF MPNet
        - Alibaba gte-Qwen2 (local path)
        """

        # CASE 1: OpenAI
        if embeddings_name == "openai_text-embedding-ada-002":
            if self.is_azure_configured():
                os.environ["OPENAI_API_TYPE"] = "azure"
                return EmbeddingsSingleton.get_instance(
                    embeddings_name,
                    model=settings.AZURE_EMBEDDINGS_DEPLOYMENT_NAME
                )
            return EmbeddingsSingleton.get_instance(
                embeddings_name, openai_api_key=embeddings_key
            )

        # CASE 2: Alibaba gte-Qwen2-1.5B-instruct (LOCAL MODEL)
        if "gte-qwen2" in embeddings_name.lower() or "gte-qwen" in embeddings_name.lower():
            local_path = "/app/application/models/gte-qwen2"

            if os.path.exists(local_path):
                logging.info(f"Loading Alibaba gte-Qwen2 embedding model from local path: {local_path}")
                return EmbeddingsSingleton.get_instance(
                    local_path,
                    trust_remote_code=True,
                    device="cuda" if settings.USE_GPU else "cpu"
                )
            else:
                logging.error("Local Alibaba gte-Qwen2 model not found! Expected at /app/application/models/gte-qwen2")
                raise FileNotFoundError("Missing model directory: /app/application/models/gte-qwen2")

        # CASE 3: HF mpnet
        if embeddings_name == "huggingface_sentence-transformers/all-mpnet-base-v2":
            return EmbeddingsSingleton.get_instance("sentence-transformers/all-mpnet-base-v2")

        # DEFAULT: try load from HF by name
        return EmbeddingsSingleton.get_instance(embeddings_name)