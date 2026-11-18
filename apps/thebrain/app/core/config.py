from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("JULIAN_APP_NAME", "TheBrain / Julian")
    host: str = os.getenv("JULIAN_HOST", "127.0.0.1")
    port: int = int(os.getenv("JULIAN_PORT", "8080"))
    data_dir: Path = Path(os.getenv("JULIAN_DATA_DIR", str(ROOT / "data"))).expanduser()
    database_path: str = os.getenv("JULIAN_DATABASE_PATH", "")
    llm_base_url: str = os.getenv("JULIAN_LLM_BASE_URL", "http://127.0.0.1:8081/v1")
    llm_model: str = os.getenv("JULIAN_LLM_MODEL", "local-model")
    llm_api_key: str = os.getenv("JULIAN_LLM_API_KEY", "not-needed")
    llm_timeout_seconds: float = float(os.getenv("JULIAN_LLM_TIMEOUT_SECONDS", "120"))
    llm_enabled: bool = _env_bool("JULIAN_LLM_ENABLED", True)
    web_search_enabled: bool = _env_bool("JULIAN_WEB_SEARCH_ENABLED", True)
    web_search_timeout_seconds: float = float(os.getenv("JULIAN_WEB_SEARCH_TIMEOUT_SECONDS", "12"))
    max_upload_bytes: int = int(os.getenv("JULIAN_MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
    max_context_chars: int = int(os.getenv("JULIAN_MAX_CONTEXT_CHARS", "24000"))
    request_timeout_seconds: float = float(os.getenv("JULIAN_REQUEST_TIMEOUT_SECONDS", "180"))
    allow_local_file_urls: bool = _env_bool("JULIAN_ALLOW_LOCAL_FILE_URLS", False)

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.resolve()

    @property
    def resolved_database_path(self) -> Path:
        if self.database_path.strip():
            return Path(self.database_path).expanduser().resolve()
        return self.resolved_data_dir / "julian.sqlite3"


settings = Settings()
