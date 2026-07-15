"""BGE-M3 embedding provider (production backend).

FlagEmbedding + torch are heavy and optional, so they are imported lazily inside
``__init__`` — importing this module never requires them. The model runs in
inference mode, producing deterministic dense vectors.
"""

from __future__ import annotations

from backend.retrieval.embedding.provider import EmbeddingProvider

_DEFAULT_MODEL = "BAAI/bge-m3"
_DIMENSION = 1024


class BGEM3EmbeddingProvider(EmbeddingProvider):
    """Dense embeddings from BAAI/bge-m3 via FlagEmbedding."""

    def __init__(self, model_name: str = _DEFAULT_MODEL, use_fp16: bool = False) -> None:
        try:
            from FlagEmbedding import BGEM3FlagModel  # heavy, optional
        except ImportError as exc:  # pragma: no cover - exercised only without dep
            raise ImportError(
                "BGEM3EmbeddingProvider requires the 'FlagEmbedding' package. "
                "Install it (and torch) to use the BGE-M3 backend, or use the "
                "default HashingEmbeddingProvider."
            ) from exc
        self._model_name = model_name
        self._model = BGEM3FlagModel(model_name, use_fp16=use_fp16)

    @property
    def provider_id(self) -> str:
        return "bge-m3"

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return _DIMENSION

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        dense = self._model.encode(texts)["dense_vecs"]
        return [vector.tolist() for vector in dense]

    def embed_query(self, text: str) -> list[float]:
        dense = self._model.encode([text])["dense_vecs"]
        return dense[0].tolist()
