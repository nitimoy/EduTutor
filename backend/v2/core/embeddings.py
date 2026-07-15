"""Embedding service using BGE-M3 (best open-source multilingual)."""

from __future__ import annotations

from typing import Any

from llama_index.core.embeddings import BaseEmbedding
from pydantic import Field


class BGEM3Embedding(BaseEmbedding):
    """BGE-M3 embedding model for educational content.

    BGE-M3 is one of the best open-source embeddings because:
    - Multilingual (English + Hindi for NCERT)
    - 1024 dimension (high capacity)
    - Handles technical/educational terms well
    - Supports dense + sparse + multi-vector retrieval
    """

    model_name: str = Field(default="BAAI/bge-m3")
    _model: Any = None

    def _get_model(self):
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel
            self._model = BGEM3FlagModel(self.model_name, use_fp16=True)
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        result = model.encode(texts)
        if isinstance(result, dict):
            return result.get("dense_vecs", result).tolist()
        return result.tolist()

    def _get_query_embedding(self, query: str) -> list[float]:
        model = self._get_model()
        result = model.encode_queries([query])
        if isinstance(result, dict):
            return result.get("dense_vecs", result)[0].tolist()
        return result[0].tolist()

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed([text])[0]

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._get_text_embeddings(texts)
