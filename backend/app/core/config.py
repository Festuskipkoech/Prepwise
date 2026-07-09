from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_env: str
    app_host: str
    app_port: int
    allowed_origins: str

    # Database
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url: str

    # Redis
    redis_url: str
    redis_password: str
    redis_db_auth: int
    redis_db_pubsub: int
    redis_db_cache: int
    redis_db_ratelimit: int

    # Qdrant
    qdrant_host: str
    qdrant_port: int

    # LLM
    anthropic_api_key: str
    openai_api_key: str
    llm_large_model: str
    llm_small_model: str

    # Embeddings
    jina_api_key: str

    # Job Search
    serp_api_key: str

    # Auth
    jwt_access_secret: str
    jwt_refresh_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expiry_minutes: int = 15
    jwt_refresh_expiry_days: int = 30
    bcrypt_cost: int = 12

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()