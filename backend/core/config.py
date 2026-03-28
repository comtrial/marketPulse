from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    database_url: str = "postgresql+asyncpg://mp_user:mp_password@localhost:5432/marketpulse"
    database_url_sync: str = "postgresql+psycopg://mp_user:mp_password@localhost:5432/marketpulse"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "mp_neo4j_password"

    # Anthropic
    anthropic_api_key: str = ""

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Model routing
    fast_model: str = "claude-haiku-4-5-20251001"
    smart_model: str = "claude-sonnet-4-20250514"

    # App
    env: str = "dev"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
