# temporal_mem/storage/qdrant_store.py

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse


class QdrantStore:
    """
    Vector store for semantic memory retrieval.

    Each memory is stored as a point:
    - id: memory_id (string)
    - vector: embedding
    - payload: metadata (user_id, type, slot, status, created_at, etc.)
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        host: str | None = None,
        port: int | None = None,
        collection: str = "",
        vector_size: int = 1536,
        distance: str = "Cosine",
    ) -> None:
        self.collection = collection

        # Cloud or local
        if url:
            self.client = QdrantClient(
                url=url,
                api_key=api_key,
                # check_compatibility=False, # optional
            )
        else:
            self.client = QdrantClient(
                host=host,
                port=port,
                # check_compatibility=False, # optional
            )

        dist = getattr(qmodels.Distance, distance.upper(), qmodels.Distance.COSINE)

        # 1) Check if collection exists
        try:
            self.client.get_collection(self.collection)
            # Collection exists → nothing to do
            # print(f"[QdrantStore] Using existing collection: {self.collection}")
            return
        except (ResponseHandlingException, ConnectionError, OSError) as e:
            # Connection errors - Qdrant server is not running or not accessible
            connection_info = f"URL: {url}" if url else f"HOST: {host}, PORT: {port}"
            raise ConnectionError(
                f"Failed to connect to Qdrant server ({connection_info}). "
                f"Please ensure Qdrant is running and accessible. "
                f"Error: {e!s}"
            ) from e
        except UnexpectedResponse as e:
            # 404 = not found → we should create it
            if e.status_code != 404:
                # some other error, bubble up
                raise

        # 2) Create collection only if it doesn't exist
        # print(f"[QdrantStore] Creating new collection: {self.collection}")
        try:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=dist,
                ),
            )
        except (ResponseHandlingException, ConnectionError, OSError) as e:
            # Connection errors during collection creation
            connection_info = f"URL: {url}" if url else f"HOST: {host}, PORT: {port}"
            raise ConnectionError(
                f"Failed to connect to Qdrant server ({connection_info}). "
                f"Please ensure Qdrant is running and accessible. "
                f"Error: {e!s}"
            ) from e

    # ------------------------------------------------------------------ #
    # UPSERT
    # ------------------------------------------------------------------ #

    def upsert_point(
        self,
        memory_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """
        Insert or update a point for a given memory.
        """
        self.client.upsert(
            collection_name=self.collection,
            points=[
                qmodels.PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    # ------------------------------------------------------------------ #
    # SEARCH
    # ------------------------------------------------------------------ #

    def search(
        self,
        query_vector: list[float],
        user_id: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search similar memories for a given user_id.

        Returns a list of dicts:
        [
          {"id": "mem_id", "score": 0.91, "payload": {...}},
          ...
        ]
        """
        must_conditions: list[qmodels.FieldCondition] = [
            qmodels.FieldCondition(
                key="user_id",
                match=qmodels.MatchValue(value=user_id),
            )
        ]

        if filters:
            if "status" in filters:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="status",
                        match=qmodels.MatchValue(value=filters["status"]),
                    )
                )
            if "type" in filters:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="type",
                        match=qmodels.MatchValue(value=filters["type"]),
                    )
                )
            if "slot" in filters:
                must_conditions.append(
                    qmodels.FieldCondition(
                        key="slot",
                        match=qmodels.MatchValue(value=filters["slot"]),
                    )
                )

        q_filter = qmodels.Filter(
            must=must_conditions,
        )

        # New API in qdrant-client 1.x
        resp = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=q_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        points = resp.points  # list[ScoredPoint]

        results: list[dict[str, Any]] = []
        for p in points:
            results.append(
                {
                    "id": str(p.id),
                    "score": p.score,
                    "payload": dict(p.payload or {}),
                }
            )

        return results

    # ------------------------------------------------------------------ #
    # DELETE
    # ------------------------------------------------------------------ #

    def delete(self, memory_id: str) -> None:
        """
        Delete a point by memory_id.
        """
        self.client.delete(
            collection_name=self.collection,
            points_selector=qmodels.PointIdsList(
                points=[memory_id],
            ),
        )
