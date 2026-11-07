from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.database import SessionDep
from app.core.errores import MensajeError
from app.core.parametros import IdRuta
from app.modules.mascotas import service
from app.modules.mascotas.schemas import (
    TAMANIO_MAXIMO,
    TAMANIO_POR_DEFECTO,
    MascotaConDuenioRead,
    MascotaCreate,
    MascotaRead,
    PaginaMascotas,
)

router = APIRouter(prefix="/mascotas", tags=["mascotas"])

Pagina = Annotated[int, Query(ge=1, description="Número de página, desde 1")]
TamanioPagina = Annotated[int, Query(ge=1, le=TAMANIO_MAXIMO, description="Mascotas por página (1 a 100)")]


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=MascotaRead,
    responses={409: {"model": MensajeError, "description": "No existe el dueño indicado"}},
)
async def crear_mascota(session: SessionDep, datos: MascotaCreate) -> MascotaRead:
    return await service.crear_mascota(session, datos)


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=PaginaMascotas,
    description=(
        "Mascotas ordenadas por id. La página 1 siempre responde (aun sin mascotas); "
        "una página mayor que `pages` responde 422 `pagina_fuera_de_rango`."
    ),
    responses={422: {"description": "Parámetros inválidos o página fuera de rango"}},
)
async def listar_mascotas(
    session: SessionDep, page: Pagina = 1, size: TamanioPagina = TAMANIO_POR_DEFECTO
) -> PaginaMascotas:
    return await service.listar_mascotas(session, page, size)


@router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=MascotaConDuenioRead,
    responses={404: {"model": MensajeError, "description": "No existe la mascota"}},
)
async def obtener_mascota(session: SessionDep, id: IdRuta) -> MascotaConDuenioRead:
    return await service.obtener_mascota(session, id)
