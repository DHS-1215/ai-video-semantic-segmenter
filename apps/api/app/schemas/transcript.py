from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    start_time: float
    end_time: float
    speaker: str | None
    text: str
    sort_order: int
    created_at: datetime
