import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# connect to Qdrant running in Docker on localhost:6333
client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))

VECTOR_SIZE = 3072
DISTANCE = Distance.COSINE

LIKED_OUTFITS = "liked_outfits"


"""
Create collections if they don't already exist.
Safe to call on every startup — it checks first and skips existing ones.
"""
def ensure_collections():
    existing = {c.name for c in client.get_collections().collections}

    if LIKED_OUTFITS not in existing:
        client.create_collection(
            collection_name=LIKED_OUTFITS,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=DISTANCE),
        )
        print(f"Created collection: {LIKED_OUTFITS}")