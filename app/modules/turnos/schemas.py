from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AwareDatetime, field_serializer
from sqlmodel import Field, SQLModel

from app.core.parametros import ENTERO_MAXIMO
from app.modules.duenios.schemas import ENTRADA


class PracticaDeTurnoCreate(SQLModel):
    model_config = ENTRADA

    practica_id: int = Field(le=ENTERO_MAXIMO)


class TurnoCreate(SQLModel):
    """Alta de turno: sin id, precios ni total (los copia y calcula el servidor, RN-06)."""

    model_config = ENTRADA

    mascota_id: int = Field(le=ENTERO_MAXIMO)
    fecha: AwareDatetime  # sin zona horaria → 422 (PA-10)
    motivo: str = Field(min_length=1)
    practicas: list[PracticaDeTurnoCreate] = Field(min_length=1)  # RN-05; repetidas las rechaza la PK (RN-07)


class MascotaDeTurnoRead(SQLModel):
    id: int
    nombre: str
    especie: str


class PracticaDeTurnoRead(SQLModel):
    practica_id: int
    nombre: str
    precio_unitario: Decimal


class TurnoRead(SQLModel):
    id: int
    fecha: datetime
    motivo: str
    total: Decimal
    mascota: MascotaDeTurnoRead
    practicas: list[PracticaDeTurnoRead]

    @field_serializer("fecha")
    def en_utc(self, valor: datetime) -> datetime:
        # Siempre en UTC: Pydantic la serializa con sufijo Z, como el ejemplo de la consigna.
        return valor.astimezone(UTC)
