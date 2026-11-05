from sqlmodel import SQLModel


class MascotaRead(SQLModel):
    id: int
    nombre: str
    especie: str
    duenio_id: int
