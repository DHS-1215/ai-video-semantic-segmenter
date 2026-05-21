"""create_core_tables

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21 21:15:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260521_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("original_url", sa.String(length=2048), nullable=False),
        sa.Column("preview_url", sa.String(length=2048), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_videos_duration_seconds_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_processing_jobs_video_id_job_type_status",
        "processing_jobs",
        ["video_id", "job_type", "status"],
        unique=False,
    )
    op.create_table(
        "semantic_segments",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_semantic_segments_confidence_range",
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_semantic_segments_time_range",
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_semantic_segments_video_id_sort_order",
        "semantic_segments",
        ["video_id", "sort_order"],
        unique=False,
    )
    op.create_table(
        "transcript_segments",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("speaker", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_transcript_segments_time_range",
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transcript_segments_video_id_sort_order",
        "transcript_segments",
        ["video_id", "sort_order"],
        unique=False,
    )
    op.create_table(
        "video_clips",
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("semantic_segment_id", sa.Uuid(), nullable=True),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("clip_url", sa.String(length=2048), nullable=True),
        sa.Column("subtitle_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "export_status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_video_clips_time_range",
        ),
        sa.ForeignKeyConstraint(
            ["semantic_segment_id"],
            ["semantic_segments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_video_clips_video_id_export_status",
        "video_clips",
        ["video_id", "export_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_video_clips_semantic_segment_id"),
        "video_clips",
        ["semantic_segment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_video_clips_video_id_export_status",
        table_name="video_clips",
    )
    op.drop_index(
        op.f("ix_video_clips_semantic_segment_id"),
        table_name="video_clips",
    )
    op.drop_table("video_clips")
    op.drop_index(
        "ix_transcript_segments_video_id_sort_order",
        table_name="transcript_segments",
    )
    op.drop_table("transcript_segments")
    op.drop_index(
        "ix_semantic_segments_video_id_sort_order",
        table_name="semantic_segments",
    )
    op.drop_table("semantic_segments")
    op.drop_index(
        "ix_processing_jobs_video_id_job_type_status",
        table_name="processing_jobs",
    )
    op.drop_table("processing_jobs")
    op.drop_table("videos")
