import asyncio
import logging

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

# Se lee en cada llamada (no se copia): los tests la bajan con monkeypatch.
TIMEOUT_READY_SEGUNDOS: float = 2.0


async def base_disponible(session: AsyncSession) -> bool:
    """True si la base contesta `SELECT 1` dentro del tiempo máximo."""
    try:
        async with asyncio.timeout(TIMEOUT_READY_SEGUNDOS):
            resultado = await session.exec(text("SELECT 1"))
            return resultado.scalar_one() == 1
    except Exception as exc:  # CancelledError es BaseException: se propaga
        logger.warning("La base no contesta a SELECT 1 (%s)", type(exc).__name__)
        return False
