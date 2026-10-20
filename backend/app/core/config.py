from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
class Settings(BaseSettings):
    app_name: str = "JobPilot"
    # "local" for development; anything else enables production defaults
    # (Secure cookies, HSTS, certificate validation, hidden API docs).
    app_env: str = "local"
    debug: bool = True

    database_url: str
    redis_url: str

    # SQL echo logs statement parameters (password and token hashes), so it
    # is controlled separately from DEBUG and off by default.
    sql_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
    # None means: validate certificates everywhere except APP_ENV=local.
    smtp_validate_certs: bool | None = None

    job_digest_min_score: float = 70
    job_digest_max_jobs: int = 10
    job_digest_timezone: str = "Asia/Kolkata"

    job_digest_min_coverage: float = 60.0

    # Comma-separated job source keys to switch off, e.g. "remotive".
    job_sources_disabled: str = ""

    gemini_api_key: str | None = None
    gemini_embedding_model: str = "gemini-embedding-2"

    # Authentication
    registration_enabled: bool = True
    session_cookie_name: str = "jobpilot_session"
    session_ttl_hours: int = 24 * 7
    # None means: Secure cookies everywhere except APP_ENV=local.
    session_cookie_secure: bool | None = None
    session_cookie_samesite: str = "lax"
    password_reset_ttl_minutes: int = 60
    login_max_failures: int = 5
    login_failure_window_seconds: int = 15 * 60

    # Comma-separated list of browser origins allowed to call the API.
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Public URL of the frontend, used in password-reset emails.
    frontend_url: str = "http://localhost:5173"

    @property
    def is_local(self) -> bool:
        return self.app_env.lower() in {"local", "development", "dev", "test"}

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return not self.is_local

    @property
    def validate_smtp_certs(self) -> bool:
        if self.smtp_validate_certs is not None:
            return self.smtp_validate_certs
        return not self.is_local

    @property
    def disabled_job_sources(self) -> set[str]:
        return {
            key.strip().lower()
            for key in self.job_sources_disabled.split(",")
            if key.strip()
        }

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
