import chromadb
from chromadb.utils import embedding_functions
from app.config import CHROMA_DIR, settings

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_ef = embedding_functions.DefaultEmbeddingFunction()
_collection = _client.get_collection("smogon", embedding_function=_ef)


def retrieve(species: str, k: int = None) -> list[str]:
    if not species:
        return []
    k = k or settings.retrieval_k
    results = _collection.query(
        query_texts=[species],
        where={"species": species.lower()},
        n_results=k,
    )
    return results["documents"][0] if results["documents"] else []