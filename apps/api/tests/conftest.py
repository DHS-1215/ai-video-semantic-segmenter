import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.api.deps import get_db, get_object_storage_service
from app.db.base import Base
from app.main import app
from app.services.storage import StoredObject


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)


@pytest.fixture
def db_session_factory(db_engine):
    return sessionmaker(
        bind=db_engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )


@pytest.fixture
def db_session(db_session_factory) -> Session:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


class FakeStorageService:
    def __init__(self) -> None:
        self.uploads: list[dict[str, str | int]] = []
        self.deleted_objects: list[dict[str, str]] = []
        self.raise_on_upload = False
        self.raise_on_delete = False

    def upload_stream(
        self,
        *,
        video_id,
        filename: str,
        data,
        length: int,
        content_type: str | None = None,
    ) -> StoredObject:
        if self.raise_on_upload:
            raise RuntimeError("upload failed")

        object_name = f"videos/{video_id}/original/{filename}"
        bucket = "videos"
        self.uploads.append(
            {
                "video_id": str(video_id),
                "filename": filename,
                "length": length,
                "content_type": content_type or "",
                "bucket": bucket,
                "object_name": object_name,
            }
        )
        return StoredObject(
            bucket=bucket,
            object_name=object_name,
            url=f"http://storage.local/{bucket}/{object_name}",
        )

    def delete_object(self, bucket: str, object_name: str) -> None:
        if self.raise_on_delete:
            raise RuntimeError("delete failed")

        self.deleted_objects.append(
            {
                "bucket": bucket,
                "object_name": object_name,
            }
        )


@pytest.fixture
def fake_storage_service() -> FakeStorageService:
    return FakeStorageService()


@pytest.fixture
def client(db_session_factory, fake_storage_service: FakeStorageService) -> TestClient:
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_get_storage_service():
        return fake_storage_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_object_storage_service] = (
        override_get_storage_service
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
