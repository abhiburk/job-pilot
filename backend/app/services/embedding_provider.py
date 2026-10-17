
from google import genai

from backend.app.core.config import settings


class EmbeddingProviderError(RuntimeError):
    """Raised when the embedding provider cannot generate an embedding."""


class GeminiEmbeddingProvider:
    """Generate text embeddings using Google's Gemini API."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise EmbeddingProviderError(
                "GEMINI_API_KEY is not configured"
            )

        try:
            self.client = genai.Client(
                api_key=settings.gemini_api_key
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                "Could not initialize the Gemini embedding client"
            ) from exc

        self.model = settings.gemini_embedding_model

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector, wrapping provider failures."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            response = await self.client.aio.models.embed_content(
                model=self.model,
                contents=text,
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                "Gemini failed to generate an embedding"
            ) from exc

        if not response.embeddings or not response.embeddings[0].values:
            raise EmbeddingProviderError(
                "Gemini returned an empty embedding"
            )

        return list(response.embeddings[0].values)

    async def close(self) -> None:
        await self.client.aio.aclose()
