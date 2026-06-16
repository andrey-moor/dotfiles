from typing import Protocol
import hashlib
import numpy as np


class Embedder(Protocol):
    dim: int

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]: ...
    def embed_query(self, text: str) -> np.ndarray: ...


class FakeEmbedder:
    """Deterministic, torch-free embedder for tests: seeded by text hash."""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


class LocalJinaEmbedder:
    """Real jina-v3 embedder. torch/sentence-transformers imported lazily."""

    def __init__(
        self, model_name: str = "jinaai/jina-embeddings-v3", dim: int = 1024
    ) -> None:
        self.model_name = model_name
        self.dim = dim
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy

            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self._model

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        m = self._load()
        arr = m.encode(texts, task="retrieval.passage", normalize_embeddings=True)
        return [a.astype(np.float32) for a in arr]

    def embed_query(self, text: str) -> np.ndarray:
        m = self._load()
        return m.encode([text], task="retrieval.query", normalize_embeddings=True)[
            0
        ].astype(np.float32)
