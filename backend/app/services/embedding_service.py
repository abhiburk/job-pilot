import hashlib
import math

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.entities import TextEmbedding
from backend.app.services.embedding_provider import GeminiEmbeddingProvider


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = GeminiEmbeddingProvider()
        self.model_name = settings.gemini_embedding_model

    @staticmethod
    def _hash_text(text: str) -> str:
        normalized = " ".join(text.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def get_embedding(
        self,
        db: AsyncSession,
        text: str,
    ) -> list[float]:
        normalized = " ".join(text.split())

        if not normalized:
            raise ValueError("Text cannot be empty")

        text_hash = self._hash_text(normalized)

        query = select(TextEmbedding.embedding).where(
            TextEmbedding.text_hash == text_hash,
            TextEmbedding.model_name == self.model_name,
        )

        result = await db.execute(query)
        cached_embedding = result.scalar_one_or_none()

        if cached_embedding is not None:
            return [float(value) for value in cached_embedding]

        # Generate only when the cache has no matching entry.
        embedding = await self.provider.embed_text(normalized)

        statement = (
            insert(TextEmbedding)
            .values(
                text_hash=text_hash,
                model_name=self.model_name,
                embedding=embedding,
            )
            .on_conflict_do_nothing(
                constraint="uq_text_embedding_hash_model"
            )
        )

        await db.execute(statement)

        # Read back the stored value, including if another request
        # inserted the same embedding concurrently.
        result = await db.execute(query)
        stored_embedding = result.scalar_one()

        return [float(value) for value in stored_embedding]

    async def close(self) -> None:
        await self.provider.close()


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    if len(vector_a) != len(vector_b):
        raise ValueError("Embedding dimensions do not match")

    if not vector_a:
        raise ValueError("Embeddings cannot be empty")

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cannot compare zero-length vectors")

    return dot_product / (norm_a * norm_b)