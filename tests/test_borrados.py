import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.database import crear_fabrica_sesiones
from app.core.modelos import Duenio, FichaDuenio, Mascota, Practica, Turno
from soporte import error_postgres

pytestmark = pytest.mark.integracion


def sobre_tabla(sentencias, tabla, verbos=("SELECT", "UPDATE", "DELETE")):
    """Sentencias que empiezan con alguno de los verbos y tocan exactamente `tabla`."""
    patron = re.compile(rf"\b(FROM|UPDATE)\s+{tabla}\b", re.IGNORECASE)
    return [
        s
        for s in sentencias
        if s.lstrip().split()[0].upper() in verbos and patron.search(s)
    ]


def borra_de(sentencias, tabla):
    """Hay un `DELETE FROM <tabla>` (palabra completa: `turno` no es `turno_practica`)."""
    return any(re.match(rf"\s*DELETE FROM {tabla}(\s|$)", q, re.IGNORECASE) for q in sentencias)


async def cuantas(motor, tabla, donde="true"):
    async with motor.connect() as conn:
        return (await conn.execute(text(f"SELECT count(*) FROM {tabla} WHERE {donde}"))).scalar_one()


@pytest.mark.parametrize("cargar_practicas", [False, True], ids=["sin_cargar", "cargadas"])
async def test_borrar_turno_deja_que_la_base_borre_sus_practicas(
    base_con_seed, sentencias_sql, cargar_practicas
):
    async with crear_fabrica_sesiones(base_con_seed)() as s:
        consulta = select(Turno).where(Turno.id == 1)
        if cargar_practicas:
            consulta = consulta.options(selectinload(Turno.practicas))
        turno = (await s.exec(consulta)).one()
        sentencias_sql.clear()

        await s.delete(turno)
        await s.commit()

    assert borra_de(sentencias_sql, "turno")
    assert sobre_tabla(sentencias_sql, "turno_practica") == []
    assert await cuantas(base_con_seed, "turno") == 0
    assert await cuantas(base_con_seed, "turno_practica") == 0
    assert await cuantas(base_con_seed, "practica") == 4


@pytest.mark.parametrize("cargar_ficha", [False, True], ids=["sin_cargar", "cargada"])
async def test_borrar_duenio_con_ficha_y_sin_mascotas_borra_la_ficha_en_la_base(
    base_con_seed, sentencias_sql, cargar_ficha
):
    fabrica = crear_fabrica_sesiones(base_con_seed)
    async with fabrica() as s:
        nuevo = Duenio(nombre="Nuevo", email="nuevo@example.com")
        nuevo.ficha = FichaDuenio(telefono="1", direccion="d")
        s.add(nuevo)
        await s.commit()
        nuevo_id = nuevo.id
    async with fabrica() as s:
        consulta = select(Duenio).where(Duenio.id == nuevo_id)
        if cargar_ficha:
            consulta = consulta.options(selectinload(Duenio.ficha))
        duenio = (await s.exec(consulta)).one()
        sentencias_sql.clear()

        await s.delete(duenio)
        await s.commit()

    assert borra_de(sentencias_sql, "duenio")
    assert sobre_tabla(sentencias_sql, "ficha_duenio") == []
    assert await cuantas(base_con_seed, "duenio", f"id = {nuevo_id}") == 0
    assert await cuantas(base_con_seed, "ficha_duenio", f"duenio_id = {nuevo_id}") == 0
    assert await cuantas(base_con_seed, "ficha_duenio") == 1  # la de Ana sigue


@pytest.mark.parametrize("cargar_mascotas", [False, True], ids=["sin_cargar", "cargadas"])
async def test_borrar_duenio_con_mascotas_lo_rechaza_la_base_y_no_cambia_nada(
    base_con_seed, sentencias_sql, cargar_mascotas
):
    fabrica = crear_fabrica_sesiones(base_con_seed)
    async with fabrica() as s:
        consulta = select(Duenio).where(Duenio.id == 1)
        if cargar_mascotas:
            consulta = consulta.options(selectinload(Duenio.mascotas), selectinload(Duenio.ficha))
        duenio = (await s.exec(consulta)).one()
        sentencias_sql.clear()

        with pytest.raises(IntegrityError) as info:
            await s.delete(duenio)
            await s.commit()
        await s.rollback()

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23503", "mascota_duenio_id_fkey")
    assert sobre_tabla(sentencias_sql, "mascota", verbos=("UPDATE", "DELETE")) == []
    assert sobre_tabla(sentencias_sql, "ficha_duenio", verbos=("UPDATE", "DELETE")) == []
    async with fabrica() as otra:  # otra sesión: todo intacto
        assert (await otra.exec(select(Duenio).where(Duenio.id == 1))).one().nombre == "Ana Gómez"
        assert len((await otra.exec(select(Mascota).where(Mascota.duenio_id == 1))).all()) == 2
    assert await cuantas(base_con_seed, "ficha_duenio", "duenio_id = 1") == 1


@pytest.mark.parametrize(
    "modelo,clave,restriccion",
    [
        (Mascota, 2, "turno_mascota_id_fkey"),  # Mishi tiene el turno 1
        (Practica, 1, "turno_practica_practica_id_fkey"),  # Consulta está en el turno 1
    ],
    ids=["mascota_con_turnos", "practica_usada"],
)
@pytest.mark.parametrize("cargar_hijas", [False, True], ids=["sin_cargar", "cargadas"])
async def test_borrar_el_lado_restrict_lo_rechaza_la_base(
    base_con_seed, sentencias_sql, modelo, clave, restriccion, cargar_hijas
):
    fabrica = crear_fabrica_sesiones(base_con_seed)
    async with fabrica() as s:
        consulta = select(modelo).where(modelo.id == clave)
        if cargar_hijas:
            consulta = consulta.options(selectinload(modelo.turnos))
        fila = (await s.exec(consulta)).one()
        sentencias_sql.clear()

        with pytest.raises(IntegrityError) as info:
            await s.delete(fila)
            await s.commit()
        await s.rollback()

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23503", restriccion)
    assert [q for q in sentencias_sql if q.lstrip().upper().startswith("UPDATE")] == []
    assert await cuantas(base_con_seed, "turno") == 1
    assert await cuantas(base_con_seed, "turno_practica") == 2


@pytest.mark.parametrize(
    "modelo,clave,tabla",
    [(Mascota, 1, "mascota"), (Practica, 4, "practica")],
    ids=["Toby", "Vacuna_quintuple"],
)
async def test_borrar_sin_historial_se_acepta(base_con_seed, modelo, clave, tabla):
    async with crear_fabrica_sesiones(base_con_seed)() as s:
        fila = (await s.exec(select(modelo).where(modelo.id == clave))).one()
        await s.delete(fila)
        await s.commit()

    assert await cuantas(base_con_seed, tabla, f"id = {clave}") == 0
