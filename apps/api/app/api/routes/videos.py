from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_object_storage_service
from app.core.config import get_settings
from app.core.constants import (
    JOB_STATUS_PENDING,
    PROCESSING_JOB_TYPE_MOCK_PIPELINE,
    VIDEO_STATUS_PENDING,
)
from app.core.errors import APIError
from app.models import ProcessingJob, SemanticSegment, TranscriptSegment, Video
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.job import (
    AudioExtractionResponse,
    MockPipelineResponse,
    ProcessingJobResponse,
)
from app.schemas.semantic import SemanticSegmentResponse
from app.schemas.transcript import TranscriptSegmentResponse
from app.schemas.video import VideoListItem, VideoResponse, VideoUploadResponse
from app.services.audio_extraction import extract_audio_for_video
from app.services.mock_pipeline import run_mock_pipeline
from app.services.storage import ObjectStorageService, StoredObject, make_safe_filename

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post(
    "/upload",
    response_model=SuccessResponse[VideoUploadResponse],
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    status_code=status.HTTP_201_CREATED,
)
def upload_video(
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    storage_service: ObjectStorageService = Depends(get_object_storage_service),
) -> SuccessResponse[VideoUploadResponse]:
    settings = get_settings()

    if file is None or not file.filename or not file.filename.strip():
        raise APIError(400, "empty_file", "Uploaded file is empty.")

    safe_filename = make_safe_filename(file.filename)
    extension = Path(safe_filename).suffix.lstrip(".").lower()
    allowed_extensions = {ext.lower() for ext in settings.allowed_video_extensions}

    if not extension or extension not in allowed_extensions:
        raise APIError(
            400,
            "unsupported_file_type",
            "Only mp4, mov, webm, and mkv uploads are supported.",
        )

    file.file.seek(0, 2)
    size_bytes = file.file.tell()
    file.file.seek(0)

    if size_bytes <= 0:
        raise APIError(400, "empty_file", "Uploaded file is empty.")

    max_upload_size_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_upload_size_bytes:
        raise APIError(
            400,
            "file_too_large",
            f"Uploaded file exceeds the {settings.max_upload_size_mb} MB limit.",
        )

    video_id = uuid4()

    try:
        stored_object = storage_service.upload_stream(
            video_id=video_id,
            filename=safe_filename,
            data=file.file,
            length=size_bytes,
            content_type=file.content_type,
        )
    except Exception as exc:
        raise APIError(500, "storage_upload_failed", "Failed to upload video file.") from exc

    video = Video(
        id=video_id,
        filename=safe_filename,
        original_url=stored_object.url,
        original_object_name=stored_object.object_name,
        preview_url=None,
        audio_url=None,
        audio_object_name=None,
        duration_seconds=None,
        status=VIDEO_STATUS_PENDING,
    )
    processing_job = ProcessingJob(
        video=video,
        job_type=PROCESSING_JOB_TYPE_MOCK_PIPELINE,
        status=JOB_STATUS_PENDING,
        error_message=None,
    )

    db.add_all([video, processing_job])
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        _attempt_storage_cleanup(storage_service, stored_object)
        raise APIError(
            500,
            "video_create_failed",
            "Failed to create video record.",
        ) from exc
    db.refresh(video)

    return SuccessResponse(
        data=VideoUploadResponse(
            video_id=video.id,
            status=video.status,
            filename=video.filename,
            original_url=video.original_url,
        )
    )


@router.post(
    "/{video_id}/jobs/mock-pipeline",
    response_model=SuccessResponse[MockPipelineResponse],
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def trigger_mock_pipeline(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> SuccessResponse[MockPipelineResponse]:
    video = _get_video_or_404(db, video_id)
    result = run_mock_pipeline(db, video)
    return SuccessResponse(data=MockPipelineResponse(**result))


@router.post(
    "/{video_id}/jobs/extract-audio",
    response_model=SuccessResponse[AudioExtractionResponse],
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def trigger_audio_extraction(
    video_id: UUID,
    db: Session = Depends(get_db),
    storage_service: ObjectStorageService = Depends(get_object_storage_service),
) -> SuccessResponse[AudioExtractionResponse]:
    video = _get_video_or_404(db, video_id)
    result = extract_audio_for_video(
        db=db,
        video=video,
        storage_service=storage_service,
    )
    return SuccessResponse(data=AudioExtractionResponse(**result))


@router.get(
    "",
    response_model=SuccessResponse[list[VideoListItem]],
    responses={422: {"model": ErrorResponse}},
)
def list_videos(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SuccessResponse[list[VideoListItem]]:
    videos = db.scalars(
        select(Video).order_by(desc(Video.created_at)).limit(limit)
    ).all()

    return SuccessResponse(
        data=[VideoListItem.model_validate(video) for video in videos]
    )


@router.get(
    "/{video_id}",
    response_model=SuccessResponse[VideoResponse],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_video(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> SuccessResponse[VideoResponse]:
    video = _get_video_or_404(db, video_id)
    return SuccessResponse(data=VideoResponse.model_validate(video))


@router.get(
    "/{video_id}/transcript",
    response_model=SuccessResponse[list[TranscriptSegmentResponse]],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_video_transcript(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> SuccessResponse[list[TranscriptSegmentResponse]]:
    _get_video_or_404(db, video_id)
    transcript_segments = db.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.sort_order.asc())
    ).all()

    return SuccessResponse(
        data=[
            TranscriptSegmentResponse.model_validate(segment)
            for segment in transcript_segments
        ]
    )


@router.get(
    "/{video_id}/segments",
    response_model=SuccessResponse[list[SemanticSegmentResponse]],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_video_segments(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> SuccessResponse[list[SemanticSegmentResponse]]:
    _get_video_or_404(db, video_id)
    semantic_segments = db.scalars(
        select(SemanticSegment)
        .where(SemanticSegment.video_id == video_id)
        .order_by(SemanticSegment.sort_order.asc())
    ).all()

    return SuccessResponse(
        data=[
            SemanticSegmentResponse.model_validate(segment)
            for segment in semantic_segments
        ]
    )


@router.get(
    "/{video_id}/jobs",
    response_model=SuccessResponse[list[ProcessingJobResponse]],
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_video_jobs(
    video_id: UUID,
    db: Session = Depends(get_db),
) -> SuccessResponse[list[ProcessingJobResponse]]:
    _get_video_or_404(db, video_id)
    processing_jobs = db.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.video_id == video_id)
        .order_by(ProcessingJob.created_at.desc())
    ).all()

    return SuccessResponse(
        data=[ProcessingJobResponse.model_validate(job) for job in processing_jobs]
    )


def _get_video_or_404(db: Session, video_id: UUID) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise APIError(404, "video_not_found", "Video not found.")
    return video


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
