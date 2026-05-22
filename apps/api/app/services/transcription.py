from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.core.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
)
from app.core.errors import APIError
from app.models import ProcessingJob, TranscriptSegment, Video
from app.services.asr import ASRProvider


def transcribe_audio_for_video(
    db: Session,
    video: Video,
    asr_provider: ASRProvider,
) -> dict[str, str | int | UUID]:
    if not video.audio_object_name:
        raise APIError(
            400,
            "missing_audio_object",
            "Video audio object is missing.",
        )

    job = _get_or_create_transcription_job(db, video.id)

    try:
        job.status = JOB_STATUS_RUNNING
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)

        transcript_results = asr_provider.transcribe(video.audio_object_name)

        db.execute(
            delete(TranscriptSegment).where(TranscriptSegment.video_id == video.id)
        )

        transcript_segments = [
            TranscriptSegment(
                video_id=video.id,
                start_time=result.start_time,
                end_time=result.end_time,
                speaker=result.speaker,
                text=result.text,
                sort_order=index,
            )
            for index, result in enumerate(transcript_results, start=1)
        ]
        db.add_all(transcript_segments)

        job.status = JOB_STATUS_COMPLETED
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)

        return {
            "video_id": video.id,
            "transcript_segments_created": len(transcript_segments),
            "job_status": job.status,
        }
    except APIError:
        raise
    except Exception as exc:
        db.rollback()
        _mark_job_failed(
            db=db,
            job_id=job.id,
            error_message=str(exc),
        )
        raise APIError(
            500,
            "audio_transcription_failed",
            "Failed to transcribe audio.",
        ) from exc


def _get_or_create_transcription_job(db: Session, video_id: UUID) -> ProcessingJob:
    job = db.scalars(
        select(ProcessingJob)
        .where(
            ProcessingJob.video_id == video_id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
        )
        .order_by(desc(ProcessingJob.created_at))
        .limit(1)
    ).first()

    if job is None:
        job = ProcessingJob(
            video_id=video_id,
            job_type=PROCESSING_JOB_TYPE_TRANSCRIBE_AUDIO,
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
