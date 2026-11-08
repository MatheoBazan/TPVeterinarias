from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.errores import MensajeError
from app.core.parametros import IdRuta
from app.modules.turnos import service
from app.modules.turnos.schemas import TurnoCreate, TurnoRead

router = APIRouter(prefix="/turnos", tags=["turnos"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=TurnoRead,
    responses={409: {"model": MensajeError, "description": "Mascota o práctica inexistente, o práctica repetida"}},
)
async def crear_turno(session: SessionDep, datos: TurnoCreate) -> TurnoRead:
    return await service.crear_turno(session, datos)


@router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=TurnoRead,
    responses={404: {"model": MensajeError, "description": "No existe el turno"}},
)
async def obtener_turno(session: SessionDep, id: IdRuta) -> TurnoRead:
    return await service.obtener_turno(session, id)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": MensajeError, "description": "No existe el turno"}},
)
async def borrar_turno(session: SessionDep, id: IdRuta) -> None:
    await service.borrar_turno(session, id)
