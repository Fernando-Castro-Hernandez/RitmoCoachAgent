"""cuentas de usuario (cambio de alcance, Fase F)

El plan original decía que no habría cuentas: la identidad era un UUID del
navegador. Este cambio lo revierte, y no es sólo una tabla más — significa que
`user_id` deja de ser un dato que manda el cliente y pasa a salir de un token
firmado.

Sobre las claves foráneas: se añaden en `athlete_profile` y `session_log`. En
SQLite las restricciones no se pueden añadir a una tabla existente sin
recrearla, así que se usa `batch_alter_table`, que es exactamente lo que hace
por debajo. En PostgreSQL —que es donde corre esto— es un ALTER normal.

**Datos previos.** Cualquier fila que existiera antes tiene un `user_id` que no
corresponde a ninguna cuenta, así que la clave foránea la rechazaría. La
migración las borra: eran de corredores anónimos de desarrollo, sin correo con
el que reclamarlas y sin forma de adoptarlas. Si esto llegara a correr sobre
datos reales habría que escribir primero una cuenta por cada `user_id` distinto,
y no es el caso.

Revision ID: a1f2c93b7e40
Revises: 8c31a7f204de
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f2c93b7e40"
down_revision: str | Sequence[str] | None = "8c31a7f204de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        # El hash de bcrypt, con la sal dentro. Nunca la contraseña.
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # Filas huérfanas del modelo anterior. Ver la cabecera.
    op.execute("DELETE FROM training_state")
    op.execute("DELETE FROM session_log")
    op.execute("DELETE FROM wellness_log")
    op.execute("DELETE FROM coach_decision")
    op.execute("DELETE FROM conversation_memory")
    op.execute("DELETE FROM telegram_link")
    op.execute("DELETE FROM nudge_log")
    op.execute("DELETE FROM athlete_profile")

    with op.batch_alter_table("athlete_profile") as lote:
        lote.create_foreign_key("fk_athlete_profile_users", "users", ["user_id"], ["id"])
    with op.batch_alter_table("session_log") as lote:
        lote.create_foreign_key("fk_session_log_users", "users", ["user_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("session_log") as lote:
        lote.drop_constraint("fk_session_log_users", type_="foreignkey")
    with op.batch_alter_table("athlete_profile") as lote:
        lote.drop_constraint("fk_athlete_profile_users", type_="foreignkey")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
