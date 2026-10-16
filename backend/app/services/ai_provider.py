
from groq import AsyncGroq, APIConnectionError, APIStatusError, RateLimitError

from backend.app.core.config import settings


MODEL = settings.groq_model


class AIProviderError(Exception):
    """Raised when the AI provider cannot generate a response."""


def get_groq_client() -> AsyncGroq:
    api_key = settings.groq_api_key

    if not api_key:
        raise AIProviderError(
            "Groq is not configured. Set GROQ_API_KEY in your environment."
        )

    return AsyncGroq(api_key=api_key)


async def generate_text(
    *,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1200,
) -> str:
    try:
        client = get_groq_client()

        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content

        if not content or not content.strip():
            raise AIProviderError("The AI provider returned an empty response.")

        return content.strip()

    except AIProviderError:
        raise
    except (RateLimitError, APIConnectionError, APIStatusError) as exc:
        raise AIProviderError(
            "The AI provider is temporarily unavailable. Please try again later."
        ) from exc
