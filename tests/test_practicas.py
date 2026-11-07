import inspect
from decimal import Decimal

import pytest

from app.modules.practicas.models import Practica

pytestmark = pytest.mark.integracion

CATALOGO_INICIAL = [
    {"id": 1, "nombre": "Consulta", "precio": "15000.00"},
    {"id": 2, "nombre": "Desparasitación", "precio": "8000.00"},
    {"id": 3, "nombre": "Vacuna antirrábica", "precio": "12000.00"},
    {"id": 4, "nombre": "Vacuna quíntuple", "precio": "14000.00"},
]


async def test_listar_practicas_responde_el_catalogo_inicial(base_con_seed, client):
    r = await client.get("/practicas/")

    assert r.status_code == 200
    assert r.json() == CATALOGO_INICIAL


async def test_listar_practicas_con_catalogo_vacio_responde_lista_vacia(esquema_vacio, client):
    r = await client.get("/practicas/")

    assert r.status_code == 200
    assert r.json() == []


async def test_listar_practicas_ordena_por_id(sesion, client):
    sesion.add(Practica(nombre="Zeta", precio=Decimal("10.00")))
    await sesion.commit()
    sesion.add(Practica(nombre="Alfa", precio=Decimal("20.00")))
    await sesion.commit()

    r = await client.get("/practicas/")

    assert [p["nombre"] for p in r.json()] == ["Zeta", "Alfa"]
    assert [p["id"] for p in r.json()] == [1, 2]


@pytest.mark.parametrize("extras", [0, 2], ids=["4_practicas", "6_practicas"])
async def test_listar_practicas_usa_una_sola_consulta(base_con_seed, client, sentencias_app, sesion_seed, extras):
    for i in range(extras):
        sesion_seed.add(Practica(nombre=f"Extra {i}", precio=Decimal("1.00")))
    await sesion_seed.commit()
    sentencias_app.clear()

    r = await client.get("/practicas/")

    assert len(r.json()) == 4 + extras
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("SELECT")
    assert "FROM practica" in sentencia


CASTRACION = {"nombre": "Castración", "precio": "30000.00"}
NOMBRE_REPETIDO = {"detail": "Ya existe una práctica con ese nombre"}


async def _filas(client) -> int:
    return len((await client.get("/practicas/")).json())


def _errores(r) -> list[dict]:
    return r.json()["detail"]


async def test_crear_practica_valida_responde_201(base_con_seed, client):
    r = await client.post("/practicas/", json=CASTRACION)

    assert r.status_code == 201
    assert r.json() == {"id": 5, **CASTRACION}
    assert (await client.get("/practicas/")).json()[-1] == {"id": 5, **CASTRACION}


@pytest.mark.parametrize(
    "enviado,esperado",
    [(9000, "9000.00"), ("4500.5", "4500.50"), ("1e2", "100.00")],
    ids=["entero_json", "un_decimal", "notacion_cientifica"],
)
async def test_crear_practica_devuelve_el_precio_con_dos_decimales(base_con_seed, client, enviado, esperado):
    r = await client.post("/practicas/", json={"nombre": "Nueva", "precio": enviado})

    assert r.status_code == 201
    assert r.json()["precio"] == esperado
    assert (await client.get("/practicas/")).json()[-1]["precio"] == esperado


async def test_crear_practica_guarda_el_nombre_sin_espacios(base_con_seed, client):
    r = await client.post("/practicas/", json={"nombre": "  Ecografía  ", "precio": "25000.00"})

    assert r.status_code == 201
    assert r.json()["nombre"] == "Ecografía"


@pytest.mark.parametrize("precio,tipo", [("0", "greater_than"), ("-100.00", "greater_than")])
async def test_crear_practica_con_precio_no_positivo_responde_422(base_con_seed, client, precio, tipo):
    r = await client.post("/practicas/", json={"nombre": "Mala", "precio": precio})

    assert r.status_code == 422
    assert (_errores(r)[0]["loc"], _errores(r)[0]["type"]) == (["body", "precio"], tipo)
    assert await _filas(client) == 4


