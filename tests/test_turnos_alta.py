import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion

VALIDO = {
    "mascota_id": 1,
    "fecha": "2026-11-12T10:30:00-03:00",
    "motivo": "Control anual",
    "practicas": [{"practica_id": 1}, {"practica_id": 3}],
}


def con(**cambios) -> dict:
    return {**VALIDO, **cambios}


async def contar(sesion, tabla: str) -> int:
    return (await sesion.exec(text(f"SELECT count(*) FROM {tabla}"))).scalar_one()


async def test_lista_de_practicas_vacia_responde_422(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.post("/turnos/", json=con(practicas=[]))

    assert r.status_code == 422
    assert [e["loc"] for e in r.json()["detail"]] == [["body", "practicas"]]
    assert sentencias_app == []


SIN_PRACTICAS = {k: v for k, v in VALIDO.items() if k != "practicas"}


@pytest.mark.parametrize(
    "cuerpo, loc",
    [
        (con(fecha="2026-11-12T10:30:00"), ["body", "fecha"]),
        (con(motivo="   "), ["body", "motivo"]),
        (con(total="1.00"), ["body", "total"]),
        (con(id=50), ["body", "id"]),
        (con(practicas=[{"practica_id": 1, "precio_unitario": "1.00"}]), ["body", "practicas", 0, "precio_unitario"]),
        (SIN_PRACTICAS, ["body", "practicas"]),
        (con(mascota_id=2147483648), ["body", "mascota_id"]),
        (con(practicas=[{"practica_id": 2147483648}]), ["body", "practicas", 0, "practica_id"]),
    ],
    ids=["fecha-sin-zona", "motivo-vacio", "total", "id", "precio-en-practica", "sin-practicas", "mascota-fuera-de-rango", "practica-fuera-de-rango"],
)
async def test_contrato_de_alta_invalido_responde_422(base_con_seed, client, sesion_seed, cuerpo, loc):
    r = await client.post("/turnos/", json=cuerpo)

    assert r.status_code == 422
    assert loc in [e["loc"] for e in r.json()["detail"]]
    assert await contar(sesion_seed, "turno") == 1


EJEMPLO_CONSIGNA = {
    "id": 2,
    "fecha": "2026-11-12T13:30:00Z",
    "motivo": "Control anual",
    "total": "27000.00",
    "mascota": {"id": 1, "nombre": "Toby", "especie": "perro"},
    "practicas": [
        {"practica_id": 1, "nombre": "Consulta", "precio_unitario": "15000.00"},
        {"practica_id": 3, "nombre": "Vacuna antirrábica", "precio_unitario": "12000.00"},
    ],
}


async def test_caso_c06_ejemplo_de_la_consigna(base_con_seed, client, sesion_seed):
    r = await client.post("/turnos/", json=VALIDO)

    assert r.status_code == 201
    assert r.json() == EJEMPLO_CONSIGNA
    filas = (
        await sesion_seed.exec(
            text("SELECT practica_id, precio_unitario::text FROM turno_practica WHERE turno_id = 2 ORDER BY 1")
        )
    ).all()
    assert [tuple(f) for f in filas] == [(1, "15000.00"), (3, "12000.00")]


async def test_practicas_ordenadas_por_id_y_total_del_servidor(base_con_seed, client):
    r = await client.post("/turnos/", json=con(practicas=[{"practica_id": 4}, {"practica_id": 1}, {"practica_id": 2}]))

    assert r.status_code == 201
    assert [p["practica_id"] for p in r.json()["practicas"]] == [1, 2, 4]
    assert r.json()["total"] == "37000.00"
    detalle = await client.get(f"/turnos/{r.json()['id']}")
    assert detalle.json() == r.json()


async def test_precio_congelado_ante_cambio_del_catalogo(base_con_seed, client, sesion_seed):
    creado = (await client.post("/turnos/", json=con(practicas=[{"practica_id": 1}]))).json()
    await sesion_seed.exec(text("UPDATE practica SET precio = 20000 WHERE id = 1"))
    await sesion_seed.commit()

    r = await client.get(f"/turnos/{creado['id']}")

    assert r.json()["practicas"][0]["precio_unitario"] == "15000.00"
    assert r.json()["total"] == creado["total"] == "15000.00"


PRACTICA_INEXISTENTE = {"detail": "No existe la práctica indicada"}
FILTRADOS = ("turno_", "fkey", "pkey", "null", "insert", "asyncpg")


async def assert_nada_guardado(sesion) -> None:
    assert await contar(sesion, "turno") == 1
    assert await contar(sesion, "turno_practica") == 2


async def test_caso_c04_practica_inexistente_no_guarda_nada(base_con_seed, client, sesion_seed):
    r = await client.post("/turnos/", json=con(practicas=[{"practica_id": 1}, {"practica_id": 999}]))

    assert r.status_code == 409
    assert r.json() == PRACTICA_INEXISTENTE
    await assert_nada_guardado(sesion_seed)


@pytest.mark.parametrize(
    "cuerpo, detalle",
    [
        (con(practicas=[{"practica_id": 1}, {"practica_id": 1}]), "Una práctica no puede repetirse en el mismo turno"),
        (con(mascota_id=999), "No existe la mascota indicada"),
        (con(practicas=[{"practica_id": 0}]), PRACTICA_INEXISTENTE["detail"]),
        (con(practicas=[{"practica_id": -1}]), PRACTICA_INEXISTENTE["detail"]),
    ],
    ids=["repetida", "mascota-inexistente", "practica-cero", "practica-negativa"],
)
async def test_rechazos_del_alta_responden_409_sin_guardar_nada(base_con_seed, client, sesion_seed, cuerpo, detalle):
    r = await client.post("/turnos/", json=cuerpo)

    assert r.status_code == 409
    assert r.json() == {"detail": detalle}
    assert not any(f in r.text.lower() for f in FILTRADOS)
    await assert_nada_guardado(sesion_seed)


async def test_despues_de_un_rechazo_la_siguiente_reserva_funciona(base_con_seed, client):
    rechazo = await client.post("/turnos/", json=con(practicas=[{"practica_id": 999}]))
    r = await client.post("/turnos/", json=VALIDO)

    assert rechazo.status_code == 409
    assert r.status_code == 201
