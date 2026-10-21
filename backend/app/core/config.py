from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Omnigesi // Dynamic Multi-Agent AIaaS"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = "postgresql+asyncpg://omnigensi:omnigensi_secret@localhost:5435/omnigensi"
    REDIS_URL: str = "redis://localhost:6382/0"
    ENCRYPTION_KEY: str = "eGZqX2tFMUdBQ2dMcm1xek1tV2M0X2V2WVBNT2pUZnU4Wms9"
    WORKSPACE_ROOT: str = "./workspace"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

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
