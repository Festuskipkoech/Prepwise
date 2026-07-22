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
    embedding_model: str = "jina-embeddings-v4"
    embedding_dimensions: int = 2048
    jina_api_key: str

    # Conversation compression
    compression_threshold_prep: int = 12000
    compression_threshold_job: int = 8000
    compression_threshold_document: int = 8000
    compression_threshold_tracker: int = 8000
    compression_tail_turns_prep: int = 6
    compression_tail_turns_job: int = 4
    compression_tail_turns_document: int = 4
    compression_tail_turns_tracker: int = 4

    # Job Search
    serp_api_key: str

    # Auth
    jwt_access_secret: str
    jwt_refresh_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expiry_minutes: int = 15
    jwt_refresh_expiry_days: int = 30
    bcrypt_cost: int = 12

    # Tests
    test_resume_path: str
    test_user_email: str
    test_user_password: str
    test_user_name: str

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def langgraph_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@localhost:5434/{self.postgres_db}"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()