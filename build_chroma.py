import json, chromadb
from chromadb.utils import embedding_functions
from app.config import DATA_DIR, CHROMA_DIR

with open(DATA_DIR/"smogon_chunks.jsonl") as f:
    chunks  = [json.loads(line) for line in f]

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
ef = embedding_functions.DefaultEmbeddingFunction()

client.delete_collection("smogon") if "smogon" in [c.name for c in client.list_collections()] else None
collection = client.create_collection("smogon", embedding_function=ef)

collection.add(
    documents=[c["text"] for c in chunks],
    ids=[f"{c['species']}-{c.get('set_name') or 'overview'}-{i}" for i, c in enumerate(chunks)],
    metadatas=[{"species": c["species"].lower()} for c in chunks],
)

print(f"Indexed {len(chunks)} chunks into Chroma at {CHROMA_DIR}")