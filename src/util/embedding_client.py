from __future__ import annotations

from dataclasses import dataclass
from typing import List

from util.constants import EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS


class EmbeddingClient:
    """
    Simple embedding interface used by indexers/retrievers in this repo.
    """

    def encode_documents(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def encode_queries(self, texts: List[str]) -> List[List[float]]:
        return self.encode_documents(texts)


@dataclass
class LocalSentenceTransformerEmbeddings(EmbeddingClient):
    model_name: str = EMBEDDING_MODEL

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)

    def encode_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        # Ensure list[list[float]]
        return vectors.astype("float32").tolist()


def get_embedding_client() -> EmbeddingClient:
    """
    Factory based on EMBEDDING_PROVIDER.

    Note: Groq does not provide embeddings; use `openai` or `local`.
    """
    if EMBEDDING_PROVIDER == "local":
        return LocalSentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)

    # Default: OpenAI embeddings via pymilvus helper (requires OPENAI_API_KEY)
    from pymilvus.model.dense import OpenAIEmbeddingFunction

    return OpenAIEmbeddingFunction(model_name=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)


