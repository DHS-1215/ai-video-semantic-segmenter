from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    project_name: str = "ai-video-semantic-segmenter"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/semantic_segmenter"
    )
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket_videos: str = "videos"
    minio_secure: bool = False
    max_upload_size_mb: int = 500
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    allowed_video_extensions: list[str] = Field(
        default_factory=lambda: ["mp4", "mov", "webm", "mkv"]
    )
    asr_provider: str = "mock"
    faster_whisper_model_size: str = "base"
    faster_whisper_device: str = "cpu"
    faster_whisper_compute_type: str = "int8"
    faster_whisper_language: str = "zh"
    faster_whisper_beam_size: int = 5
    faster_whisper_vad_filter: bool = False
    semantic_segmenter_provider: str = "mock"
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4-flash"
    zhipu_temperature: float = 0.2
    zhipu_timeout_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
