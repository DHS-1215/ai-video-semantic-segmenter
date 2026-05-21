from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_object_storage_service
from app.core.constants import JOB_STATUS_PENDING, PROCESSING_JOB_TYPE_MOCK_PIPELINE
from app.main import app
from app.models import ProcessingJob, TranscriptSegment, Video


def test_upload_video_success_creates_video_and_job(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("demo.mp4", BytesIO(b"video-data"), "video/mp4")},
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["success"] is True
    assert payload["data"]["filename"] == "demo.mp4"
    assert payload["data"]["status"] == "pending"
    assert payload["data"]["original_url"].startswith("http://storage.local/videos/")
    assert len(fake_storage_service.uploads) == 1

    saved_video = db_session.get(Video, UUID(payload["data"]["video_id"]))
    assert saved_video is not None
    assert saved_video.filename == "demo.mp4"

    job = db_session.query(ProcessingJob).filter_by(video_id=saved_video.id).one()
    assert job.job_type == PROCESSING_JOB_TYPE_MOCK_PIPELINE
    assert job.status == JOB_STATUS_PENDING


def test_upload_video_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("empty.mp4", BytesIO(b""), "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "empty_file",
            "message": "Uploaded file is empty.",
        },
    }


def test_upload_video_rejects_invalid_extension(client: TestClient) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("demo.txt", BytesIO(b"not-a-video"), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "unsupported_file_type",
            "message": "Only mp4, mov, webm, and mkv uploads are supported.",
        },
    }


def test_upload_video_rejects_oversized_file(client: TestClient, monkeypatch) -> None:
    from app.api.routes import videos as videos_route_module

    settings = videos_route_module.get_settings()
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)

    response = client.post(
        "/api/videos/upload",
        files={"file": ("large.mp4", BytesIO(b"x" * (1024 * 1024 + 1)), "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "file_too_large",
            "message": "Uploaded file exceeds the 1 MB limit.",
        },
    }


def test_upload_video_storage_failure_does_not_create_db_rows(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
) -> None:
    fake_storage_service.raise_on_upload = True

    response = client.post(
        "/api/videos/upload",
        files={"file": ("broken.mp4", BytesIO(b"video-data"), "video/mp4")},
    )

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "storage_upload_failed",
            "message": "Failed to upload video file.",
        },
    }
    assert db_session.scalar(select(func.count(Video.id))) == 0
    assert db_session.scalar(select(func.count(ProcessingJob.id))) == 0
    assert fake_storage_service.deleted_objects == []


def test_upload_video_db_commit_failure_attempts_storage_cleanup(
    db_session_factory,
    fake_storage_service,
    monkeypatch,
) -> None:
    class CommitFailingSession:
        def __init__(self, real_session: Session) -> None:
            self._real_session = real_session
            self.rollback_called = False

        def add_all(self, items) -> None:
            self._real_session.add_all(items)

        def commit(self) -> None:
            raise RuntimeError("commit failed")

        def rollback(self) -> None:
            self.rollback_called = True
            self._real_session.rollback()

        def refresh(self, instance) -> None:
            self._real_session.refresh(instance)

        def close(self) -> None:
            self._real_session.close()

    holder: dict[str, CommitFailingSession] = {}

    def override_get_db():
        wrapped_session = CommitFailingSession(db_session_factory())
        holder["session"] = wrapped_session
        try:
            yield wrapped_session
        finally:
            wrapped_session.close()

    def override_get_storage_service():
        return fake_storage_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_object_storage_service] = (
        override_get_storage_service
    )

    with TestClient(app) as failing_client:
        response = failing_client.post(
            "/api/videos/upload",
            files={"file": ("commit-fail.mp4", BytesIO(b"video-data"), "video/mp4")},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_create_failed",
            "message": "Failed to create video record.",
        },
    }
    assert holder["session"].rollback_called is True
    assert len(fake_storage_service.uploads) == 1
    assert fake_storage_service.deleted_objects == [
        {
            "bucket": "videos",
            "object_name": fake_storage_service.uploads[0]["object_name"],
        }
    ]


def test_get_videos_returns_list_in_descending_created_order(
    client: TestClient,
    db_session: Session,
) -> None:
    older_video = Video(
        id=uuid4(),
        filename="older.mp4",
        original_url="http://storage.local/videos/older.mp4",
        preview_url=None,
        duration_seconds=None,
        status="pending",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    newer_video = Video(
        id=uuid4(),
        filename="newer.mp4",
        original_url="http://storage.local/videos/newer.mp4",
        preview_url=None,
        duration_seconds=None,
        status="pending",
        created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    db_session.add_all([older_video, newer_video])
    db_session.commit()

    response = client.get("/api/videos")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert [item["filename"] for item in payload["data"]] == ["newer.mp4", "older.mp4"]


def test_get_video_returns_detail(client: TestClient, db_session: Session) -> None:
    video = Video(
        id=uuid4(),
        filename="detail.mp4",
        original_url="http://storage.local/videos/detail.mp4",
        preview_url=None,
        duration_seconds=42.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    response = client.get(f"/api/videos/{video.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["id"] == str(video.id)
    assert payload["data"]["filename"] == "detail.mp4"


def test_get_missing_video_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/videos/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_not_found",
            "message": "Video not found.",
        },
    }


def test_get_video_transcript_returns_empty_array_when_no_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="empty-transcript.mp4",
        original_url="http://storage.local/videos/empty-transcript.mp4",
        preview_url=None,
        duration_seconds=None,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    response = client.get(f"/api/videos/{video.id}/transcript")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": [],
    }


def test_get_video_transcript_returns_segments_in_sort_order(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="has-transcript.mp4",
        original_url="http://storage.local/videos/has-transcript.mp4",
        preview_url=None,
        duration_seconds=None,
        status="pending",
    )
    later_segment = TranscriptSegment(
        video=video,
        start_time=5.0,
        end_time=10.0,
        speaker=None,
        text="Second line",
        sort_order=2,
        created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    earlier_segment = TranscriptSegment(
        video=video,
        start_time=0.0,
        end_time=4.0,
        speaker="Speaker 1",
        text="First line",
        sort_order=1,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([video, later_segment, earlier_segment])
    db_session.commit()

    response = client.get(f"/api/videos/{video.id}/transcript")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert [item["sort_order"] for item in payload["data"]] == [1, 2]
