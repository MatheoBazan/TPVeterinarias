from collections.abc import Mapping
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errores import Rechazo, traducir_rechazo
from app.modules.mascotas.models import Mascota
from app.modules.mascotas.schemas import (
    MascotaConDuenioRead,
    MascotaCreate,
    MascotaRead,
    PaginaMascotas,
)

MASCOTA_INEXISTENTE: Final = "No existe la mascota"
DUENIO_INDICADO_INEXISTENTE: Final = "No existe el dueño indicado"
PAGINA_INEXISTENTE: Final = "La página pedida no existe"

RECHAZOS_ALTA: Final[Mapping[str, Rechazo]] = {
    "mascota_duenio_id_fkey": Rechazo(status.HTTP_409_CONFLICT, DUENIO_INDICADO_INEXISTENTE),
}


async def obtener_mascota(session: AsyncSession, mascota_id: int) -> MascotaConDuenioRead:
    consulta = select(Mascota).where(Mascota.id == mascota_id).options(joinedload(Mascota.duenio))
    mascota = (await session.exec(consulta)).one_or_none()
    if mascota is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MASCOTA_INEXISTENTE)
    return MascotaConDuenioRead.model_validate(mascota)


async def crear_mascota(session: AsyncSession, datos: MascotaCreate) -> MascotaRead:
    mascota = Mascota.model_validate(datos)
    session.add(mascota)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_ALTA) from exc
    return MascotaRead.model_validate(mascota)


async def listar_mascotas(session: AsyncSession, page: int, size: int) -> PaginaMascotas:
    total = (await session.exec(select(func.count()).select_from(Mascota))).one()
    pages = (total + size - 1) // size
    if page > max(pages, 1):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "type": "pagina_fuera_de_rango",
                    "loc": ["query", "page"],
                    "msg": PAGINA_INEXISTENTE,
                    "input": page,
                    "ctx": {"pages": pages},
                }
            ],
        )
    consulta = select(Mascota).order_by(Mascota.id).offset((page - 1) * size).limit(size)
    mascotas = (await session.exec(consulta)).all()
    return PaginaMascotas(
        items=[MascotaRead.model_validate(m) for m in mascotas],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
