from google import genai
from backend.app.core.config import settings


class GeminiEmbeddingProvider:
    """Generate text embeddings using Google's Gemini API."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )
        self.model = settings.gemini_embedding_model

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a piece of text."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        response = await self.client.aio.models.embed_content(
            model=self.model,
            contents=text,
        )

        if not response.embeddings or not response.embeddings[0].values:
            raise RuntimeError("Gemini returned an empty embedding")

        return list(response.embeddings[0].values)

    async def close(self) -> None:
        await self.client.aio.aclose()