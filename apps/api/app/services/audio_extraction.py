from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
)
from app.core.errors import APIError
from app.models import ProcessingJob, Video
from app.services import ffmpeg as ffmpeg_service
from app.services.storage import ObjectStorageService, StoredObject

AUDIO_OBJECT_BASENAME = "audio.wav"


def extract_audio_for_video(
    db: Session,
    video: Video,
    storage_service: ObjectStorageService,
) -> dict[str, str | float | UUID]:
    if not video.original_object_name:
        raise APIError(
            400,
            "missing_original_object",
            "Video original object is missing.",
        )

    job = _get_or_create_extract_audio_job(db, video.id)
    uploaded_audio: StoredObject | None = None

    try:
        job.status = JOB_STATUS_RUNNING
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_video_path = Path(temp_dir) / (
                f"source{Path(video.filename).suffix or '.mp4'}"
            )
            output_audio_path = Path(temp_dir) / AUDIO_OBJECT_BASENAME

            storage_service.download_object(
                bucket=get_settings().minio_bucket_videos,
                object_name=video.original_object_name,
                destination_path=str(input_video_path),
            )

            duration_seconds = ffmpeg_service.extract_audio(
                str(input_video_path),
                str(output_audio_path),
            )

            audio_object_name = f"videos/{video.id}/audio/{AUDIO_OBJECT_BASENAME}"
            with output_audio_path.open("rb") as audio_file:
                uploaded_audio = storage_service.upload_stream(
                    video_id=video.id,
                    filename=AUDIO_OBJECT_BASENAME,
                    object_name=audio_object_name,
                    data=audio_file,
                    length=output_audio_path.stat().st_size,
                    content_type="audio/wav",
                )

        video.audio_url = uploaded_audio.url
        video.audio_object_name = uploaded_audio.object_name
        video.duration_seconds = duration_seconds
        job.status = JOB_STATUS_COMPLETED
        job.error_message = None
        db.add_all([video, job])
        db.commit()
        db.refresh(video)
        db.refresh(job)

        return {
            "video_id": video.id,
            "job_status": job.status,
            "audio_url": video.audio_url,
            "audio_object_name": video.audio_object_name,
            "duration_seconds": video.duration_seconds,
        }
    except APIError:
        raise
    except Exception as exc:
        db.rollback()

        if uploaded_audio is not None:
            _attempt_storage_cleanup(storage_service, uploaded_audio)

        _mark_job_failed(
            db=db,
            job_id=job.id,
            error_message=str(exc),
        )
        raise APIError(
            500,
            "audio_extraction_failed",
            "Failed to extract audio.",
        ) from exc


def _get_or_create_extract_audio_job(db: Session, video_id: UUID) -> ProcessingJob:
    job = db.scalars(
        select(ProcessingJob)
        .where(
            ProcessingJob.video_id == video_id,
            ProcessingJob.job_type == PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
        )
        .order_by(desc(ProcessingJob.created_at))
        .limit(1)
    ).first()

    if job is None:
        job = ProcessingJob(
            video_id=video_id,
            job_type=PROCESSING_JOB_TYPE_EXTRACT_AUDIO,
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


def _attempt_storage_cleanup(
    storage_service: ObjectStorageService,
    stored_object: StoredObject,
) -> None:
    try:
        storage_service.delete_object(
            bucket=stored_object.bucket,
            object_name=stored_object.object_name,
        )
    except Exception:
        pass
