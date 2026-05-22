from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_asr_provider,
    get_db,
    get_object_storage_service,
    get_semantic_segmenter_provider,
)
from app.core.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
    PROCESSING_JOB_TYPE_MOCK_PIPELINE,
    PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
    PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
)
from app.main import app
from app.models import ProcessingJob, SemanticSegment, TranscriptSegment, Video
from app.services import audio_extraction as audio_extraction_service
from app.services.asr import TranscriptResultSegment


def _build_transcript_segments(
    video: Video,
    entries: list[tuple[float, float, str | None, str]],
) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            video=video,
            start_time=start_time,
            end_time=end_time,
            speaker=speaker,
            text=text,
            sort_order=sort_order,
        )
        for sort_order, (start_time, end_time, speaker, text) in enumerate(
            entries,
            start=1,
        )
    ]


def _semantic_test_transcript_entries() -> list[tuple[float, float, str | None, str]]:
    return [
        (0.0, 36.0, "林晓", "今天先从品牌团队处理长视频内容的现状讲起，我们每天都要整理发布会和访谈视频。"),
        (36.0, 78.0, "周明", "现在最大的成本还是人工回看视频，想找到一个完整话题往往要拖很多次时间轴。"),
        (78.0, 122.0, "林晓", "如果只有零散片段，没有上下文，品牌审核和后续剪辑都很难判断内容是否完整。"),
        (122.0, 164.0, "周明", "所以第一步必须先把音频提取出来，再把说话内容整理成可阅读的转写文本。"),
        (164.0, 208.0, "林晓", "有了转写之后，团队才能基于文本去检索关键词，而不是反复回听整段音频。"),
        (208.0, 252.0, "周明", "接下来语义分段要解决的问题，是把连续讨论品牌策略的内容归在同一个内容单元。"),
        (252.0, 294.0, "林晓", "如果系统能给出每段标题、摘要和关键词，审核同学会更容易理解这段内容在讲什么。"),
        (294.0, 338.0, "周明", "这些结构化元数据也能帮助后续团队做素材复用，比如官网摘要、案例整理和社媒脚本。"),
        (338.0, 380.0, "林晓", "这一轮我们先用 Mock provider 跑通接口和数据结构，确认前后端能完整消费语义分段结果。"),
        (380.0, 420.0, "周明", "等到抽象稳定之后，再替换成真实 LLM 服务去判断主题边界和分段理由。"),
    ]


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
    assert saved_video.original_object_name == "videos/" + str(saved_video.id) + "/original/demo.mp4"

    job = db_session.query(ProcessingJob).filter_by(video_id=saved_video.id).one()
    assert job.job_type == PROCESSING_JOB_TYPE_MOCK_PIPELINE
    assert job.status == JOB_STATUS_PENDING


def test_upload_video_sets_original_object_name(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("source.mov", BytesIO(b"video-data"), "video/quicktime")},
    )

    assert response.status_code == 201
    payload = response.json()
    saved_video = db_session.get(Video, UUID(payload["data"]["video_id"]))

    assert saved_video is not None
    assert saved_video.original_object_name is not None
    assert saved_video.original_object_name.endswith("/original/source.mov")


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
        original_object_name="videos/example/original/detail.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
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
    assert payload["data"]["original_object_name"] == "videos/example/original/detail.mp4"
    assert payload["data"]["audio_url"] == (
        "http://storage.local/videos/videos/example/audio/audio.wav"
    )
    assert payload["data"]["audio_object_name"] == "videos/example/audio/audio.wav"


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


def test_extract_audio_requires_video(client: TestClient) -> None:
    response = client.post(f"/api/videos/{uuid4()}/jobs/extract-audio")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_not_found",
            "message": "Video not found.",
        },
    }


def test_transcribe_audio_requires_video(client: TestClient) -> None:
    response = client.post(f"/api/videos/{uuid4()}/jobs/transcribe-audio")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_not_found",
            "message": "Video not found.",
        },
    }


def test_extract_audio_requires_original_object_name(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="legacy.mp4",
        original_url="http://storage.local/videos/legacy.mp4",
        original_object_name=None,
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/extract-audio")

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "missing_original_object",
            "message": "Video original object is missing.",
        },
    }
    assert (
        db_session.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.video_id == video.id,
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
            )
        )
        == 0
    )


