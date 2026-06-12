from __future__ import annotations

import hashlib
import importlib
import math
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Fixed namespace for deterministic UUID5 point IDs.
# Qdrant local mode requires PointStruct objects with UUID or uint64 IDs.
# uuid5(QDRANT_NS, candidate_id) is stable across restarts: upserting the same
# candidate always targets the same point (idempotent), and the original
# candidate_id remains queryable via payload filter.
_QDRANT_NS = uuid.UUID("00000000-0000-0000-0000-00000000c0de")


class TextEmbeddingService:
    def __init__(self, context):
        self.context = context
        self.model = None
        self.mode = "HASH_FALLBACK"
        self.dimension = 64
        self._load_model()

    def embed(self, text: str) -> list[float]:
        text = text or ""
        if self.model is not None:
            try:
                vector = self.model.encode(text)
                return [float(value) for value in vector]
            except Exception:
                pass
        return self._hash_embedding(text)

    def _load_model(self) -> None:
        config = self.context.config.get("vector", {}).get("text", {})
        model_name = config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            sentence_transformers = importlib.import_module("sentence_transformers")
            sentence_transformer = getattr(sentence_transformers, "SentenceTransformer")
            self.model = sentence_transformer(model_name)
            self.mode = "SENTENCE_TRANSFORMER"
            sample_vector = self.model.encode("cv-card-demo")
            self.dimension = len(sample_vector)
        except Exception:
            self.model = None

    def _hash_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = np.zeros(self.dimension, dtype=np.float32)
        if not text:
            return vector.tolist()
        for index, character in enumerate(text.encode("utf-8")):
            vector[index % self.dimension] += float(character) / 255.0
        for index, value in enumerate(digest):
            vector[index % self.dimension] += float(value) / 255.0
        norm = float(np.linalg.norm(vector)) or 1.0
        return (vector / norm).tolist()


class ImageEmbeddingService:
    def __init__(self, context):
        self.context = context
        self.model = None
        self.mode = "FINGERPRINT_FALLBACK"
        self.dimension = 16
        self._load_model()

    def embed(self, image_path: str) -> list[float]:
        path = Path(image_path)
        if not path.exists():
            return [0.0] * self.dimension
        if self.model is not None:
            try:
                pil_module = importlib.import_module("PIL.Image")
                image = pil_module.open(str(path)).convert("RGB")
                vector = self.model.encode(image)
                return [float(value) for value in vector]
            except Exception:
                pass
        return self._fingerprint_embedding(path)

    def _load_model(self) -> None:
        try:
            sentence_transformers = importlib.import_module("sentence_transformers")
            sentence_transformer = getattr(sentence_transformers, "SentenceTransformer")
            model_name = self.context.config.get("vector", {}).get("image", {}).get("model", "clip-ViT-B-32")
            self.model = sentence_transformer(model_name)
            self.mode = "CLIP"
            sample_vector = self.model.encode(importlib.import_module("PIL.Image").new("RGB", (4, 4)))
            self.dimension = len(sample_vector)
        except Exception:
            self.model = None

    def _fingerprint_embedding(self, image_path: Path) -> list[float]:
        try:
            import cv2
        except Exception:
            return [0.0] * self.dimension

        image = cv2.imread(str(image_path))
        if image is None:
            return [0.0] * self.dimension
        resized = cv2.resize(image, (4, 4), interpolation=cv2.INTER_AREA)
        vector = resized.astype("float32").reshape(-1) / 255.0
        if vector.size < self.dimension:
            vector = np.pad(vector, (0, self.dimension - vector.size))
        elif vector.size > self.dimension:
            vector = vector[: self.dimension]
        norm = float(np.linalg.norm(vector)) or 1.0
        return (vector / norm).tolist()


