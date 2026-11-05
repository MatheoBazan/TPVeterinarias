import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Configuracion
from app.core.database import crear_fabrica_sesiones, crear_motor

from soporte import abrir_servidor_mudo, cliente_de, levantar_app, validar_url_de_test


@pytest.fixture
def url_base_test(monkeypatch: pytest.MonkeyPatch) -> str:
    """URL de `veterinaria_test` validada; la deja como DATABASE_URL del proceso."""
    url = validar_url_de_test(os.environ.get("TEST_DATABASE_URL"))
    monkeypatch.setenv("DATABASE_URL", url)
    return url


@pytest.fixture
async def app(url_base_test: str, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    async with levantar_app(url_base_test, monkeypatch) as aplicacion:
        yield aplicacion


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with cliente_de(app) as cliente:
        yield cliente


@pytest.fixture
async def servidor_mudo() -> AsyncIterator[int]:
    """Puerto de un servidor TCP que acepta conexiones y nunca contesta."""
    servidor, escritores = await abrir_servidor_mudo()
    try:
        yield servidor.sockets[0].getsockname()[1]
    finally:
        for escritor in list(escritores):
            escritor.close()
        servidor.close()
        await servidor.wait_closed()


@pytest.fixture
async def motor_test(url_base_test: str) -> AsyncIterator[AsyncEngine]:
    """Motor sobre `veterinaria_test` (guard `_test` de `url_base_test`)."""
    motor = crear_motor(Configuracion(database_url=url_base_test, sql_echo=False))
    try:
        yield motor
    finally:
        await motor.dispose()


@pytest.fixture
async def esquema_vacio(motor_test: AsyncEngine) -> AsyncEngine:
    """Las seis tablas recién creadas y vacías, ids desde 1."""
    from reiniciar import recrear_esquema

    await recrear_esquema(motor_test)
    return motor_test


@pytest.fixture
async def sesion(esquema_vacio: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with crear_fabrica_sesiones(esquema_vacio)() as s:
        yield s


@pytest.fixture
def sentencias_sql(motor_test: AsyncEngine) -> Iterator[list[str]]:
    """Sentencias SQL que el motor de test envía a la base (listener, sin `echo`)."""
    capturadas: list[str] = []

    def al_ejecutar(conn, cursor, statement, parameters, context, executemany):
        capturadas.append(statement)

    event.listen(motor_test.sync_engine, "before_cursor_execute", al_ejecutar)
    try:
        yield capturadas
    finally:
        event.remove(motor_test.sync_engine, "before_cursor_execute", al_ejecutar)


@pytest.fixture
async def base_con_seed(esquema_vacio: AsyncEngine) -> AsyncEngine:
    """Esquema recién creado con los datos iniciales ya confirmados (sesión propia)."""
    from reiniciar import cargar_datos_iniciales

    async with crear_fabrica_sesiones(esquema_vacio)() as s:
        await cargar_datos_iniciales(s)
    return esquema_vacio