def test_transcribe_audio_requires_audio_object_name(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="no-audio.mp4",
        original_url="http://storage.local/videos/no-audio.mp4",
        original_object_name="videos/example/original/no-audio.mp4",
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "missing_audio_object",
            "message": "Video audio object is missing.",
        },
    }
    assert (
        db_session.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.video_id == video.id,
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
            )
        )
        == 0
    )


def test_extract_audio_success_updates_video_and_job(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
    monkeypatch,
) -> None:
    video = Video(
        id=uuid4(),
        filename="demo.mp4",
        original_url="http://storage.local/videos/demo.mp4",
        original_object_name=f"videos/{uuid4()}/original/demo.mp4",
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    def fake_extract_audio(_: str, output_audio_path: str) -> float:
        Path(output_audio_path).write_bytes(b"wav-data")
        return 42.5

    monkeypatch.setattr(
        audio_extraction_service.ffmpeg_service,
        "extract_audio",
        fake_extract_audio,
    )

    response = client.post(f"/api/videos/{video.id}/jobs/extract-audio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "video_id": str(video.id),
        "job_status": JOB_STATUS_COMPLETED,
        "audio_url": f"http://storage.local/videos/videos/{video.id}/audio/audio.wav",
        "audio_object_name": f"videos/{video.id}/audio/audio.wav",
        "duration_seconds": 42.5,
    }
    assert len(fake_storage_service.downloads) == 1
    assert fake_storage_service.downloads[0]["bucket"] == "videos"
    assert fake_storage_service.downloads[0]["object_name"] == video.original_object_name

    db_session.expire_all()
    saved_video = db_session.get(Video, video.id)
    assert saved_video is not None
    assert saved_video.audio_url == payload["data"]["audio_url"]
    assert saved_video.audio_object_name == payload["data"]["audio_object_name"]
    assert saved_video.duration_seconds == 42.5

    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
        )
    ).one()
    assert job.status == JOB_STATUS_COMPLETED
    assert job.error_message is None
    assert fake_storage_service.uploads[-1]["object_name"] == (
        f"videos/{video.id}/audio/audio.wav"
    )


def test_transcribe_audio_with_mock_provider_still_works(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
) -> None:
    video = Video(
        id=uuid4(),
        filename="transcribe.mp4",
        original_url="http://storage.local/videos/transcribe.mp4",
        original_object_name="videos/example/original/transcribe.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "video_id": str(video.id),
        "transcript_segments_created": 10,
        "job_status": JOB_STATUS_COMPLETED,
    }

    transcript_segments = db_session.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.video_id == video.id)
        .order_by(TranscriptSegment.sort_order.asc())
    ).all()
    assert len(transcript_segments) == 10
    assert [segment.sort_order for segment in transcript_segments] == list(
        range(1, 11)
    )
    assert transcript_segments[0].start_time == 0.0
    assert transcript_segments[-1].end_time == 420.0
    assert all(segment.text.strip() for segment in transcript_segments)
    assert fake_storage_service.downloads == []

    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
        )
    ).one()
    assert job.status == JOB_STATUS_COMPLETED
    assert job.error_message is None


def test_transcribe_audio_is_idempotent_for_transcripts(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="transcribe-idempotent.mp4",
        original_url="http://storage.local/videos/transcribe-idempotent.mp4",
        original_object_name="videos/example/original/transcribe-idempotent.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    first_response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")
    second_response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert (
        db_session.scalar(
            select(func.count(TranscriptSegment.id)).where(
                TranscriptSegment.video_id == video.id
            )
        )
        == 10
    )
    assert (
        db_session.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.video_id == video.id,
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
            )
        )
        == 1
    )


def test_transcribe_audio_provider_failure_marks_job_failed(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="provider-fail.mp4",
        original_url="http://storage.local/videos/provider-fail.mp4",
        original_object_name="videos/example/original/provider-fail.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    class FailingASRProvider:
        def transcribe(self, audio_object_name: str):
            raise RuntimeError(f"provider failed for {audio_object_name}")

    app.dependency_overrides[get_asr_provider] = lambda: FailingASRProvider()
    try:
        response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")
    finally:
        app.dependency_overrides.pop(get_asr_provider, None)

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "audio_transcription_failed",
            "message": "Failed to transcribe audio.",
        },
    }
    assert (
        db_session.scalar(
            select(func.count(TranscriptSegment.id)).where(
                TranscriptSegment.video_id == video.id
            )
        )
        == 0
    )

    db_session.expire_all()
    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
        )
    ).one()
    assert job.status == JOB_STATUS_FAILED
    assert job.error_message is not None
    assert "provider failed" in job.error_message


