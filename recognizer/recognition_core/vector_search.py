import torch
from tools.qdrant import _get_client


def search(query: torch.Tensor, limit=12):
    client, collection_name = _get_client()
    if isinstance(query, torch.Tensor):
        query = query.detach().cpu()

    results = client.query_points(
        collection_name=collection_name,
        query=query.tolist(),
        limit=limit,
    )

    return [
        {
            'embed_id': point.payload.get('embed_id'),
            'user_id': point.payload.get('user_id'),
            'pose': point.payload.get('pose'),
            'score': point.score,
        }
        for point in results.points
    ]
