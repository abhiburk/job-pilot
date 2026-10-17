import asyncio
import math
import os

from google import genai

from backend.app.core.config import settings

async def main():
    client = genai.Client(
        api_key=settings.gemini_api_key
    )

    texts = [
        "Senior Laravel backend developer building REST APIs and billing systems",
        "PHP engineer experienced in Laravel, APIs, queues, and payment processing",
        "Frontend designer specializing in colors and visual layouts",
    ]

    vectors = []

    for text in texts:
        result = await client.aio.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
        )
        vectors.append(result.embeddings[0].values)

    def cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        return dot / (norm_a * norm_b)

    print(
        "Backend role similarity:",
        round(cosine_similarity(vectors[0], vectors[1]), 4),
    )
    print(
        "Backend vs frontend similarity:",
        round(cosine_similarity(vectors[0], vectors[2]), 4),
    )

    await client.aio.aclose()


if __name__ == "__main__":
    asyncio.run(main())