import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion


@pytest.mark.parametrize("mascota_id", [1, 3])
async def test_detalle_de_mascota_usa_una_sola_consulta(base_con_seed, client, sentencias_app, mascota_id):
    sentencias_app.clear()

    r = await client.get(f"/mascotas/{mascota_id}")

    assert r.status_code == 200
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("SELECT")
    assert "FROM mascota" in sentencia
    assert "JOIN duenio" in sentencia


@pytest.mark.parametrize("valor", ["abc", "2147483648"])
async def test_id_de_ruta_invalido_no_envia_sentencias(base_con_seed, client, sentencias_app, valor):
    sentencias_app.clear()

    r = await client.get(f"/mascotas/{valor}")

    assert r.status_code == 422
    assert sentencias_app == []


async def test_alta_con_duenio_inexistente_no_consulta_antes_de_escribir(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.post("/mascotas/", json={"nombre": "Fantasma", "especie": "gato", "duenio_id": 999})

    assert r.status_code == 409
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("INSERT INTO MASCOTA")


@pytest.mark.parametrize("size", [1, 3, 20])
async def test_listado_usa_dos_consultas(base_con_seed, client, sesion_seed, sentencias_app, size):
    await sesion_seed.exec(
        text(
            "INSERT INTO mascota (nombre, especie, duenio_id) "
            "SELECT 'm' || g, 'perro', 1 FROM generate_series(1, 22) AS g"
        )
    )
    await sesion_seed.commit()
    sentencias_app.clear()

    r = await client.get(f"/mascotas/?size={size}")

    assert r.status_code == 200
    assert len(r.json()["items"]) == size
    conteo, pagina = sentencias_app
    assert "count" in conteo.lower()
    assert "count" not in pagina.lower()
    for sentencia in (conteo, pagina):
        assert "FROM mascota" in sentencia
        assert "duenio" not in sentencia.replace("duenio_id", "")


@pytest.mark.parametrize("consulta", ["size=0", "page=abc"])
async def test_parametros_invalidos_no_envian_sentencias(base_con_seed, client, sentencias_app, consulta):
    sentencias_app.clear()

    r = await client.get(f"/mascotas/?{consulta}")

    assert r.status_code == 422
    assert sentencias_app == []


async def test_pagina_fuera_de_rango_solo_cuenta(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.get("/mascotas/?page=5")

    assert r.status_code == 422
    (sentencia,) = sentencias_app
    assert "count" in sentencia.lower()
    assert "FROM mascota" in sentencia
