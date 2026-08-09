"""add aquarium journal entries

Revision ID: 20260809_000001
Revises: 20260731_000005
Create Date: 2026-08-09 00:00:01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260809_000001"
down_revision: Union[str, Sequence[str], None] = "20260731_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID_TYPE = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "aquarium_journal_entries",
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("aquarium_id", UUID_TYPE, nullable=False),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aquarium_id"], ["aquariums.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_aquarium_journal_entries_aquarium_id",
        "aquarium_journal_entries",
        ["aquarium_id"],
        unique=False,
    )
    op.create_index(
        "ix_aquarium_journal_entries_entry_at",
        "aquarium_journal_entries",
        ["entry_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_aquarium_journal_entries_entry_at", table_name="aquarium_journal_entries")
    op.drop_index("ix_aquarium_journal_entries_aquarium_id", table_name="aquarium_journal_entries")
    op.drop_table("aquarium_journal_entries")
