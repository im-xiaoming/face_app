from django.conf import settings
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
import torch

_cache = {}

def _get_client():
    if _cache:
        return _cache['client']
    
    client = QdrantClient(path=Path(settings.BASE_DIR) / 'vectorstore' / 'qdrant')
    collection_name = 'users'
    
    if not client.collection_exists(collection_name=collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),
        )
        
    _cache['client'] = client
    _cache['collection_name'] = collection_name
    
    return _cache['client'], _cache['collection_name']


def search(query: torch.Tensor, limit=5):
    client, collection_name = _get_client['client']
    
    results = client.query_points(
        collection_name=collection_name,
        query=query.tolist(),
        query_filter=Filter(
            must=[
                FieldCondition(key="user_id", match=MatchValue(value=1))
            ]
        ),
        limit=limit,
    )
    outputs = []

    for point in results.points:
        outputs.append({
            'user_id': point.payload.get('user_id'),
            'score': point.score
        })
    return outputs

    
def update(queries: list[tuple[int, torch.Tensor, dict]]):
    client, collection_name = _get_client['client']
    
    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(id=id, vector=vector.tolist(), payload=payload) \
                for id, vector, payload in queries
        ]
    )
    print("DONE!")
    

def delete(ids: list[int]):
    client, collection_name = _get_client['client']
     
    client.delete(
        collection_name=collection_name,
        points_selector=ids
    )
    print("DONE!")