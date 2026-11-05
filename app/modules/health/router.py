from fastapi import APIRouter, Response, status

from app.core.database import SessionDep
from app.modules.health import service
from app.modules.health.schemas import EstadoSalud

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", status_code=status.HTTP_200_OK, response_model=EstadoSalud)
async def live() -> EstadoSalud:
    return EstadoSalud(estado="vivo")


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    response_model=EstadoSalud,
    responses={503: {"model": EstadoSalud, "description": "La base no contesta"}},
)
async def ready(session: SessionDep, response: Response) -> EstadoSalud:
    if await service.base_disponible(session):
        return EstadoSalud(estado="listo")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return EstadoSalud(estado="sin base")