def test_transcribe_audio_provider_requiring_local_file_downloads_audio(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
) -> None:
    video = Video(
        id=uuid4(),
        filename="local-asr.mp4",
        original_url="http://storage.local/videos/local-asr.mp4",
        original_object_name="videos/example/original/local-asr.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=64.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    class LocalFileASRProvider:
        requires_local_file = True

        def __init__(self) -> None:
            self.audio_path: str | None = None

        def transcribe(self, audio_path: str):
            self.audio_path = audio_path
            assert Path(audio_path).exists()
            return [
                TranscriptResultSegment(
                    start_time=0.0,
                    end_time=8.0,
                    speaker="Speaker 1",
                    text="本地音频文件转写第一段",
                ),
                TranscriptResultSegment(
                    start_time=8.0,
                    end_time=16.0,
                    speaker="Speaker 1",
                    text="本地音频文件转写第二段",
                ),
            ]

    provider = LocalFileASRProvider()
    app.dependency_overrides[get_asr_provider] = lambda: provider
    try:
        response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")
    finally:
        app.dependency_overrides.pop(get_asr_provider, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "video_id": str(video.id),
        "transcript_segments_created": 2,
        "job_status": JOB_STATUS_COMPLETED,
    }
    assert provider.audio_path is not None
    assert len(fake_storage_service.downloads) == 1
    assert fake_storage_service.downloads[0]["bucket"] == "videos"
    assert fake_storage_service.downloads[0]["object_name"] == video.audio_object_name

    transcript_segments = db_session.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.video_id == video.id)
        .order_by(TranscriptSegment.sort_order.asc())
    ).all()
    assert [segment.sort_order for segment in transcript_segments] == [1, 2]
    assert [segment.text for segment in transcript_segments] == [
        "本地音频文件转写第一段",
        "本地音频文件转写第二段",
    ]


def test_transcribe_audio_local_provider_failure_marks_job_failed(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
) -> None:
    video = Video(
        id=uuid4(),
        filename="local-asr-fail.mp4",
        original_url="http://storage.local/videos/local-asr-fail.mp4",
        original_object_name="videos/example/original/local-asr-fail.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=64.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    class FailingLocalFileASRProvider:
        requires_local_file = True

        def transcribe(self, audio_path: str):
            assert Path(audio_path).exists()
            raise RuntimeError(f"local asr failed for {audio_path}")

    app.dependency_overrides[get_asr_provider] = lambda: FailingLocalFileASRProvider()
    try:
        response = client.post(f"/api/videos/{video.id}/jobs/transcribe-audio")
    finally:
        app.dependency_overrides.pop(get_asr_provider, None)

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "audio_transcription_failed",
            "message": "Failed to transcribe audio.",
        },
    }
    assert len(fake_storage_service.downloads) == 1
    assert (
        db_session.scalar(
            select(func.count(TranscriptSegment.id)).where(
                TranscriptSegment.video_id == video.id
            )
        )
        == 0
    )

    db_session.expire_all()
    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
        )
    ).one()
    assert job.status == JOB_STATUS_FAILED
    assert job.error_message is not None
    assert "local asr failed" in job.error_message


def test_semantic_segmentation_requires_video(client: TestClient) -> None:
    response = client.post(f"/api/videos/{uuid4()}/jobs/semantic-segmentation")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_not_found",
            "message": "Video not found.",
        },
    }


def test_semantic_segmentation_requires_transcript_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="no-transcript.mp4",
        original_url="http://storage.local/videos/no-transcript.mp4",
        original_object_name="videos/example/original/no-transcript.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/semantic-segmentation")

    assert response.status_code == 400
    assert response.json() == {
        "success": False,
        "error": {
            "code": "missing_transcript_segments",
            "message": "Transcript segments are missing.",
        },
    }
    assert (
        db_session.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.video_id == video.id,
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
            )
        )
        == 0
    )


