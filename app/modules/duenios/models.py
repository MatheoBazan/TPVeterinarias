from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.mascotas.models import Mascota


class Duenio(SQLModel, table=True):
    __tablename__ = "duenio"
    __table_args__ = (UniqueConstraint("email", name="uq_duenio_email"),)

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    email: str

    ficha: Optional["FichaDuenio"] = Relationship(
        back_populates="duenio",
        passive_deletes="all",
        sa_relationship_kwargs={"uselist": False},
    )
    mascotas: list["Mascota"] = Relationship(
        back_populates="duenio", passive_deletes="all"
    )


class FichaDuenio(SQLModel, table=True):
    __tablename__ = "ficha_duenio"
    __table_args__ = (UniqueConstraint("duenio_id", name="uq_ficha_duenio_duenio_id"),)

    id: int | None = Field(default=None, primary_key=True)
    duenio_id: int = Field(foreign_key="duenio.id", ondelete="CASCADE")
    telefono: str
    direccion: str

    duenio: Optional["Duenio"] = Relationship(back_populates="ficha")
