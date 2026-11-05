from pydantic import ConfigDict, EmailStr, field_validator
from sqlmodel import Field, SQLModel

ENTRADA = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DuenioCreate(SQLModel):
    model_config = ENTRADA

    nombre: str = Field(min_length=1)
    email: EmailStr


class DuenioUpdate(SQLModel):
    model_config = ENTRADA

    nombre: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None

    @field_validator("nombre", "email")
    @classmethod
    def no_admite_null(cls, valor: str | None) -> str:
        # Sólo corre sobre lo enviado: un campo omitido sigue fuera de `exclude_unset`.
        if valor is None:
            raise ValueError("no puede ser null")
        return valor


class DuenioRead(SQLModel):
    id: int
    nombre: str
    email: str


class FichaRead(SQLModel):
    id: int
    duenio_id: int
    telefono: str
    direccion: str


class DuenioConFichaRead(DuenioRead):
    ficha: FichaRead | None


class FichaCreate(SQLModel):
    model_config = ENTRADA

    telefono: str = Field(min_length=1)
    direccion: str = Field(min_length=1)
