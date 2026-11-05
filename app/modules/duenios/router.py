from fastapi import APIRouter, status

from app.core.database import SessionDep
from app.core.errores import MensajeError
from app.core.parametros import IdRuta
from app.modules.duenios import service
from app.modules.duenios.schemas import (
    DuenioConFichaRead,
    DuenioCreate,
    DuenioRead,
    DuenioUpdate,
    FichaCreate,
    FichaRead,
)
from app.modules.mascotas.schemas import MascotaRead

router = APIRouter(prefix="/duenios", tags=["duenios"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=DuenioRead,
    responses={409: {"model": MensajeError, "description": "Ya existe un dueño con ese email"}},
)
async def crear_duenio(session: SessionDep, datos: DuenioCreate) -> DuenioRead:
    return await service.crear_duenio(session, datos)


@router.get(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=DuenioConFichaRead,
    responses={404: {"model": MensajeError, "description": "No existe el dueño"}},
)
async def obtener_duenio(session: SessionDep, id: IdRuta) -> DuenioConFichaRead:
    return await service.obtener_duenio(session, id)


@router.patch(
    "/{id}",
    status_code=status.HTTP_200_OK,
    response_model=DuenioConFichaRead,
    responses={
        404: {"model": MensajeError, "description": "No existe el dueño"},
        409: {"model": MensajeError, "description": "Ya existe un dueño con ese email"},
    },
)
async def actualizar_duenio(session: SessionDep, id: IdRuta, datos: DuenioUpdate) -> DuenioConFichaRead:
    return await service.actualizar_duenio(session, id, datos)


@router.post(
    "/{id}/ficha",
    status_code=status.HTTP_201_CREATED,
    response_model=FichaRead,
    responses={
        404: {"model": MensajeError, "description": "No existe el dueño"},
        409: {"model": MensajeError, "description": "El dueño ya tiene una ficha"},
    },
)
async def crear_ficha(session: SessionDep, id: IdRuta, datos: FichaCreate) -> FichaRead:
    return await service.crear_ficha(session, id, datos)


@router.get(
    "/{id}/mascotas",
    status_code=status.HTTP_200_OK,
    response_model=list[MascotaRead],
    responses={404: {"model": MensajeError, "description": "No existe el dueño"}},
)
async def listar_mascotas(session: SessionDep, id: IdRuta) -> list[MascotaRead]:
    return await service.listar_mascotas(session, id)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": MensajeError, "description": "No existe el dueño"},
        409: {"model": MensajeError, "description": "El dueño tiene mascotas a su nombre"},
    },
)
async def borrar_duenio(session: SessionDep, id: IdRuta) -> None:
    await service.borrar_duenio(session, id)
