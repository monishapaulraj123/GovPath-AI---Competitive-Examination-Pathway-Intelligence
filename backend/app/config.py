import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        load_dotenv(BASE_DIR / ".env", override=False)
        self.APP_NAME: str = os.getenv("APP_NAME", "GovPath AI")
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "govpath-ai-dev-secret-key-2026-change-me")
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'govpath_ai.db').as_posix()}")

        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "")
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        self.LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

        self.ORCHESTRATOR_MAX_ITERATIONS: int = int(os.getenv("ORCHESTRATOR_MAX_ITERATIONS", "4"))
        self.ORCHESTRATOR_MAX_TOOL_CALLS: int = int(os.getenv("ORCHESTRATOR_MAX_TOOL_CALLS", "24"))
        self.ORCHESTRATOR_MAX_LLM_CALLS: int = int(os.getenv("ORCHESTRATOR_MAX_LLM_CALLS", "6"))
        self.ORCHESTRATOR_TIMEOUT_SECONDS: float = float(os.getenv("ORCHESTRATOR_TIMEOUT_SECONDS", "45.0"))
        self.ORCHESTRATOR_TOOL_TIMEOUT_SECONDS: float = float(os.getenv("ORCHESTRATOR_TOOL_TIMEOUT_SECONDS", "10.0"))
        self.ORCHESTRATOR_TOKEN_BUDGET: int = int(os.getenv("ORCHESTRATOR_TOKEN_BUDGET", "20000"))

        self.NEO4J_URI: str = os.getenv("NEO4J_URI", "")
        self.NEO4J_USER: str = os.getenv("NEO4J_USER", "")
        self.NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

        self.CORS_ORIGINS: list[str] = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
            ).split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
