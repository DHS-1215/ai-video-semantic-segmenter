from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
)
from app.core.errors import APIError
from app.models import ProcessingJob, SemanticSegment, TranscriptSegment, Video
from app.services.semantic_segmenter import SemanticSegmenterProvider


def segment_transcript_for_video(
    db: Session,
    video: Video,
    segmenter_provider: SemanticSegmenterProvider,
) -> dict[str, str | int | UUID]:
    transcript_segments = db.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.video_id == video.id)
        .order_by(TranscriptSegment.sort_order.asc())
    ).all()

    if not transcript_segments:
        raise APIError(
            400,
            "missing_transcript_segments",
            "Transcript segments are missing.",
        )

    job = _get_or_create_semantic_segmentation_job(db, video.id)

    try:
        job.status = JOB_STATUS_RUNNING
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)

        semantic_candidates = segmenter_provider.segment(transcript_segments)
        if not semantic_candidates:
            raise RuntimeError("Segmenter provider returned no semantic segments.")

        db.execute(
            delete(SemanticSegment).where(SemanticSegment.video_id == video.id)
        )

        semantic_segments = [
            SemanticSegment(
                video_id=video.id,
                start_time=candidate.start_time,
                end_time=candidate.end_time,
                title=candidate.title,
                summary=candidate.summary,
                topic=candidate.topic,
                keywords=candidate.keywords,
                transcript_text=candidate.transcript_text,
                confidence=candidate.confidence,
                reason=candidate.reason,
                sort_order=index,
            )
            for index, candidate in enumerate(semantic_candidates, start=1)
        ]
        db.add_all(semantic_segments)

        job.status = JOB_STATUS_COMPLETED
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)

        return {
            "video_id": video.id,
            "semantic_segments_created": len(semantic_segments),
            "job_status": job.status,
        }
    except Exception as exc:
        db.rollback()
        _mark_job_failed(
            db=db,
            job_id=job.id,
            error_message=str(exc),
        )
        if isinstance(exc, APIError):
            raise
        raise APIError(
            500,
            "semantic_segmentation_failed",
            "Failed to generate semantic segments.",
        ) from exc


def _get_or_create_semantic_segmentation_job(
    db: Session,
    video_id: UUID,
) -> ProcessingJob:
    job = db.scalars(
        select(ProcessingJob)
        .where(
            ProcessingJob.video_id == video_id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
        )
        .order_by(desc(ProcessingJob.created_at))
        .limit(1)
    ).first()

    if job is None:
        job = ProcessingJob(
            video_id=video_id,
            job_type=PROCESSING_JOB_TYPE_SEMANTIC_SEGMENT,
            status=JOB_STATUS_PENDING,
            error_message=None,
        )
        db.add(job)
        db.flush()

    return job


def _mark_job_failed(
    *,
    db: Session,
    job_id: UUID,
    error_message: str,
) -> None:
    try:
        job = db.get(ProcessingJob, job_id)
        if job is None:
            return

        job.status = JOB_STATUS_FAILED
        job.error_message = error_message[:1000]
        db.commit()
    except Exception:
        db.rollback()
