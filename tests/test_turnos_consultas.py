import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion

CONTROL = ("BEGIN", "COMMIT", "ROLLBACK")


def sin_control(sentencias: list[str]) -> list[str]:
    return [s for s in sentencias if s.strip().upper() not in CONTROL]


async def insertar_turno(sesion, practicas: list[int]) -> int:
    turno_id = (
        await sesion.exec(
            text(
                "INSERT INTO turno (mascota_id, fecha, motivo, total) "
                "VALUES (1, '2026-11-20T10:00:00Z', 'x', 0) RETURNING id"
            )
        )
    ).scalar_one()
    for practica_id in practicas:
        await sesion.exec(
            text(
                "INSERT INTO turno_practica (turno_id, practica_id, precio_unitario) "
                "SELECT :t, id, precio FROM practica WHERE id = :p"
            ).bindparams(t=turno_id, p=practica_id)
        )
    await sesion.commit()
    return turno_id


async def test_detalle_usa_dos_consultas_con_una_y_tres_practicas(
    base_con_seed, client, sesion_seed, sentencias_app
):
    con_una = await insertar_turno(sesion_seed, [1])
    con_tres = await insertar_turno(sesion_seed, [1, 2, 3])

    for turno_id, cantidad in ((con_una, 1), (con_tres, 3)):
        sentencias_app.clear()
        r = await client.get(f"/turnos/{turno_id}")

        assert r.status_code == 200
        assert len(r.json()["practicas"]) == cantidad
        turno, practicas = sin_control(sentencias_app)
        assert "FROM turno" in turno and "JOIN mascota" in turno
        assert "FROM turno_practica" in practicas and "JOIN practica" in practicas


async def test_alta_rechazada_no_consulta_antes_de_escribir(base_con_seed, client, sentencias_app):
    cuerpo = {
        "mascota_id": 1,
        "fecha": "2026-11-12T10:30:00-03:00",
        "motivo": "Control",
        "practicas": [{"practica_id": 1}, {"practica_id": 999}],
    }
    sentencias_app.clear()

    r = await client.post("/turnos/", json=cuerpo)

    assert r.status_code == 409
    primera, *_ = sin_control(sentencias_app)
    assert primera.lstrip().upper().startswith("INSERT INTO TURNO ")


async def test_borrado_envia_un_solo_delete_y_la_cascada_la_hace_la_base(base_con_seed, client, sentencias_app):
    sentencias_app.clear()

    r = await client.delete("/turnos/1")

    assert r.status_code == 204
    (sentencia,) = sin_control(sentencias_app)
    assert sentencia.lstrip().upper().startswith("DELETE FROM TURNO ")
