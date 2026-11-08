from fastapi import APIRouter, status

from app.modules.laboratorio import service
from app.modules.laboratorio.schemas import StockRead

router = APIRouter(prefix="/laboratorio", tags=["laboratorio"])


@router.get("/stock/{vacuna}", status_code=status.HTTP_200_OK, response_model=StockRead)
async def consultar_stock(vacuna: str) -> StockRead:
    return await service.consultar_stock(vacuna)
