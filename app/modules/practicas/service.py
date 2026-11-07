from collections.abc import Mapping
from typing import Final

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errores import Rechazo, traducir_rechazo
from app.modules.practicas.models import Practica
from app.modules.practicas.schemas import PracticaCreate, PracticaRead

RECHAZOS_ALTA: Final[Mapping[str, Rechazo]] = {
    "uq_practica_nombre": Rechazo(status.HTTP_409_CONFLICT, "Ya existe una práctica con ese nombre"),
}


async def listar_practicas(session: AsyncSession) -> list[PracticaRead]:
    practicas = (await session.exec(select(Practica).order_by(Practica.id))).all()
    return [PracticaRead.model_validate(p) for p in practicas]


async def crear_practica(session: AsyncSession, datos: PracticaCreate) -> PracticaRead:
    practica = Practica.model_validate(datos)
    session.add(practica)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_ALTA) from exc
    return PracticaRead.model_validate(practica)
