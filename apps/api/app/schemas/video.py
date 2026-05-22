from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VideoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    original_url: str
    preview_url: str | None
    duration_seconds: float | None
    status: str
    created_at: datetime
    updated_at: datetime


class VideoResponse(VideoListItem):
    original_object_name: str | None
    audio_url: str | None
    audio_object_name: str | None


class VideoUploadResponse(BaseModel):
    video_id: UUID
    status: str
    filename: str
    original_url: str
