from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env(path: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    else:
        load_dotenv(path)


load_project_env(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    biographies_dir: Path = PROJECT_ROOT / "data" / "biographies"

    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "change-this-password")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2-pro:free")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    llm_cache_enabled: bool = os.getenv("LLM_CACHE_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
    llm_cache_dir: Path = PROJECT_ROOT / ".cache" / "llm"


settings = Settings()