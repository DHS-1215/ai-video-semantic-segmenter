from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    CLIP_EXPORT_STATUS_PENDING,
    JOB_STATUS_PENDING,
    VIDEO_STATUS_PENDING,
)
from app.models import (
    ProcessingJob,
    SemanticSegment,
    TranscriptSegment,
    Video,
    VideoClip,
)


def test_video_can_be_created(db_session: Session) -> None:
    video = Video(
        filename="demo-video.mp4",
        original_url="http://localhost:9000/videos/demo-video.mp4",
        preview_url=None,
        duration_seconds=120.5,
        status=VIDEO_STATUS_PENDING,
    )

    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    saved_video = db_session.scalar(select(Video).where(Video.id == video.id))

    assert saved_video is not None
    assert saved_video.filename == "demo-video.mp4"
    assert saved_video.created_at is not None
    assert saved_video.updated_at is not None


def test_transcript_segment_can_associate_with_video(db_session: Session) -> None:
    video = Video(
        filename="transcript-source.mp4",
        original_url="http://localhost:9000/videos/transcript-source.mp4",
        status=VIDEO_STATUS_PENDING,
    )
    segment = TranscriptSegment(
        start_time=0.0,
        end_time=4.5,
        speaker="Speaker 1",
        text="This is the first transcript segment.",
        sort_order=1,
        video=video,
    )

    db_session.add(segment)
    db_session.commit()
    db_session.refresh(segment)

    saved_segment = db_session.scalar(
        select(TranscriptSegment).where(TranscriptSegment.id == segment.id)
    )

    assert saved_segment is not None
    assert saved_segment.video_id == video.id
    assert saved_segment.video.filename == "transcript-source.mp4"


def test_semantic_segment_can_associate_with_video(db_session: Session) -> None:
    video = Video(
        filename="semantic-source.mp4",
        original_url="http://localhost:9000/videos/semantic-source.mp4",
        status=VIDEO_STATUS_PENDING,
    )
    semantic_segment = SemanticSegment(
        start_time=5.0,
        end_time=19.0,
        title="Product Introduction",
        summary="Introduces the product positioning.",
        topic="introduction",
        keywords=["product", "brand", "positioning"],
        transcript_text="Here we introduce the product and explain its positioning.",
        confidence=0.92,
        reason="Topic remains consistent throughout this interval.",
        sort_order=1,
        video=video,
    )

    db_session.add(semantic_segment)
    db_session.commit()
    db_session.refresh(semantic_segment)

    saved_segment = db_session.scalar(
        select(SemanticSegment).where(SemanticSegment.id == semantic_segment.id)
    )

    assert saved_segment is not None
    assert saved_segment.video_id == video.id
    assert saved_segment.video.filename == "semantic-source.mp4"
    assert saved_segment.keywords == ["product", "brand", "positioning"]


def test_processing_job_can_associate_with_video(db_session: Session) -> None:
    video = Video(
        filename="job-source.mp4",
        original_url="http://localhost:9000/videos/job-source.mp4",
        status=VIDEO_STATUS_PENDING,
    )
    job = ProcessingJob(
        job_type="transcription",
        status=JOB_STATUS_PENDING,
        error_message=None,
        video=video,
    )

    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    saved_job = db_session.scalar(
        select(ProcessingJob).where(ProcessingJob.id == job.id)
    )

    assert saved_job is not None
    assert saved_job.video_id == video.id
    assert saved_job.video.filename == "job-source.mp4"


def test_video_clip_can_associate_with_video_and_semantic_segment(
    db_session: Session,
) -> None:
    video = Video(
        filename="clip-source.mp4",
        original_url="http://localhost:9000/videos/clip-source.mp4",
        status=VIDEO_STATUS_PENDING,
    )
    semantic_segment = SemanticSegment(
        start_time=10.0,
        end_time=24.0,
        title='Campaign Message',
        summary="Captures the main campaign message.",
        topic="campaign",
        keywords=["campaign", "message"],
        transcript_text="This section delivers the main campaign message.",
        confidence=0.88,
        reason="The semantic topic stays focused on the campaign message.",
        sort_order=1,
        video=video,
    )
    video_clip = VideoClip(
        start_time=10.0,
        end_time=24.0,
        clip_url=None,
        subtitle_url=None,
        video=video,
        semantic_segment=semantic_segment,
    )

    db_session.add(video_clip)
    db_session.commit()
    db_session.refresh(video_clip)

    saved_clip = db_session.scalar(select(VideoClip).where(VideoClip.id == video_clip.id))

    assert saved_clip is not None
    assert saved_clip.video_id == video.id
    assert saved_clip.semantic_segment_id == semantic_segment.id
    assert saved_clip.export_status == CLIP_EXPORT_STATUS_PENDING
