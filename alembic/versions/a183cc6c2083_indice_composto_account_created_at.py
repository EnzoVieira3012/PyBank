"""indice composto account created_at

Revision ID: a183cc6c2083
Revises: cd7f74cbc224
Create Date: 2026-09-06 03:25:17.207142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a183cc6c2083'
down_revision: Union[str, Sequence[str], None] = 'cd7f74cbc224'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extrato filtrando por conta + ordenado por data: indice composto
    (account_id, created_at DESC) evita full scan crescente."""
    op.create_index(
        "ix_transactions_account_created",
        "transactions",
        ["account_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Drop schema."""
    op.drop_index("ix_transactions_account_created", table_name="transactions")
