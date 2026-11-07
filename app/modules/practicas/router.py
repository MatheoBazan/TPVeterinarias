from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.errores import MensajeError
from app.modules.practicas import service
from app.modules.practicas.schemas import PracticaCreate, PracticaRead

router = APIRouter(prefix="/practicas", tags=["practicas"])


@router.get("/", status_code=status.HTTP_200_OK, response_model=list[PracticaRead])
async def listar_practicas(session: SessionDep) -> list[PracticaRead]:
    return await service.listar_practicas(session)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=PracticaRead,
    responses={409: {"model": MensajeError, "description": "Ya existe una práctica con ese nombre"}},
)
async def crear_practica(session: SessionDep, datos: PracticaCreate) -> PracticaRead:
    return await service.crear_practica(session, datos)
