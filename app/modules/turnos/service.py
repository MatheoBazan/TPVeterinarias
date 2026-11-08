from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from asyncpg.exceptions import NotNullViolationError
from fastapi import HTTPException, status
from sqlalchemy import ARRAY, Integer, bindparam, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errores import Rechazo, traducir_rechazo
from app.modules.turnos.models import Turno, TurnoPractica
from app.modules.turnos.schemas import (
    MascotaDeTurnoRead,
    PracticaDeTurnoRead,
    TurnoCreate,
    TurnoRead,
)

TURNO_INEXISTENTE: Final = "No existe el turno"
PRACTICA_INEXISTENTE: Final = "No existe la práctica indicada"

RECHAZOS_ALTA: Final[Mapping[str, Rechazo]] = {
    "turno_mascota_id_fkey": Rechazo(status.HTTP_409_CONFLICT, "No existe la mascota indicada"),
    "turno_practica_pkey": Rechazo(
        status.HTTP_409_CONFLICT, "Una práctica no puede repetirse en el mismo turno"
    ),
    # Defensivo: con INSERTAR_PRACTICAS una práctica inexistente la rechaza el NOT NULL, no la FK.
    "turno_practica_practica_id_fkey": Rechazo(status.HTTP_409_CONFLICT, PRACTICA_INEXISTENTE),
}

# El precio lo copia la base en la misma sentencia que escribe (design D-1): sin consulta previa
# al catálogo y sin ventana entre leer el precio y guardarlo. Una práctica inexistente deja
# precio_unitario en NULL (LEFT JOIN) y la rechaza el NOT NULL; una repetida, la PK compuesta.
INSERTAR_PRACTICAS: Final = text(
    """
    INSERT INTO turno_practica (turno_id, practica_id, precio_unitario)
    SELECT :turno_id, pedida.practica_id, practica.precio
    FROM unnest(:ids) WITH ORDINALITY AS pedida(practica_id, orden)
    LEFT JOIN practica ON practica.id = pedida.practica_id
    ORDER BY pedida.orden
    RETURNING precio_unitario
    """
).bindparams(bindparam("ids", type_=ARRAY(Integer)))


def traducir_rechazo_alta(exc: IntegrityError) -> HTTPException:
    """El NOT NULL no informa nombre de restricción: se reconoce por la columna (design D-2)."""
    causa = exc.orig.__cause__ if exc.orig is not None else None
    if isinstance(causa, NotNullViolationError) and causa.column_name == "precio_unitario":
        return HTTPException(status.HTTP_409_CONFLICT, PRACTICA_INEXISTENTE)
    return traducir_rechazo(exc, RECHAZOS_ALTA)


def a_lectura(turno: Turno) -> TurnoRead:
    """Contrato de salida: el precio sale de turno_practica (congelado), el nombre del catálogo."""
    return TurnoRead(
        id=turno.id,
        fecha=turno.fecha,
        motivo=turno.motivo,
        total=turno.total,
        mascota=MascotaDeTurnoRead.model_validate(turno.mascota),
        practicas=[
            PracticaDeTurnoRead(
                practica_id=tp.practica_id,
                nombre=tp.practica.nombre,
                precio_unitario=tp.precio_unitario,
            )
            for tp in sorted(turno.practicas, key=lambda tp: tp.practica_id)
        ],
    )


async def obtener_turno(session: AsyncSession, turno_id: int) -> TurnoRead:
    # Dos SELECT fijos: turno JOIN mascota, y turno_practica JOIN practica (D-4).
    # populate_existing: el alta relee en la misma sesión un turno que ya está en el identity map.
    consulta = (
        select(Turno)
        .where(Turno.id == turno_id)
        .options(
            joinedload(Turno.mascota),
            selectinload(Turno.practicas).joinedload(TurnoPractica.practica),
        )
        .execution_options(populate_existing=True)
    )
    turno = (await session.exec(consulta)).one_or_none()
    if turno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, TURNO_INEXISTENTE)
    return a_lectura(turno)


async def crear_turno(session: AsyncSession, datos: TurnoCreate) -> TurnoRead:
    turno = Turno(mascota_id=datos.mascota_id, fecha=datos.fecha, motivo=datos.motivo, total=Decimal("0"))
    session.add(turno)
    try:
        await session.flush()
        precios = (
            await session.exec(
                INSERTAR_PRACTICAS.bindparams(
                    turno_id=turno.id, ids=[p.practica_id for p in datos.practicas]
                )
            )
        ).scalars().all()
        turno.total = sum(precios, start=Decimal("0"))
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()  # todo o nada: ni el turno ni sus prácticas
        raise traducir_rechazo_alta(exc) from exc
    return await obtener_turno(session, turno.id)


async def borrar_turno(session: AsyncSession, turno_id: int) -> None:
    # Las filas de turno_practica las borra la base (ON DELETE CASCADE, RN-09), no el ORM.
    resultado = await session.exec(delete(Turno).where(Turno.id == turno_id))
    if resultado.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, TURNO_INEXISTENTE)
    await session.commit()
