from decimal import Decimal

from pydantic import ConfigDict, field_validator
from sqlmodel import Field, SQLModel

ENTRADA = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PracticaCreate(SQLModel):
    model_config = ENTRADA

    nombre: str = Field(min_length=1)
    precio: Decimal = Field(gt=0, max_digits=10, decimal_places=2)

    @field_validator("precio")
    @classmethod
    def con_dos_decimales(cls, valor: Decimal) -> Decimal:
        # Sólo fija la escala (decimal_places=2 ya rechazó lo que no entra): así el 201 y el GET coinciden.
        return valor.quantize(Decimal("0.01"))


class PracticaRead(SQLModel):
    id: int
    nombre: str
    precio: Decimal
