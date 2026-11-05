"""Traducción de los rechazos de la base (IntegrityError) a respuestas HTTP con mensaje propio."""
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

RECHAZO_GENERICO: Final = "La base rechazó la escritura"


class MensajeError(SQLModel):
    """Cuerpo de los 404/409 (el mismo formato que usa FastAPI); sólo documenta OpenAPI."""

    detail: str


@dataclass(frozen=True)
class Rechazo:
    status_code: int
    mensaje: str


def restriccion_violada(exc: IntegrityError) -> str | None:
    """Nombre de la restricción que rechazó la escritura.

    exc.orig es el error adaptado por SQLAlchemy (trae sqlstate); su __cause__ es la
    excepción de asyncpg, la única que trae constraint_name.
    """
    causa = exc.orig.__cause__ if exc.orig is not None else None
    return getattr(causa, "constraint_name", None)


def traducir_rechazo(exc: IntegrityError, rechazos: Mapping[str, Rechazo]) -> HTTPException:
    """HTTPException prevista para la restricción violada; si no está en `rechazos`, 409 genérico."""
    restriccion = restriccion_violada(exc)
    rechazo = rechazos.get(restriccion)
    if rechazo is None:
        # Sólo restricción y SQLSTATE: nunca los valores ni credenciales.
        logger.warning(
            "Rechazo no previsto de la base: restriccion=%s sqlstate=%s",
            restriccion,
            getattr(exc.orig, "sqlstate", None),
        )
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=RECHAZO_GENERICO)
    return HTTPException(status_code=rechazo.status_code, detail=rechazo.mensaje)
