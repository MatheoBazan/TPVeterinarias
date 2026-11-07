from typing import Final

from sqlmodel import Field, SQLModel

from app.core.parametros import ENTERO_MAXIMO
from app.modules.duenios.schemas import ENTRADA, DuenioRead

TAMANIO_POR_DEFECTO: Final = 20
TAMANIO_MAXIMO: Final = 100


class MascotaRead(SQLModel):
    id: int
    nombre: str
    especie: str
    duenio_id: int


class MascotaCreate(SQLModel):
    model_config = ENTRADA

    nombre: str = Field(min_length=1)
    especie: str = Field(min_length=1)
    duenio_id: int = Field(le=ENTERO_MAXIMO)


class MascotaConDuenioRead(MascotaRead):
    duenio: DuenioRead


class PaginaMascotas(SQLModel):
    items: list[MascotaRead]
    total: int
    page: int
    size: int
    pages: int
