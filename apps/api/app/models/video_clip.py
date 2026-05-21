from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import CLIP_EXPORT_STATUS_PENDING
from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.semantic_segment import SemanticSegment
    from app.models.video import Video


class VideoClip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "video_clips"
    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_video_clips_time_range",
        ),
        Index(
            "ix_video_clips_video_id_export_status",
            "video_id",
            "export_status",
        ),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    semantic_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("semantic_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    clip_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    subtitle_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    export_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CLIP_EXPORT_STATUS_PENDING,
    )

    video: Mapped["Video"] = relationship(back_populates="video_clips")
    semantic_segment: Mapped["SemanticSegment | None"] = relationship(
        back_populates="video_clips",
    )
