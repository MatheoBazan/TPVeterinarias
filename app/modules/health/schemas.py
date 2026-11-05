from sqlmodel import SQLModel


class EstadoSalud(SQLModel):
    estado: str
