from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    data_dir: Path = BACKEND_ROOT / "data"
    database_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    # 배포 전까지는 단일 사용자. 테이블에는 처음부터 user_id를 남겨둔다.
    default_user_id: str = "me"
    max_upload_mb: int = 50

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'reader.db'}"


settings = Settings()
