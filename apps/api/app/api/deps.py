from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.asr import ASRProvider, create_asr_provider
from app.services.semantic_segmenter import (
    SemanticSegmenterProvider,
    create_semantic_segmenter_provider,
)
from app.services.storage import ObjectStorageService, get_storage_service


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_object_storage_service() -> ObjectStorageService:
    return get_storage_service()


def get_asr_provider() -> ASRProvider:
    return create_asr_provider(get_settings())


def get_semantic_segmenter_provider() -> SemanticSegmenterProvider:
    return create_semantic_segmenter_provider(get_settings())
