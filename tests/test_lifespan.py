import os

import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import ConfiguracionInvalida
from app.main import crear_app
from soporte import URL_NADIE_ESCUCHA, levantar_app


@pytest.mark.integracion
async def test_lifespan_guarda_motor_y_fabrica_en_app_state(app):
    assert isinstance(app.state.engine, AsyncEngine)
    assert isinstance(app.state.session_factory, async_sessionmaker)
    esperada = make_url(os.environ["TEST_DATABASE_URL"]).database
    assert app.state.engine.url.database == esperada


@pytest.mark.parametrize(
    ("sql_echo", "esperado"), [(None, False), ("0", False), ("1", True), ("true", True)]
)
async def test_lifespan_eco_del_motor_sigue_a_sql_echo(monkeypatch, sql_echo, esperado):
    if sql_echo is None:
        monkeypatch.delenv("SQL_ECHO", raising=False)
    else:
        monkeypatch.setenv("SQL_ECHO", sql_echo)

    async with levantar_app(URL_NADIE_ESCUCHA, monkeypatch) as aplicacion:
        assert aplicacion.state.engine.echo is esperado


async def test_lifespan_arranca_y_apaga_sin_base_disponible(monkeypatch):
    async with levantar_app(URL_NADIE_ESCUCHA, monkeypatch) as aplicacion:
        assert isinstance(aplicacion.state.engine, AsyncEngine)


async def test_lifespan_sin_database_url_falla_con_configuracion_invalida(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ConfiguracionInvalida):
        async with LifespanManager(crear_app()):
            pass  # pragma: no cover


@pytest.mark.integracion
async def test_lifespan_al_apagar_cierra_el_motor_y_sus_conexiones(
    url_base_test, monkeypatch
):
    eventos: list[str] = []
    async with levantar_app(url_base_test, monkeypatch) as aplicacion:
        motor = aplicacion.state.engine
        event.listen(
            motor.sync_engine, "engine_disposed", lambda _motor: eventos.append("dispose")
        )
        async with motor.connect() as conexion:
            await conexion.execute(text("SELECT 1"))
        pool = motor.pool
        assert pool.checkedin() == 1

    assert eventos == ["dispose"]
    assert pool.checkedin() == 0
