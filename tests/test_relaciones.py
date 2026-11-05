from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select

from app.core.database import crear_fabrica_sesiones
from app.core.modelos import Duenio, Mascota, Practica, Turno, TurnoPractica

pytestmark = pytest.mark.integracion

FECHA = datetime(2026, 11, 12, 10, 30, tzinfo=timezone(timedelta(hours=-3)))


def test_asignar_el_duenio_a_una_mascota_la_agrega_a_su_coleccion_sin_consultas():
    duenio = Duenio(nombre="Ana", email="ana@x")
    mascota = Mascota(nombre="Toby", especie="perro")

    mascota.duenio = duenio

    assert duenio.mascotas == [mascota]


def test_asignar_la_ficha_al_duenio_apunta_la_ficha_de_vuelta():
    from app.core.modelos import FichaDuenio

    duenio = Duenio(nombre="Ana", email="ana@x")
    ficha = FichaDuenio(telefono="1", direccion="d")

    duenio.ficha = ficha

    assert ficha.duenio is duenio


async def test_alta_de_turno_con_sus_practicas_en_una_sola_transaccion(
    esquema_vacio, sesion
):
    duenio = Duenio(nombre="Ana", email="ana@x")
    mascota = Mascota(nombre="Toby", especie="perro", duenio=duenio)
    p1 = Practica(nombre="P1", precio=Decimal("10"))
    p2 = Practica(nombre="P2", precio=Decimal("20"))
    sesion.add_all([mascota, p1, p2])
    await sesion.flush()
    turno = Turno(mascota_id=mascota.id, fecha=FECHA, motivo="m", total=Decimal("30"))
    turno.practicas.append(TurnoPractica(practica_id=p1.id, precio_unitario=p1.precio))
    turno.practicas.append(TurnoPractica(practica_id=p2.id, precio_unitario=p2.precio))

    sesion.add(turno)
    await sesion.commit()

    filas = (await sesion.exec(select(TurnoPractica).order_by(TurnoPractica.practica_id))).all()
    assert [(f.turno_id, f.practica_id) for f in filas] == [(turno.id, p1.id), (turno.id, p2.id)]
    assert [f.precio_unitario for f in filas] == [Decimal("10.00"), Decimal("20.00")]


async def test_misma_practica_dos_veces_en_el_mismo_turno_falla_toda_la_transaccion(
    esquema_vacio, sesion
):
    from sqlalchemy.exc import IntegrityError

    from soporte import error_postgres

    duenio = Duenio(nombre="Ana", email="ana@x")
    mascota = Mascota(nombre="Toby", especie="perro", duenio=duenio)
    practica = Practica(nombre="P1", precio=Decimal("10"))
    sesion.add_all([mascota, practica])
    await sesion.flush()
    turno = Turno(mascota_id=mascota.id, fecha=FECHA, motivo="m", total=Decimal("20"))
    for _ in range(2):
        turno.practicas.append(
            TurnoPractica(practica_id=practica.id, precio_unitario=practica.precio)
        )
    sesion.add(turno)

    with pytest.raises(IntegrityError) as info:
        await sesion.commit()
    await sesion.rollback()

    assert error_postgres(info.value).constraint_name == "turno_practica_pkey"
    assert (await sesion.exec(select(Turno))).all() == []


async def test_ficha_de_duenio_es_un_objeto(base_con_seed):
    from app.core.modelos import FichaDuenio

    async with crear_fabrica_sesiones(base_con_seed)() as s:
        duenio = (
            await s.exec(select(Duenio).where(Duenio.id == 1).options(joinedload(Duenio.ficha)))
        ).unique().one()

    assert isinstance(duenio.ficha, FichaDuenio)
    assert duenio.ficha.duenio_id == 1


async def test_duenio_sin_ficha_devuelve_none(base_con_seed):
    async with crear_fabrica_sesiones(base_con_seed)() as s:
        duenio = (
            await s.exec(select(Duenio).where(Duenio.id == 2).options(joinedload(Duenio.ficha)))
        ).unique().one()

    assert duenio.ficha is None


@pytest.mark.parametrize("duenio_id,nombres", [(1, ["Toby", "Mishi"]), (2, ["Luna"])])
async def test_mascotas_del_duenio_con_selectinload_y_vuelta_al_mismo_duenio(
    base_con_seed, duenio_id, nombres
):
    async with crear_fabrica_sesiones(base_con_seed)() as s:
        duenio = (
            await s.exec(
                select(Duenio).where(Duenio.id == duenio_id).options(selectinload(Duenio.mascotas))
            )
        ).one()
        await s.close()
        # ya sin sesión: sólo lo cargado es accesible
        assert sorted(m.nombre for m in duenio.mascotas) == sorted(nombres)


async def test_turno_con_mascota_y_practicas_accesible_despues_de_cerrar_la_sesion(base_con_seed):
    async with crear_fabrica_sesiones(base_con_seed)() as s:
        turno = (
            await s.exec(
                select(Turno)
                .where(Turno.id == 1)
                .options(
                    joinedload(Turno.mascota),
                    selectinload(Turno.practicas).joinedload(TurnoPractica.practica),
                )
            )
        ).one()
    # sesión cerrada

    assert turno.mascota.nombre == "Mishi"
    assert sorted((tp.practica.nombre, tp.practica.precio) for tp in turno.practicas) == [
        ("Consulta", Decimal("15000.00")),
        ("Desparasitación", Decimal("8000.00")),
    ]


async def test_mascotas_cargadas_apuntan_de_vuelta_al_mismo_duenio(base_con_seed):
    async with crear_fabrica_sesiones(base_con_seed)() as s:
        duenio = (
            await s.exec(
                select(Duenio).where(Duenio.id == 1).options(selectinload(Duenio.mascotas))
            )
        ).one()
        mascotas = duenio.mascotas
        assert len(mascotas) == 2
        assert all(m.duenio is duenio for m in mascotas)
