from sqlmodel import SQLModel


class StockRead(SQLModel):
    vacuna: str
    stock: int
