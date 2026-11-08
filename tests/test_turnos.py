import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion

TURNO_1 = {
    "id": 1,
    "fecha": "2026-11-10T12:00:00Z",
    "motivo": "Control y desparasitación",
    "total": "23000.00",
    "mascota": {"id": 2, "nombre": "Mishi", "especie": "gato"},
    "practicas": [
        {"practica_id": 1, "nombre": "Consulta", "precio_unitario": "15000.00"},
        {"practica_id": 2, "nombre": "Desparasitación", "precio_unitario": "8000.00"},
    ],
}


async def test_detalle_del_turno_del_seed(base_con_seed, client):
    r = await client.get("/turnos/1")

    assert r.status_code == 200
    assert r.json() == TURNO_1


async def test_turno_inexistente_responde_404(base_con_seed, client):
    r = await client.get("/turnos/999")

    assert r.status_code == 404
    assert r.json() == {"detail": "No existe el turno"}


async def test_id_no_entero_responde_422_sin_sentencias(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.get("/turnos/abc")

    assert r.status_code == 422
    assert sentencias_app == []


async def test_caso_c05_borrar_turno_borra_sus_practicas(base_con_seed, client, sesion_seed):
    r = await client.delete("/turnos/1")

    assert r.status_code == 204
    assert r.content == b""
    assert (await client.get("/turnos/1")).status_code == 404
    quedan = (await sesion_seed.exec(text("SELECT count(*) FROM turno_practica WHERE turno_id = 1"))).scalar_one()
    assert quedan == 0
    assert len((await client.get("/practicas/")).json()) == 4


async def test_borrar_turno_inexistente_responde_404(base_con_seed, client):
    r = await client.delete("/turnos/999")

    assert r.status_code == 404
    assert r.json() == {"detail": "No existe el turno"}
