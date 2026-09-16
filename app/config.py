import logging
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent   # app/config.py -> app/ -> repo root
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"))

    llm_backend: str = "gemini"
    gemini_api_key: str | None = None
    model_name: str = "gemini-3.1-flash-lite"
    ollama_model: str = "llama3.1"
    ollama_url: str = "http://127.0.0.1:11434"
    retrieval_k: int = 3


settings = Settings()


def setup_logging(level: str = "ERROR"):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(BASE_DIR / "coach.log")],
    )