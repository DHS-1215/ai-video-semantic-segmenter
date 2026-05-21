from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    video_id: UUID
    job_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MockPipelineResponse(BaseModel):
    video_id: UUID
    transcript_segments_created: int
    semantic_segments_created: int
    job_status: str
