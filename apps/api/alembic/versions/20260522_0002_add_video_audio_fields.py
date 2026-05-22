"""add_video_audio_fields

Revision ID: 20260522_0002
Revises: 20260521_0001
Create Date: 2026-05-22 13:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260522_0002"
down_revision: Union[str, None] = "20260521_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("original_object_name", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("audio_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "videos",
        sa.Column("audio_object_name", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("videos", "audio_object_name")
    op.drop_column("videos", "audio_url")
    op.drop_column("videos", "original_object_name")
