"""represent users.email uniqueness as a named constraint

Revision ID: 0003_email_unique_constraint
Revises: 0002_create_datasets
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_email_unique_constraint"
down_revision: Union[str, Sequence[str], None] = "0002_create_datasets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_index("ix_users_email", table_name="users")


def downgrade() -> None:
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.drop_constraint("uq_users_email", "users", type_="unique")
