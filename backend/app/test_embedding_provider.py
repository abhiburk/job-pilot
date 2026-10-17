import asyncio

from backend.app.services.embedding_provider import GeminiEmbeddingProvider


async def main():
    provider = GeminiEmbeddingProvider()

    try:
        vector = await provider.embed_text(
            "Senior Laravel developer building REST APIs"
        )

        print("Embedding dimensions:", len(vector))
        print("First five values:", vector[:5])

    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())