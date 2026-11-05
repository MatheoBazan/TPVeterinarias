import logging

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlmodel import delete, select

from app.core.errores import RECHAZO_GENERICO, Rechazo, restriccion_violada, traducir_rechazo
from app.modules.duenios.models import Duenio, FichaDuenio
from app.modules.practicas.models import Practica

pytestmark = pytest.mark.integracion


async def test_restriccion_violada_de_email_repetido_es_uq_duenio_email(base_con_seed, sesion):
    sesion.add(Duenio(nombre="Otra Ana", email="ana.gomez@example.com"))

    with pytest.raises(IntegrityError) as capturado:
        await sesion.commit()

    assert restriccion_violada(capturado.value) == "uq_duenio_email"


async def _fk_ficha_inexistente(s):
    s.add(FichaDuenio(duenio_id=999, telefono="1", direccion="d"))


async def _segunda_ficha(s):
    s.add(FichaDuenio(duenio_id=1, telefono="1", direccion="d"))


async def _borrar_con_mascotas(s):
    await s.exec(delete(Duenio).where(Duenio.id == 1))


async def _sin_email(s):
    await s.exec(text("INSERT INTO duenio (nombre) VALUES ('Sin Email')"))


@pytest.mark.parametrize(
    "escritura,esperada",
    [
        (_fk_ficha_inexistente, "ficha_duenio_duenio_id_fkey"),
        (_segunda_ficha, "uq_ficha_duenio_duenio_id"),
        (_borrar_con_mascotas, "mascota_duenio_id_fkey"),
        (_sin_email, None),
    ],
    ids=["fk_ficha", "unique_ficha", "restrict_mascotas", "not_null_sin_email"],
)
async def test_restriccion_violada_segun_la_escritura_rechazada(base_con_seed, sesion, escritura, esperada):
    with pytest.raises(IntegrityError) as capturado:
        await escritura(sesion)
        await sesion.commit()

    assert restriccion_violada(capturado.value) == esperada


RECHAZOS = {
    "uq_duenio_email": Rechazo(409, "Ya existe un dueño con ese email"),
    "ficha_duenio_duenio_id_fkey": Rechazo(404, "No existe el dueño"),
}


async def _email_repetido(s):
    s.add(Duenio(nombre="Otra Ana", email="ana.gomez@example.com"))
    await s.commit()


async def _fk_ficha_inexistente_commit(s):
    s.add(FichaDuenio(duenio_id=999, telefono="1", direccion="d"))
    await s.commit()


async def _escribir(sesion, escritura) -> IntegrityError:
    with pytest.raises(IntegrityError) as capturado:
        await escritura(sesion)
    return capturado.value


@pytest.mark.parametrize(
    "escritura,codigo,mensaje",
    [
        (_email_repetido, 409, "Ya existe un dueño con ese email"),
        (_fk_ficha_inexistente_commit, 404, "No existe el dueño"),
    ],
    ids=["email", "fk_ficha"],
)
async def test_traducir_rechazo_previsto_devuelve_su_codigo_y_mensaje(
    base_con_seed, sesion, caplog, escritura, codigo, mensaje
):
    exc = await _escribir(sesion, escritura)

    with caplog.at_level(logging.WARNING, logger="app.core.errores"):
        http = traducir_rechazo(exc, RECHAZOS)

    assert isinstance(http, HTTPException)
    assert (http.status_code, http.detail) == (codigo, mensaje)
    assert caplog.records == []


async def _not_null(s):
    await s.exec(text("INSERT INTO duenio (nombre) VALUES ('Sin Email')"))


async def _practica_nombre_repetido(s):
    s.add(Practica(nombre="Consulta", precio=1))
    await s.commit()


@pytest.mark.parametrize(
    "rechazos,escritura,restriccion",
    [
        ({"otra_restriccion": Rechazo(409, "x")}, _email_repetido, "uq_duenio_email"),
        ({}, _fk_ficha_inexistente_commit, "ficha_duenio_duenio_id_fkey"),
        (RECHAZOS, _not_null, None),
        ({}, _practica_nombre_repetido, "uq_practica_nombre"),
    ],
    ids=["mapa_sin_la_restriccion", "mapa_vacio", "not_null_sin_nombre", "practica_no_declarada"],
)
async def test_traducir_rechazo_no_previsto_responde_409_generico_y_lo_registra(
    base_con_seed, sesion, caplog, rechazos, escritura, restriccion
):
    exc = await _escribir(sesion, escritura)

    with caplog.at_level(logging.WARNING, logger="app.core.errores"):
        http = traducir_rechazo(exc, rechazos)

    assert (http.status_code, http.detail) == (409, RECHAZO_GENERICO)
    (registro,) = caplog.records
    mensaje = registro.getMessage()
    assert f"restriccion={restriccion}" in mensaje
    assert "sqlstate=23" in mensaje
    assert "ana.gomez" not in mensaje and "Sin Email" not in mensaje


async def test_despues_del_rollback_la_sesion_vuelve_a_leer(base_con_seed, sesion):
    await _escribir(sesion, _email_repetido)

    await sesion.rollback()

    assert len((await sesion.exec(select(Duenio))).all()) == 2
