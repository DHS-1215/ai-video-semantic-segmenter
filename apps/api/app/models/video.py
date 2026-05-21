from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import VIDEO_STATUS_PENDING
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.processing_job import ProcessingJob
    from app.models.semantic_segment import SemanticSegment
    from app.models.transcript_segment import TranscriptSegment
    from app.models.video_clip import VideoClip


class Video(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_videos_duration_seconds_non_negative",
        ),
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    preview_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=VIDEO_STATUS_PENDING,
    )

    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.sort_order",
    )
    semantic_segments: Mapped[list["SemanticSegment"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="SemanticSegment.sort_order",
    )
    video_clips: Mapped[list["VideoClip"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )
