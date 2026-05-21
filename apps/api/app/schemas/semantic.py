from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SemanticSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    start_time: float
    end_time: float
    title: str
    summary: str
    topic: str
    keywords: list[str]
    transcript_text: str
    confidence: float
    reason: str
    sort_order: int
    created_at: datetime
    updated_at: datetime
