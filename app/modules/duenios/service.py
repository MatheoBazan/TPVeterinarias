from collections.abc import Mapping
from operator import attrgetter
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errores import Rechazo, traducir_rechazo
from app.modules.duenios.models import Duenio, FichaDuenio
from app.modules.duenios.schemas import (
    DuenioConFichaRead,
    DuenioCreate,
    DuenioRead,
    DuenioUpdate,
    FichaCreate,
    FichaRead,
)
from app.modules.mascotas.schemas import MascotaRead

DUENIO_INEXISTENTE: Final = "No existe el dueño"

RECHAZOS_EMAIL: Final[Mapping[str, Rechazo]] = {
    "uq_duenio_email": Rechazo(status.HTTP_409_CONFLICT, "Ya existe un dueño con ese email"),
}

RECHAZOS_FICHA: Final[Mapping[str, Rechazo]] = {
    "uq_ficha_duenio_duenio_id": Rechazo(status.HTTP_409_CONFLICT, "El dueño ya tiene una ficha"),
    "ficha_duenio_duenio_id_fkey": Rechazo(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE),
}

RECHAZOS_BORRADO: Final[Mapping[str, Rechazo]] = {
    "mascota_duenio_id_fkey": Rechazo(
        status.HTTP_409_CONFLICT, "No se puede borrar el dueño: tiene mascotas a su nombre"
    ),
}


async def _duenio_con_ficha(session: AsyncSession, duenio_id: int) -> Duenio | None:
    """El dueño con su ficha en una sola sentencia (la lectura que la respuesta necesita)."""
    consulta = select(Duenio).where(Duenio.id == duenio_id).options(joinedload(Duenio.ficha))
    return (await session.exec(consulta)).one_or_none()


async def obtener_duenio(session: AsyncSession, duenio_id: int) -> DuenioConFichaRead:
    duenio = await _duenio_con_ficha(session, duenio_id)
    if duenio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE)
    return DuenioConFichaRead.model_validate(duenio)


async def crear_duenio(session: AsyncSession, datos: DuenioCreate) -> DuenioRead:
    duenio = Duenio.model_validate(datos)
    session.add(duenio)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_EMAIL) from exc
    return DuenioRead.model_validate(duenio)


async def actualizar_duenio(
    session: AsyncSession, duenio_id: int, datos: DuenioUpdate
) -> DuenioConFichaRead:
    duenio = await _duenio_con_ficha(session, duenio_id)
    if duenio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE)
    duenio.sqlmodel_update(datos.model_dump(exclude_unset=True))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_EMAIL) from exc
    return DuenioConFichaRead.model_validate(duenio)


async def crear_ficha(session: AsyncSession, duenio_id: int, datos: FichaCreate) -> FichaRead:
    ficha = FichaDuenio.model_validate(datos, update={"duenio_id": duenio_id})
    session.add(ficha)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_FICHA) from exc
    return FichaRead.model_validate(ficha)


async def listar_mascotas(session: AsyncSession, duenio_id: int) -> list[MascotaRead]:
    consulta = select(Duenio).where(Duenio.id == duenio_id).options(selectinload(Duenio.mascotas))
    duenio = (await session.exec(consulta)).one_or_none()
    if duenio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE)
    return [MascotaRead.model_validate(m) for m in sorted(duenio.mascotas, key=attrgetter("id"))]


async def borrar_duenio(session: AsyncSession, duenio_id: int) -> None:
    try:
        resultado = await session.exec(delete(Duenio).where(Duenio.id == duenio_id))
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_BORRADO) from exc
    if resultado.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE)
    await session.commit()
