"""registro de avisos proactivos (tarea E2)

La tabla es a la vez el historial de qué se le mandó al corredor y el candado
que impide mandárselo dos veces. `sent_on` guarda la fecha **local** del
corredor — la única fecha local del esquema — porque la clave de deduplicación
es «una vez por mañana suya», y eso en UTC no se puede expresar.

Revision ID: 8c31a7f204de
Revises: 46613e15f0fe
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c31a7f204de"
down_revision: str | Sequence[str] | None = "46613e15f0fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nudge_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("flow", sa.String(length=32), nullable=False),
        sa.Column("sent_on", sa.Date(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_nudge_log_user_id"), "nudge_log", ["user_id"], unique=False)
    # El índice que sirve a la consulta caliente: el barrido horario pregunta
    # «¿ya salió este flujo para este corredor en esta fecha suya?».
    op.create_index(
        "ix_nudge_log_user_flow", "nudge_log", ["user_id", "flow", "sent_on"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_nudge_log_user_flow", table_name="nudge_log")
    op.drop_index(op.f("ix_nudge_log_user_id"), table_name="nudge_log")
    op.drop_table("nudge_log")
