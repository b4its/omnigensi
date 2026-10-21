from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Omnigesi // Dynamic Multi-Agent AIaaS"
    APP_VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://omnigensi:omnigensi_secret@localhost:5558/omnigensi"
    REDIS_URL: str = "redis://localhost:6505/0"
    ENCRYPTION_KEY: str = "eGZqX2tFMUdBQ2dMcm1xek1tV2M0X2V2WVBNT2pUZnU4Wms9"
    WORKSPACE_ROOT: str = "./workspace"

    # Comma-separated list of allowed browser origins. Native mobile clients
    # are not subject to CORS, but the web UI and mobile WebViews are.
    CORS_ORIGINS: str = "http://localhost:5296,http://localhost:3123,http://127.0.0.1:5296"

    # Regex allowing LAN/mobile development hosts (e.g. http://192.168.1.10:5296).
    # Applies to the web UI loaded from a phone/tablet on the same network.
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"

    # Public base URL that mobile clients should use to reach this backend.
    # Leave empty to auto-detect from the incoming request.
    PUBLIC_BASE_URL: str = ""

    # --- Authentication ---------------------------------------------------
    # Single shared operator password. This is deliberately simple: one
    # password guards the whole instance, no users or roles.
    APP_PASSWORD: str = "123"
    # Set AUTH_ENABLED=false only for local experiments where a login prompt
    # would get in the way.
    AUTH_ENABLED: bool = True
    # Secret used to sign session tokens. Falls back to ENCRYPTION_KEY so a
    # single deployment secret is enough.
    AUTH_TOKEN_SECRET: str = ""
    # Session lifetime in seconds (default 7 days).
    AUTH_TOKEN_TTL_SECONDS: int = 60 * 60 * 24 * 7
    # Cookie name holding the signed session token.
    AUTH_COOKIE_NAME: str = "omnigensi_session"
    # Send the cookie only over HTTPS. Enable when serving behind TLS.
    AUTH_COOKIE_SECURE: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def workspace_path(self) -> Path:
        p = Path(self.WORKSPACE_ROOT).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
