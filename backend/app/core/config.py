from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


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
    allowed_origins: list[str]

    # Database
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url: str

    # Qdrant
    qdrant_host: str  
    qdrant_port: int  

    # LLM
    anthropic_api_key: str
    openai_api_key:str
    llm_sonnet_model: str  
    llm_haiku_model: str  
    # Embeddings
    jina_api_key: str

    # Job Search
    serp_api_key: str

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str  
    jwt_expiry_days: int  

    # Profile
    profile_path: str 

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()