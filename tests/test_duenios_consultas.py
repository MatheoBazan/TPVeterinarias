import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion


@pytest.mark.parametrize("duenio_id", [1, 2], ids=["con_ficha", "sin_ficha"])
async def test_detalle_de_duenio_usa_una_sola_consulta(base_con_seed, client, sentencias_app, duenio_id):
    sentencias_app.clear()

    r = await client.get(f"/duenios/{duenio_id}")

    assert r.status_code == 200
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("SELECT")
    assert "JOIN ficha_duenio" in sentencia


async def test_alta_con_email_repetido_no_consulta_antes_de_escribir(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.post("/duenios/", json={"nombre": "Otra Ana", "email": "ana.gomez@example.com"})

    assert r.status_code == 409
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("INSERT INTO DUENIO")


async def test_patch_obtiene_la_ficha_en_la_misma_consulta(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.patch("/duenios/1", json={"nombre": "Ana María Gómez"})

    assert r.status_code == 200
    assert r.json()["ficha"]["id"] == 1
    lecturas = [s for s in sentencias_app if s.lstrip().upper().startswith("SELECT")]
    escrituras = [s for s in sentencias_app if s.lstrip().upper().startswith("UPDATE")]
    assert len(sentencias_app) == 2
    assert len(lecturas) == 1 and "JOIN ficha_duenio" in lecturas[0]
    assert len(escrituras) == 1 and escrituras[0].lstrip().upper().startswith("UPDATE DUENIO")
    assert not any("email" in s.lower().split("where")[-1] for s in sentencias_app)


@pytest.mark.parametrize(
    "duenio_id,codigo",
    [(999, 404), (1, 409)],
    ids=["duenio_inexistente", "segunda_ficha"],
)
async def test_alta_de_ficha_rechazada_envia_solo_el_insert(base_con_seed, client, sentencias_app, duenio_id, codigo):
    sentencias_app.clear()

    r = await client.post(f"/duenios/{duenio_id}/ficha", json={"telefono": "1", "direccion": "d"})

    assert r.status_code == codigo
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("INSERT INTO FICHA_DUENIO")


@pytest.mark.parametrize(
    "duenio_id,cantidad",
    [(2, 1), (1, 2), (3, 4)],
    ids=["una", "dos", "cuatro"],
)
async def test_mascotas_del_duenio_usan_dos_consultas(
    base_con_seed, client, sesion, sentencias_app, duenio_id, cantidad
):
    await sesion.exec(text("INSERT INTO duenio (nombre, email) VALUES ('Cuatro', 'cuatro@example.com')"))
    await sesion.exec(
        text(
            "INSERT INTO mascota (nombre, especie, duenio_id) VALUES "
            "('a', 'perro', 3), ('b', 'perro', 3), ('c', 'gato', 3), ('d', 'gato', 3)"
        )
    )
    await sesion.commit()
    sentencias_app.clear()

    r = await client.get(f"/duenios/{duenio_id}/mascotas")

    assert r.status_code == 200 and len(r.json()) == cantidad
    assert len(sentencias_app) == 2
    assert "FROM duenio" in sentencias_app[0]
    assert "FROM mascota" in sentencias_app[1]


async def test_mascotas_de_duenio_inexistente_envia_una_sola_consulta(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.get("/duenios/999/mascotas")

    assert r.status_code == 404
    assert len(sentencias_app) == 1


@pytest.mark.parametrize(
    "duenio_id,codigo",
    [(999, 404), (1, 409), (3, 204)],
    ids=["inexistente", "con_mascotas", "borrable"],
)
async def test_borrado_envia_una_unica_sentencia_delete(base_con_seed, client, sentencias_app, duenio_id, codigo):
    await client.post("/duenios/", json={"nombre": "Lucía", "email": "lucia@example.com"})
    sentencias_app.clear()

    r = await client.delete(f"/duenios/{duenio_id}")

    assert r.status_code == codigo
    (sentencia,) = sentencias_app
    assert sentencia.lstrip().upper().startswith("DELETE FROM DUENIO")
