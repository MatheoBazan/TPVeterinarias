import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError


def validar_url_de_test(url: str | None) -> str:
    """Devuelve la URL si apunta a una base `*_test`; si no, hace fallar el test."""
    if not url or not url.strip():
        pytest.fail(
            "Falta TEST_DATABASE_URL: copiá env.example a .env y completala "
            "(la base de tests debe terminar en _test)."
        )
    base = make_url(url).database or ""
    if not base.endswith("_test"):
        pytest.fail(
            "TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test "
            "para no tocar la base de desarrollo."
        )
    return url


URL_NADIE_ESCUCHA = "postgresql+asyncpg://nadie:nada@127.0.0.1:1/inexistente"


@asynccontextmanager
async def levantar_app(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    """Levanta `crear_app()` con su lifespan real apuntando a `url`."""
    from app.main import crear_app

    monkeypatch.setenv("DATABASE_URL", url)
    aplicacion = crear_app()
    async with LifespanManager(aplicacion):
        yield aplicacion


@asynccontextmanager
async def cliente_de(aplicacion: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=aplicacion), base_url="http://test"
    ) as cliente:
        yield cliente


async def abrir_servidor_mudo() -> tuple[asyncio.Server, set[asyncio.StreamWriter]]:
    """Servidor TCP que acepta conexiones y nunca envía bytes."""
    escritores: set[asyncio.StreamWriter] = set()

    async def manejador(
        lector: asyncio.StreamReader, escritor: asyncio.StreamWriter
    ) -> None:
        escritores.add(escritor)
        await lector.read()  # hasta EOF; nunca escribe

    servidor = await asyncio.start_server(manejador, "127.0.0.1", 0)
    return servidor, escritores


def error_postgres(exc: DBAPIError) -> asyncpg.PostgresError:
    """Excepción original de asyncpg (con `sqlstate` y `constraint_name`) de un error del ORM."""
    original = exc.orig.__cause__ if exc.orig is not None else None
    if not isinstance(original, asyncpg.PostgresError):
        pytest.fail(f"El error no viene de PostgreSQL: {exc!r}")
    return original