def test_semantic_segmentation_success_creates_semantic_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="semantic-success.mp4",
        original_url="http://storage.local/videos/semantic-success.mp4",
        original_object_name="videos/example/original/semantic-success.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    transcript_segments = _build_transcript_segments(
        video,
        _semantic_test_transcript_entries(),
    )
    db_session.add_all([video, *transcript_segments])
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/semantic-segmentation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "video_id": str(video.id),
        "semantic_segments_created": 5,
        "job_status": JOB_STATUS_COMPLETED,
    }

    semantic_segments = db_session.scalars(
        select(SemanticSegment)
        .where(SemanticSegment.video_id == video.id)
        .order_by(SemanticSegment.sort_order.asc())
    ).all()
    assert len(semantic_segments) == 5
    assert [segment.sort_order for segment in semantic_segments] == [1, 2, 3, 4, 5]
    assert semantic_segments[0].start_time == 0.0
    assert semantic_segments[-1].end_time == 420.0
    assert all(segment.transcript_text.strip() for segment in semantic_segments)
    assert "品牌团队处理长视频内容" in semantic_segments[0].transcript_text
    assert all(0.0 <= segment.confidence <= 1.0 for segment in semantic_segments)

    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
        )
    ).one()
    assert job.status == JOB_STATUS_COMPLETED
    assert job.error_message is None


def test_semantic_segmentation_is_idempotent_for_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="semantic-idempotent.mp4",
        original_url="http://storage.local/videos/semantic-idempotent.mp4",
        original_object_name="videos/example/original/semantic-idempotent.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    transcript_segments = _build_transcript_segments(
        video,
        _semantic_test_transcript_entries(),
    )
    db_session.add_all([video, *transcript_segments])
    db_session.commit()

    first_response = client.post(f"/api/videos/{video.id}/jobs/semantic-segmentation")
    second_response = client.post(f"/api/videos/{video.id}/jobs/semantic-segmentation")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert (
        db_session.scalar(
            select(func.count(SemanticSegment.id)).where(
                SemanticSegment.video_id == video.id
            )
        )
        == 5
    )
    assert (
        db_session.scalar(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.video_id == video.id,
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
            )
        )
        == 1
    )


def test_semantic_segmentation_provider_failure_marks_job_failed(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="semantic-provider-fail.mp4",
        original_url="http://storage.local/videos/semantic-provider-fail.mp4",
        original_object_name="videos/example/original/semantic-provider-fail.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=420.0,
        status="pending",
    )
    transcript_segments = _build_transcript_segments(
        video,
        _semantic_test_transcript_entries(),
    )
    db_session.add_all([video, *transcript_segments])
    db_session.commit()

    class FailingSegmenterProvider:
        def segment(self, transcript_segments: list[TranscriptSegment]):
            raise RuntimeError(f"provider failed for {len(transcript_segments)} segments")

    app.dependency_overrides[get_semantic_segmenter_provider] = (
        lambda: FailingSegmenterProvider()
    )
    try:
        response = client.post(f"/api/videos/{video.id}/jobs/semantic-segmentation")
    finally:
        app.dependency_overrides.pop(get_semantic_segmenter_provider, None)

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "semantic_segmentation_failed",
            "message": "Failed to generate semantic segments.",
        },
    }
    assert (
        db_session.scalar(
            select(func.count(SemanticSegment.id)).where(
                SemanticSegment.video_id == video.id
            )
        )
        == 0
    )

    db_session.expire_all()
    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
        )
    ).one()
    assert job.status == JOB_STATUS_FAILED
    assert job.error_message is not None
    assert "provider failed" in job.error_message


def test_semantic_segmentation_with_short_transcript_still_creates_segment(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="semantic-short.mp4",
        original_url="http://storage.local/videos/semantic-short.mp4",
        original_object_name="videos/example/original/semantic-short.mp4",
        preview_url=None,
        audio_url="http://storage.local/videos/videos/example/audio/audio.wav",
        audio_object_name="videos/example/audio/audio.wav",
        duration_seconds=48.0,
        status="pending",
    )
    transcript_segments = _build_transcript_segments(
        video,
        [
            (
                0.0,
                48.0,
                "林晓",
                "这是一段简短的品牌视频说明，但依然需要生成一个完整的语义段结果。",
            )
        ],
    )
    db_session.add_all([video, *transcript_segments])
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/semantic-segmentation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == {
        "video_id": str(video.id),
        "semantic_segments_created": 1,
        "job_status": JOB_STATUS_COMPLETED,
    }

    semantic_segments = db_session.scalars(
        select(SemanticSegment)
        .where(SemanticSegment.video_id == video.id)
        .order_by(SemanticSegment.sort_order.asc())
    ).all()
    assert len(semantic_segments) == 1
    assert semantic_segments[0].sort_order == 1
    assert semantic_segments[0].transcript_text.strip()
    assert 0.0 <= semantic_segments[0].confidence <= 1.0


