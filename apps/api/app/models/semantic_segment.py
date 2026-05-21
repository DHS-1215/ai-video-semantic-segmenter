from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.video import Video
    from app.models.video_clip import VideoClip


class SemanticSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "semantic_segments"
    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_semantic_segments_time_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_semantic_segments_confidence_range",
        ),
        Index(
            "ix_semantic_segments_video_id_sort_order",
            "video_id",
            "sort_order",
        ),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    video: Mapped["Video"] = relationship(back_populates="semantic_segments")
    video_clips: Mapped[list["VideoClip"]] = relationship(
        back_populates="semantic_segment",
    )
