from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PENDING,
    PROCESSING_JOB_TYPE_MOCK_PIPELINE,
    VIDEO_STATUS_COMPLETED,
)
from app.models import ProcessingJob, SemanticSegment, TranscriptSegment, Video


def test_run_mock_pipeline_creates_transcripts_and_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="pipeline-source.mp4",
        original_url="http://storage.local/videos/pipeline-source.mp4",
        preview_url=None,
        duration_seconds=420.0,
        status="pending",
    )
    job = ProcessingJob(
        video=video,
        job_type=PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        status=JOB_STATUS_PENDING,
        error_message=None,
    )
    db_session.add_all([video, job])
    db_session.commit()

    response = client.post(f"/api/videos/{video.id}/jobs/mock-pipeline")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["video_id"] == str(video.id)
    assert payload["data"]["transcript_segments_created"] == 10
    assert payload["data"]["semantic_segments_created"] == 5
    assert payload["data"]["job_status"] == JOB_STATUS_COMPLETED

    assert (
        db_session.scalar(
            select(func.count(TranscriptSegment.id)).where(
                TranscriptSegment.video_id == video.id
            )
        )
        == 10
    )
    segments = db_session.scalars(
        select(SemanticSegment)
        .where(SemanticSegment.video_id == video.id)
        .order_by(SemanticSegment.sort_order.asc())
    ).all()
    assert len(segments) == 5
    assert all(segment.transcript_text.strip() for segment in segments)
    assert all(0.0 <= segment.confidence <= 1.0 for segment in segments)

    db_session.expire_all()
    refreshed_video = db_session.get(Video, video.id)
    refreshed_job = db_session.get(ProcessingJob, job.id)
    assert refreshed_video is not None
    assert refreshed_job is not None
    assert refreshed_video.status == VIDEO_STATUS_COMPLETED
    assert refreshed_job.status == JOB_STATUS_COMPLETED


def test_run_mock_pipeline_is_idempotent_for_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="idempotent.mp4",
        original_url="http://storage.local/videos/idempotent.mp4",
        preview_url=None,
        duration_seconds=420.0,
        status="pending",
    )
    job = ProcessingJob(
        video=video,
        job_type=PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        status=JOB_STATUS_PENDING,
        error_message=None,
    )
    db_session.add_all([video, job])
    db_session.commit()

    first_response = client.post(f"/api/videos/{video.id}/jobs/mock-pipeline")
    second_response = client.post(f"/api/videos/{video.id}/jobs/mock-pipeline")

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
                ProcessingJob.job_type == PROCESSING_JOB_TYPE_MOCK_PIPELINE,
            )
        )
        == 1
    )


def test_get_video_segments_returns_sorted_segments(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="segments.mp4",
        original_url="http://storage.local/videos/segments.mp4",
        preview_url=None,
        duration_seconds=60.0,
        status="completed",
    )
    second_segment = SemanticSegment(
        video=video,
        start_time=20.0,
        end_time=40.0,
        title="Operational Bottleneck",
        summary="Explains the bottleneck.",
        topic="bottleneck",
        keywords=["workflow", "editing"],
        transcript_text="Second transcript block.",
        confidence=0.82,
        reason="Topic remains on editing delay.",
        sort_order=2,
    )
    first_segment = SemanticSegment(
        video=video,
        start_time=0.0,
        end_time=20.0,
        title="Meeting Opening",
        summary="Introduces the review.",
        topic="opening",
        keywords=["meeting", "context"],
        transcript_text="First transcript block.",
        confidence=0.93,
        reason="Topic stays on meeting context.",
        sort_order=1,
    )
    db_session.add_all([video, second_segment, first_segment])
    db_session.commit()

    response = client.get(f"/api/videos/{video.id}/segments")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert [item["sort_order"] for item in payload["data"]] == [1, 2]


def test_get_video_segments_video_not_found(client: TestClient) -> None:
    response = client.get(f"/api/videos/{uuid4()}/segments")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_not_found",
            "message": "Video not found.",
        },
    }


def test_get_video_jobs_returns_jobs(client: TestClient, db_session: Session) -> None:
    video = Video(
        id=uuid4(),
        filename="jobs.mp4",
        original_url="http://storage.local/videos/jobs.mp4",
        preview_url=None,
        duration_seconds=120.0,
        status="completed",
    )
    older_job = ProcessingJob(
        video=video,
        job_type="upload",
        status="completed",
        error_message=None,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    newer_job = ProcessingJob(
        video=video,
        job_type=PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        status="completed",
        error_message=None,
        created_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )
    db_session.add_all([video, older_job, newer_job])
    db_session.commit()

    response = client.get(f"/api/videos/{video.id}/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert [item["job_type"] for item in payload["data"]] == [
        PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        "upload",
    ]


def test_mock_pipeline_video_not_found(client: TestClient) -> None:
    response = client.post(f"/api/videos/{uuid4()}/jobs/mock-pipeline")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "video_not_found",
            "message": "Video not found.",
        },
    }


def test_get_video_transcript_after_mock_pipeline_returns_sorted_transcripts(
    client: TestClient,
    db_session: Session,
) -> None:
    video = Video(
        id=uuid4(),
        filename="mock-transcript.mp4",
        original_url="http://storage.local/videos/mock-transcript.mp4",
        preview_url=None,
        duration_seconds=420.0,
        status="pending",
    )
    job = ProcessingJob(
        video=video,
        job_type=PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        status=JOB_STATUS_PENDING,
        error_message=None,
    )
    db_session.add_all([video, job])
    db_session.commit()

    run_response = client.post(f"/api/videos/{video.id}/jobs/mock-pipeline")
    assert run_response.status_code == 200

    response = client.get(f"/api/videos/{video.id}/transcript")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["data"]) == 10
    assert [item["sort_order"] for item in payload["data"]] == list(range(1, 11))
    assert all(item["text"].strip() for item in payload["data"])
    assert payload["data"][0]["start_time"] == 0.0
    assert payload["data"][-1]["end_time"] == 420.0

    previous_end_time = None
    for item in payload["data"]:
        assert item["end_time"] > item["start_time"]
        if previous_end_time is not None:
            assert item["start_time"] == previous_end_time
        previous_end_time = item["end_time"]