def test_extract_audio_storage_download_failure_marks_job_failed(
    client: TestClient,
    db_session: Session,
    fake_storage_service,
) -> None:
    video = Video(
        id=uuid4(),
        filename="download-fail.mp4",
        original_url="http://storage.local/videos/download-fail.mp4",
        original_object_name=f"videos/{uuid4()}/original/download-fail.mp4",
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()
    fake_storage_service.raise_on_download = True

    response = client.post(f"/api/videos/{video.id}/jobs/extract-audio")

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "audio_extraction_failed",
            "message": "Failed to extract audio.",
        },
    }

    db_session.expire_all()
    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
        )
    ).one()
    saved_video = db_session.get(Video, video.id)
    assert saved_video is not None
    assert saved_video.audio_url is None
    assert saved_video.audio_object_name is None
    assert saved_video.duration_seconds is None
    assert job.status == JOB_STATUS_FAILED
    assert job.error_message is not None
    assert "download failed" in job.error_message


def test_extract_audio_ffmpeg_failure_marks_job_failed(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    video = Video(
        id=uuid4(),
        filename="ffmpeg-fail.mp4",
        original_url="http://storage.local/videos/ffmpeg-fail.mp4",
        original_object_name=f"videos/{uuid4()}/original/ffmpeg-fail.mp4",
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status="pending",
    )
    db_session.add(video)
    db_session.commit()

    def fake_extract_audio(_: str, __: str) -> float:
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(
        audio_extraction_service.ffmpeg_service,
        "extract_audio",
        fake_extract_audio,
    )

    response = client.post(f"/api/videos/{video.id}/jobs/extract-audio")

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "audio_extraction_failed",
            "message": "Failed to extract audio.",
        },
    }

    db_session.expire_all()
    job = db_session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.video_id == video.id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
        )
    ).one()
    assert job.status == JOB_STATUS_FAILED
    assert job.error_message is not None
    assert "ffmpeg exploded" in job.error_message


def test_extract_audio_db_commit_failure_cleans_uploaded_audio(
    db_session_factory,
    fake_storage_service,
    monkeypatch,
) -> None:
    seed_session = db_session_factory()
    video_id = uuid4()
    video = Video(
        id=video_id,
        filename="commit-fail.mp4",
        original_url="http://storage.local/videos/commit-fail.mp4",
        original_object_name=f"videos/{uuid4()}/original/commit-fail.mp4",
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status="pending",
    )
    seed_session.add(video)
    seed_session.commit()
    seed_session.close()

    def fake_extract_audio(_: str, output_audio_path: str) -> float:
        Path(output_audio_path).write_bytes(b"wav-data")
        return 91.2

    monkeypatch.setattr(
        audio_extraction_service.ffmpeg_service,
        "extract_audio",
        fake_extract_audio,
    )

    class SecondCommitFailingSession:
        def __init__(self, real_session: Session) -> None:
            self._real_session = real_session
            self.commit_calls = 0

        def commit(self) -> None:
            self.commit_calls += 1
            if self.commit_calls == 2:
                raise RuntimeError("final commit failed")
            self._real_session.commit()

        def __getattr__(self, name: str):
            return getattr(self._real_session, name)

    holder: dict[str, SecondCommitFailingSession] = {}

    def override_get_db():
        wrapped_session = SecondCommitFailingSession(db_session_factory())
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
        response = failing_client.post(f"/api/videos/{video_id}/jobs/extract-audio")

    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "audio_extraction_failed",
            "message": "Failed to extract audio.",
        },
    }
    assert fake_storage_service.deleted_objects == [
        {
            "bucket": "videos",
            "object_name": f"videos/{video_id}/audio/audio.wav",
        }
    ]

    check_session = db_session_factory()
    try:
        saved_video = check_session.get(Video, video_id)
        job = check_session.scalars(
            select(ProcessingJob).where(
                ProcessingJob.video_id == video_id,
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
            )
        ).one()
    finally:
        check_session.close()

    assert saved_video is not None
    assert saved_video.audio_url is None
    assert saved_video.audio_object_name is None
    assert saved_video.duration_seconds is None
    assert job.status == JOB_STATUS_FAILED
    assert job.error_message is not None
    assert "final commit failed" in job.error_message


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
