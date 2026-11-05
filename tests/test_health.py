import os
import time

import pytest
from sqlalchemy.engine import make_url

from app.modules.health import service
from soporte import URL_NADIE_ESCUCHA, cliente_de, levantar_app

TIMEOUT_DE_PRUEBA = 0.5
MARGEN_SEGUNDOS = 1.0
SIN_BASE = {"estado": "sin base"}


# --- GET /health/live -------------------------------------------------------


@pytest.mark.integracion
async def test_live_responde_200_estado_vivo(client):
    respuesta = await client.get("/health/live")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "vivo"}


async def test_live_con_la_base_caida_responde_200_en_menos_de_un_segundo(monkeypatch):
    async with levantar_app(URL_NADIE_ESCUCHA, monkeypatch) as aplicacion:
        async with cliente_de(aplicacion) as cliente:
            inicio = time.perf_counter()
            respuesta = await cliente.get("/health/live")
            duracion = time.perf_counter() - inicio

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "vivo"}
    assert duracion < 1.0


@pytest.mark.integracion
async def test_live_no_abre_conexiones_pero_ready_si(app, client):
    pool = app.state.engine.pool

    await client.get("/health/live")
    assert (pool.checkedin(), pool.checkedout()) == (0, 0)

    await client.get("/health/ready")
    assert (pool.checkedin(), pool.checkedout()) == (1, 0)


# --- GET /health/ready ------------------------------------------------------


@pytest.mark.integracion
async def test_ready_con_base_disponible_responde_200_listo(client):
    respuesta = await client.get("/health/ready")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "listo"}


@pytest.mark.integracion
async def test_ready_repetido_devuelve_la_conexion_al_pool(app, client):
    for _ in range(2):
        respuesta = await client.get("/health/ready")
        assert respuesta.status_code == 200
        assert respuesta.json() == {"estado": "listo"}
        assert app.state.engine.pool.checkedout() == 0


async def _ready_con_url(monkeypatch, url: str):
    monkeypatch.setattr(service, "TIMEOUT_READY_SEGUNDOS", TIMEOUT_DE_PRUEBA)
    async with levantar_app(url, monkeypatch) as aplicacion:
        async with cliente_de(aplicacion) as cliente:
            inicio = time.perf_counter()
            respuesta = await cliente.get("/health/ready")
            duracion = time.perf_counter() - inicio
    return respuesta, duracion


async def test_ready_sin_base_responde_503_sin_base(monkeypatch):
    respuesta, _ = await _ready_con_url(monkeypatch, URL_NADIE_ESCUCHA)

    assert respuesta.status_code == 503
    assert respuesta.json() == SIN_BASE


async def test_ready_con_servidor_mudo_responde_503_en_tiempo_acotado(
    monkeypatch, servidor_mudo
):
    url = f"postgresql+asyncpg://u:p@127.0.0.1:{servidor_mudo}/veterinaria_test"

    respuesta, duracion = await _ready_con_url(monkeypatch, url)

    assert respuesta.status_code == 503
    assert respuesta.json() == SIN_BASE
    assert duracion < TIMEOUT_DE_PRUEBA + MARGEN_SEGUNDOS


@pytest.mark.integracion
async def test_ready_con_base_inexistente_responde_503(monkeypatch, url_base_test):
    url = make_url(os.environ["TEST_DATABASE_URL"]).set(database="base_inexistente_test")

    respuesta, _ = await _ready_con_url(monkeypatch, url.render_as_string(hide_password=False))

    assert respuesta.status_code == 503
    assert respuesta.json() == SIN_BASE


async def test_ready_nada_escucha_responde_503_antes_del_limite(monkeypatch):
    respuesta, duracion = await _ready_con_url(monkeypatch, URL_NADIE_ESCUCHA)

    assert respuesta.status_code == 503
    assert duracion < TIMEOUT_DE_PRUEBA + MARGEN_SEGUNDOS


async def test_despues_de_un_503_la_aplicacion_sigue_atendiendo(monkeypatch):
    monkeypatch.setattr(service, "TIMEOUT_READY_SEGUNDOS", TIMEOUT_DE_PRUEBA)
    async with levantar_app(URL_NADIE_ESCUCHA, monkeypatch) as aplicacion:
        async with cliente_de(aplicacion) as cliente:
            primera = await cliente.get("/health/ready")
            viva = await cliente.get("/health/live")
            segunda = await cliente.get("/health/ready")

    assert primera.status_code == 503
    assert (viva.status_code, viva.json()) == (200, {"estado": "vivo"})
    assert (segunda.status_code, segunda.json()) == (503, SIN_BASE)


# --- Contrato OpenAPI -------------------------------------------------------


async def test_openapi_declara_los_codigos_de_salud(monkeypatch):
    async with levantar_app(URL_NADIE_ESCUCHA, monkeypatch) as aplicacion:
        async with cliente_de(aplicacion) as cliente:
            esquema = (await cliente.get("/openapi.json")).json()

    assert set(esquema["paths"]["/health/ready"]["get"]["responses"]) >= {"200", "503"}
    assert "200" in esquema["paths"]["/health/live"]["get"]["responses"]
