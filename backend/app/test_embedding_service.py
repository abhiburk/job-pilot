import asyncio

from backend.app.core.database import AsyncSessionLocal
from backend.app.services.embedding_service import (
    EmbeddingService,
    cosine_similarity,
)

async def main():
    service = EmbeddingService()

    try:
        async with AsyncSessionLocal() as db:
            text_a = (
                "Senior Laravel backend developer building "
                "REST APIs, billing systems and queues."
            )
            text_b = (
                "PHP engineer experienced in Laravel, REST APIs "
                "and payment processing."
            )

            vector_a = await service.get_embedding(db, text_a)
            vector_b = await service.get_embedding(db, text_b)

            similarity = cosine_similarity(vector_a, vector_b)

            await db.commit()

            print("Embedding dimensions:", len(vector_a))
            print("Semantic similarity:", round(similarity, 4))

            # Request the same text again to verify cache retrieval.
            cached_vector = await service.get_embedding(db, text_a)
            print("Cache returns same vector:", cached_vector == vector_a)

            await db.rollback()

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())