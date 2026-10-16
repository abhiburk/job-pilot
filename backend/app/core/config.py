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

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str
    smtp_from_name: str = "JobPilot"
    smtp_use_tls: bool = False
    smtp_start_tls: bool = True

    job_digest_min_score: float = 70
    job_digest_max_jobs: int = 10
    job_digest_timezone: str = "Asia/Kolkata"


settings = Settings()