@pytest.mark.parametrize(
    "precio,tipo",
    [("12.345", "decimal_max_places"), ("100000000.00", "decimal_whole_digits")],
)
async def test_crear_practica_con_precio_fuera_de_numeric_10_2_responde_422(base_con_seed, client, precio, tipo):
    r = await client.post("/practicas/", json={"nombre": "Mala", "precio": precio})

    assert r.status_code == 422
    assert (_errores(r)[0]["loc"], _errores(r)[0]["type"]) == (["body", "precio"], tipo)
    assert await _filas(client) == 4


@pytest.mark.parametrize("precio", ["abc", "NaN"])
async def test_crear_practica_con_precio_no_numerico_responde_422(base_con_seed, client, precio):
    r = await client.post("/practicas/", json={"nombre": "Rara", "precio": precio})

    assert r.status_code == 422
    assert _errores(r)[0]["loc"] == ["body", "precio"]
    assert await _filas(client) == 4


@pytest.mark.parametrize(
    "cuerpo,loc,tipo",
    [
        ({"precio": "100.00"}, ["body", "nombre"], "missing"),
        ({"nombre": "Sin precio"}, ["body", "precio"], "missing"),
        ({"nombre": "   ", "precio": "100.00"}, ["body", "nombre"], "string_too_short"),
        ({"id": 9, "nombre": "Con id", "precio": "100.00"}, ["body", "id"], "extra_forbidden"),
    ],
    ids=["sin_nombre", "sin_precio", "nombre_vacio", "con_id"],
)
async def test_crear_practica_con_cuerpo_invalido_responde_422(base_con_seed, client, cuerpo, loc, tipo):
    r = await client.post("/practicas/", json=cuerpo)

    assert r.status_code == 422
    assert (_errores(r)[0]["loc"], _errores(r)[0]["type"]) == (loc, tipo)
    assert await _filas(client) == 4


async def test_crear_practica_con_nombre_repetido_responde_409(base_con_seed, client):
    r = await client.post("/practicas/", json={"nombre": "Consulta", "precio": "20000.00"})

    assert r.status_code == 409
    assert r.json() == NOMBRE_REPETIDO
    catalogo = (await client.get("/practicas/")).json()
    assert len(catalogo) == 4
    assert catalogo[0]["precio"] == "15000.00"


@pytest.mark.parametrize("nombre", ["  Vacuna antirrábica ", "Vacuna quíntuple"])
async def test_crear_practica_con_nombre_repetido_tras_quitar_espacios_responde_409(base_con_seed, client, nombre):
    r = await client.post("/practicas/", json={"nombre": nombre, "precio": "1.00"})

    assert r.status_code == 409
    assert r.json() == NOMBRE_REPETIDO


async def test_el_409_no_expone_detalles_de_la_base(base_con_seed, client):
    r = await client.post("/practicas/", json={"nombre": "Consulta", "precio": "20000.00"})

    for prohibido in ("uq_practica_nombre", "duplicate key", "INSERT", "asyncpg"):
        assert prohibido not in r.text


async def test_despues_de_un_409_la_siguiente_alta_funciona(base_con_seed, client):
    await client.post("/practicas/", json={"nombre": "Consulta", "precio": "20000.00"})

    r = await client.post("/practicas/", json=CASTRACION)

    assert r.status_code == 201
    assert r.json()["id"] > 4


async def test_alta_repetida_no_consulta_antes_de_escribir(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.post("/practicas/", json={"nombre": "Consulta", "precio": "20000.00"})

    assert r.status_code == 409
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("INSERT INTO PRACTICA")


async def test_openapi_declara_los_codigos_de_practicas(base_con_seed, client):
    rutas = (await client.get("/openapi.json")).json()["paths"]["/practicas/"]

    assert "200" in rutas["get"]["responses"]
    assert {"201", "409", "422"} <= set(rutas["post"]["responses"])
    esquema = rutas["post"]["responses"]["409"]["content"]["application/json"]["schema"]
    assert esquema["$ref"].endswith("/MensajeError")


def test_handlers_de_practicas_son_async():
    from app.modules.practicas.router import router

    assert router.routes
    assert all(inspect.iscoroutinefunction(r.endpoint) for r in router.routes)
