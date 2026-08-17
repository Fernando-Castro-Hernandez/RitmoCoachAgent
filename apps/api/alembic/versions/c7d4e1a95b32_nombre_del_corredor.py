"""el nombre del corredor

Una columna, y la razón por la que es anulable importa más que la columna.

`NULL` significa «no lo dijo», no «se llama vacío». El coach sólo usa el nombre
cuando lo hay: llamar «Fernando» a quien nunca dio su nombre no suena cercano,
suena a que el sistema sabe cosas que nadie le contó. Un `default=''` habría
borrado esa distinción, que es justo la que hace falta para decidir si se
saluda por el nombre o no.

Va en la capa dura y no en la blanda porque es la primera pregunta del
carrusel: es el único dato que la conversación no puede recoger con gracia
—preguntar el nombre a la tercera frase es raro— y el único que cambia el tono
de todo lo demás.

Revision ID: c7d4e1a95b32
Revises: a1f2c93b7e40
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d4e1a95b32"
down_revision: str | Sequence[str] | None = "a1f2c93b7e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("athlete_profile", sa.Column("name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("athlete_profile", "name")
