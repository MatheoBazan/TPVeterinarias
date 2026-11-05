from typing import Annotated

import pytest
from asgi_lifespan import LifespanManager
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import SessionDep
from app.main import crear_app

pytestmark = pytest.mark.integracion


@pytest.fixture
async def sonda(url_base_test):
    """App con una ruta sonda que expone las sesiones que recibe."""
    sesiones: list[AsyncSession] = []
    aplicacion = crear_app()

    async def misma_sesion(session: SessionDep) -> AsyncSession:
        return session

    @aplicacion.get("/_sonda")
    async def _sonda(
        session: SessionDep, otra: Annotated[AsyncSession, Depends(misma_sesion)]
    ) -> dict[str, bool]:
        sesiones.append(session)
        await session.exec(text("SELECT 1"))
        return {"misma": session is otra}

    async with LifespanManager(aplicacion):
        transporte = ASGITransport(app=aplicacion)
        async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
            yield aplicacion, cliente, sesiones


async def test_get_session_dos_peticiones_reciben_sesiones_distintas(sonda):
    _, cliente, sesiones = sonda

    await cliente.get("/_sonda")
    await cliente.get("/_sonda")

    assert len(sesiones) == 2
    assert sesiones[0] is not sesiones[1]


async def test_get_session_dentro_de_una_peticion_la_sesion_es_la_misma(sonda):
    _, cliente, _ = sonda

    respuesta = await cliente.get("/_sonda")

    assert respuesta.json() == {"misma": True}


async def test_get_session_entrega_asyncsession_de_sqlmodel_sin_expirar_al_confirmar(sonda):
    _, cliente, sesiones = sonda

    await cliente.get("/_sonda")

    assert isinstance(sesiones[0], AsyncSession)
    assert sesiones[0].sync_session.expire_on_commit is False


async def test_get_session_devuelve_la_conexion_al_pool_al_terminar(sonda):
    aplicacion, cliente, _ = sonda

    respuesta = await cliente.get("/_sonda")

    assert respuesta.status_code == 200
    assert aplicacion.state.engine.pool.checkedout() == 0