class QdrantVectorStore:
    def __init__(self, context):
        self.context = context
        self.client = None
        self.mode = "IN_MEMORY_NON_PERSISTENT"
        self.collections: Dict[str, Dict[str, Dict[str, Any]]] = {
            "candidate_text_embeddings": {},
            "candidate_image_embeddings": {},
        }
        # Qdrant local mode is not thread-safe; serialise all client calls.
        self._lock = threading.Lock()
        self._load_client()

    def upsert(self, *, collection: str, point_id: str, vector: list[float], payload: Dict[str, Any]) -> None:
        if self.client is not None:
            models = importlib.import_module("qdrant_client.models")
            # Qdrant local mode requires PointStruct objects (not plain dicts).
            # The remote REST client accepts dicts; local mode does not — hence
            # the previous AttributeError: 'dict' object has no attribute 'id'.
            # UUID5 from point_id gives a stable, valid Qdrant point identifier.
            qdrant_id = str(uuid.uuid5(_QDRANT_NS, point_id))
            point = models.PointStruct(
                id=qdrant_id,
                vector=[float(v) for v in vector],
                payload={**(payload or {}), "_point_key": point_id},
            )
            with self._lock:
                self._ensure_qdrant_collection(collection, len(vector))
                self.client.upsert(collection_name=collection, points=[point])
            return

        self.collections.setdefault(collection, {})[point_id] = {
            "vector": vector,
            "payload": payload,
        }

    def search(self, *, collection: str, vector: list[float], limit: int = 3) -> list[Dict[str, Any]]:
        if self.client is not None:
            with self._lock:
                results = self.client.search(collection_name=collection, query_vector=vector, limit=limit)
            return [
                {
                    "id": item.payload.get("_point_key", str(item.id)),
                    "score": float(item.score),
                    "payload": dict(item.payload or {}),
                }
                for item in results
            ]

        scores = []
        for pid, item in self.collections.get(collection, {}).items():
            score = self._cosine_similarity(vector, item["vector"])
            scores.append({"id": pid, "score": score, "payload": dict(item.get("payload") or {})})
        scores.sort(key=lambda item: item["score"], reverse=True)
        return scores[:limit]

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "mode": self.mode,
            "collections": list(self.collections.keys()),
        }

    def _load_client(self) -> None:
        vector_config = self.context.config.get("vector", {})
        enabled = bool(vector_config.get("enabled", True))
        if not enabled:
            return

        try:
            qdrant_module = importlib.import_module("qdrant_client")
            qdrant_client = getattr(qdrant_module, "QdrantClient")
            path = vector_config.get("qdrant_path", "./data/qdrant")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.client = qdrant_client(path=path)
            self.mode = "QDRANT"
        except Exception:
            self.client = None
            self.mode = "IN_MEMORY_NON_PERSISTENT"

    def _ensure_qdrant_collection(self, collection: str, dimension: int) -> None:
        models = importlib.import_module("qdrant_client.models")
        existing = [item.name for item in self.client.get_collections().collections]
        if collection in existing:
            return
        self.client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )

    def _cosine_similarity(self, vector_a: list[float], vector_b: list[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a)) or 1.0
        norm_b = math.sqrt(sum(b * b for b in vector_b)) or 1.0
        return float(dot_product / (norm_a * norm_b))


class VectorService:
    service_name = "vector"

    def __init__(self, context):
        self.context = context
        self.text_embedding = TextEmbeddingService(context)
        self.image_embedding = ImageEmbeddingService(context)
        self.store = QdrantVectorStore(context)

    def index_text(
        self,
        candidate_id: str,
        text: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        snapshot_id: Optional[str] = None,
    ) -> None:
        if not text.strip():
            return
        vector = self.text_embedding.embed(text)
        point_id = self._point_id(candidate_id, snapshot_id, suffix="text")
        self.store.upsert(
            collection="candidate_text_embeddings",
            point_id=point_id,
            vector=vector,
            payload={"candidate_id": candidate_id, **(payload or {})},
        )

    def search_text(self, text: str, limit: int = 3) -> list[Dict[str, Any]]:
        if not text.strip():
            return []
        vector = self.text_embedding.embed(text)
        return self.store.search(collection="candidate_text_embeddings", vector=vector, limit=limit)

    def index_image(
        self,
        candidate_id: str,
        image_path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        snapshot_id: Optional[str] = None,
    ) -> None:
        vector = self.image_embedding.embed(image_path)
        point_id = self._point_id(candidate_id, snapshot_id, suffix="image")
        self.store.upsert(
            collection="candidate_image_embeddings",
            point_id=point_id,
            vector=vector,
            payload={"candidate_id": candidate_id, **(payload or {})},
        )

    def search_image(self, image_path: str, limit: int = 3) -> list[Dict[str, Any]]:
        vector = self.image_embedding.embed(image_path)
        return self.store.search(collection="candidate_image_embeddings", vector=vector, limit=limit)

    def get_status(self) -> Dict[str, Any]:
        payload = self.store.get_status()
        payload["text_embedding_mode"] = self.text_embedding.mode
        payload["image_embedding_mode"] = self.image_embedding.mode
        return payload

    @staticmethod
    def _point_id(candidate_id: str, snapshot_id: Optional[str], *, suffix: str) -> str:
        snapshot_key = snapshot_id or "latest"
        return f"{candidate_id}:{snapshot_key}:{suffix}"