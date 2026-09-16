import logging

import chromadb
from chromadb.utils import embedding_functions

from app.config import CHROMA_DIR, settings

logger = logging.getLogger(__name__)
_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_collection(
            "smogon",
            embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        )
    except Exception as error:
        logger.warning("Smogon index unavailable: %s", error)
    return _collection


def retrieve(species: str, k: int | None = None) -> list[str]:
    if not species:
        return []

    collection = _get_collection()
    if collection is None:
        return []

    results = collection.query(
        query_texts=[species],
        where={"species": species.lower()},
        n_results=k or settings.retrieval_k,
    )
    return results["documents"][0] if results.get("documents") else []