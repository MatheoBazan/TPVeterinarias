import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion

TOBY = {"id": 1, "nombre": "Toby", "especie": "perro", "duenio_id": 1}
MISHI = {"id": 2, "nombre": "Mishi", "especie": "gato", "duenio_id": 1}
LUNA = {"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2}


def fuera_de_rango(page: int, pages: int) -> dict:
    return {
        "detail": [
            {
                "type": "pagina_fuera_de_rango",
                "loc": ["query", "page"],
                "msg": "La página pedida no existe",
                "input": page,
                "ctx": {"pages": pages},
            }
        ]
    }


# --- Envoltorio ---


async def test_listado_por_defecto_devuelve_el_envoltorio(base_con_seed, client):
    r = await client.get("/mascotas/")

    assert r.status_code == 200
    assert r.json() == {"items": [TOBY, MISHI, LUNA], "total": 3, "page": 1, "size": 20, "pages": 1}


async def test_ultima_pagina_incompleta(base_con_seed, client):
    r = await client.get("/mascotas/?page=2&size=2")

    assert r.status_code == 200
    assert r.json() == {"items": [LUNA], "total": 3, "page": 2, "size": 2, "pages": 2}


@pytest.mark.parametrize(
    "consulta,ids,pages",
    [("page=1&size=3", [1, 2, 3], 1), ("page=3&size=1", [3], 3)],
    ids=["una_pagina_exacta", "ultima_de_tres"],
)
async def test_pagina_en_el_borde(base_con_seed, client, consulta, ids, pages):
    r = await client.get(f"/mascotas/?{consulta}")

    assert r.status_code == 200
    cuerpo = r.json()
    assert [m["id"] for m in cuerpo["items"]] == ids
    assert cuerpo["total"] == 3
    assert cuerpo["pages"] == pages


@pytest.mark.parametrize(
    "size,ids,pages",
    [(1, [1], 3), (100, [1, 2, 3], 1)],
)
async def test_tamanios_en_el_limite(base_con_seed, client, size, ids, pages):
    r = await client.get(f"/mascotas/?size={size}")

    assert r.status_code == 200
    cuerpo = r.json()
    assert [m["id"] for m in cuerpo["items"]] == ids
    assert cuerpo["size"] == size
    assert cuerpo["pages"] == pages


async def test_listado_ordenado_por_id_aunque_cambie_el_orden_fisico(base_con_seed, client, sesion_seed):
    await sesion_seed.exec(text("UPDATE mascota SET nombre = 'Toby' WHERE id = 1"))
    await sesion_seed.commit()

    r = await client.get("/mascotas/")

    assert [m["id"] for m in r.json()["items"]] == [1, 2, 3]


async def test_listado_vacio_responde_la_primera_pagina(esquema_vacio, client):
    r = await client.get("/mascotas/")

    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}


# --- Tamaño y página inválidos ---


@pytest.mark.parametrize(
    "valor,tipo",
    [("0", "greater_than_equal"), ("101", "less_than_equal"), ("-5", "greater_than_equal"), ("abc", "int_parsing")],
)
async def test_tamanio_invalido_responde_422(base_con_seed, client, valor, tipo):
    r = await client.get(f"/mascotas/?size={valor}")

    assert r.status_code == 422
    (error,) = r.json()["detail"]
    assert error["loc"] == ["query", "size"]
    assert error["type"] == tipo


@pytest.mark.parametrize(
    "valor,tipo",
    [("0", "greater_than_equal"), ("-1", "greater_than_equal"), ("abc", "int_parsing")],
)
async def test_pagina_invalida_responde_422(base_con_seed, client, valor, tipo):
    r = await client.get(f"/mascotas/?page={valor}")

    assert r.status_code == 422
    (error,) = r.json()["detail"]
    assert error["loc"] == ["query", "page"]
    assert error["type"] == tipo


# --- Página fuera de rango ---


async def test_pagina_mas_alla_de_pages_responde_422(base_con_seed, client):
    r = await client.get("/mascotas/?page=3&size=2")

    assert r.status_code == 422
    assert r.json() == fuera_de_rango(3, 2)


async def test_pagina_2_con_valores_por_defecto_responde_422(base_con_seed, client):
    r = await client.get("/mascotas/?page=2")

    assert r.status_code == 422
    assert r.json() == fuera_de_rango(2, 1)


async def test_sin_mascotas_solo_la_primera_pagina_responde(esquema_vacio, client):
    primera = await client.get("/mascotas/?page=1")
    segunda = await client.get("/mascotas/?page=2")

    assert primera.status_code == 200
    assert primera.json()["items"] == []
    assert primera.json()["pages"] == 0
    assert segunda.status_code == 422
    assert segunda.json() == fuera_de_rango(2, 0)
