from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobPilot"
    app_env: str = "local"
    debug: bool = True

    database_url: str
    redis_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"


settings = Settings()