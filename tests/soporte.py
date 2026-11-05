import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class BloqueHttp:
    titulo: str
    metodo: str
    url: str
    cabeceras: dict[str, str]
    cuerpo: bytes | None
    codigo_esperado: int


def bloques_http(ruta: Path) -> list[BloqueHttp]:
    """Bloques `###` de un archivo `.http`: petición y primer código de `# Esperado:`."""
    bloques: list[BloqueHttp] = []
    for crudo in ruta.read_text(encoding="utf-8").split("\n### ")[1:]:
        lineas = crudo.splitlines()
        esperado = next(l for l in lineas if l.startswith("# Esperado:"))
        codigo = int(re.search(r"\d{3}", esperado).group())
        peticion = [l for l in lineas[1:] if not l.startswith("#")]
        metodo, url = peticion[0].split(maxsplit=1)
        cabeceras: dict[str, str] = {}
        indice = 1
        while indice < len(peticion) and peticion[indice].strip():
            nombre, valor = peticion[indice].split(":", 1)
            cabeceras[nombre.strip()] = valor.strip()
            indice += 1
        cuerpo = "\n".join(peticion[indice + 1 :]).strip()
        bloques.append(
            BloqueHttp(lineas[0].strip(), metodo, url.strip(), cabeceras, cuerpo.encode() or None, codigo)
        )
    return bloques
