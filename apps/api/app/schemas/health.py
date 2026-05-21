from pydantic import BaseModel


class HealthPayload(BaseModel):
    status: str
    service: str
    environment: str


class HealthResponse(BaseModel):
    success: bool
    data: HealthPayload
