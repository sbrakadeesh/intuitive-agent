from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    use_mock_ollama: bool = True

    # SQLite (LangGraph checkpoints and incident records)
    db_path: str = "./triage.db"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()
