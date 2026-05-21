from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.storage import ObjectStorageService, get_storage_service


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_object_storage_service() -> ObjectStorageService:
    return get_storage_service()
