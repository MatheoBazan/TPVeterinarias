from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Numeric
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.mascotas.models import Mascota
    from app.modules.practicas.models import Practica


class Turno(SQLModel, table=True):
    __tablename__ = "turno"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_turno_total_no_negativo"),)

    id: int | None = Field(default=None, primary_key=True)
    mascota_id: int = Field(foreign_key="mascota.id", ondelete="RESTRICT", index=True)
    fecha: datetime = Field(sa_type=DateTime(timezone=True))
    motivo: str
    total: Decimal = Field(sa_type=Numeric(12, 2))

    mascota: Optional["Mascota"] = Relationship(back_populates="turnos")
    practicas: list["TurnoPractica"] = Relationship(
        back_populates="turno", passive_deletes="all"
    )


class TurnoPractica(SQLModel, table=True):
    __tablename__ = "turno_practica"
    __table_args__ = (
        CheckConstraint(
            "precio_unitario > 0", name="ck_turno_practica_precio_unitario_positivo"
        ),
    )

    turno_id: int | None = Field(
        default=None, primary_key=True, foreign_key="turno.id", ondelete="CASCADE"
    )
    practica_id: int | None = Field(
        default=None,
        primary_key=True,
        foreign_key="practica.id",
        ondelete="RESTRICT",
        index=True,
    )
    precio_unitario: Decimal = Field(sa_type=Numeric(10, 2))

    turno: Optional["Turno"] = Relationship(back_populates="practicas")
    practica: Optional["Practica"] = Relationship(back_populates="turnos")
