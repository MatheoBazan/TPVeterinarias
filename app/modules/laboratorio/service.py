import asyncio

from app.modules.laboratorio import cliente
from app.modules.laboratorio.schemas import StockRead


async def consultar_stock(vacuna: str) -> StockRead:
    # consultar_stock es sincrónica (time.sleep): corre en un hilo aparte para no frenar el
    # bucle de eventos mientras espera (Ej. 6, caso C-09).
    stock = await asyncio.to_thread(cliente.consultar_stock, vacuna)
    return StockRead(vacuna=vacuna, stock=stock)
