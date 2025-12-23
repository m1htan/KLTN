from application.retriever.classic_rag import ClassicRAG
from application.retriever.graph_rag import GraphRAG

class RetrieverCreator:
    retrievers = {
        "classic": ClassicRAG,
        "graph": GraphRAG,
        "default": GraphRAG,
    }

    @classmethod
    def create_retriever(cls, type, *args, **kwargs):
        retriever_type = (type or "default").lower()
        retiever_class = cls.retrievers.get(retriever_type)
        if not retiever_class:
            raise ValueError(f"No retievers class found for type {type}")
        return retiever_class(*args, **kwargs)
