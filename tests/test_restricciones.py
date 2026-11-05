from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.practicas.models import Practica
from app.modules.turnos.models import Turno
from soporte import error_postgres

pytestmark = pytest.mark.integracion


async def ejecutar(motor, sql, **parametros):
    async with motor.begin() as conn:
        return await conn.execute(text(sql), parametros)


@pytest.fixture
async def padres(esquema_vacio):
    """Dos dueños, una mascota (dueño 1), dos prácticas y dos turnos (mascota 1), con ids 1 y 2."""
    async with esquema_vacio.begin() as conn:
        for sql in (
            "INSERT INTO duenio (nombre, email) VALUES ('A', 'a@x'), ('B', 'b@x')",
            "INSERT INTO mascota (nombre, especie, duenio_id) VALUES ('M', 'perro', 1)",
            "INSERT INTO practica (nombre, precio) VALUES ('P1', 1), ('P2', 2)",
            "INSERT INTO turno (mascota_id, fecha, motivo, total) VALUES "
            "(1, '2026-11-10T09:00:00-03:00', 'm', 0), (1, '2026-11-11T09:00:00-03:00', 'm', 0)",
        ):
            await conn.execute(text(sql))
    return esquema_vacio


async def contar(motor, tabla):
    async with motor.connect() as conn:
        return (await conn.execute(text(f"SELECT count(*) FROM {tabla}"))).scalar_one()


@pytest.mark.parametrize(
    "valor,esperado",
    [(15000, Decimal("15000.00")), (Decimal("0.10"), Decimal("0.10"))],
)
async def test_precio_vuelve_como_decimal_exacto(sesion, valor, esperado):
    sesion.add(Practica(nombre="p", precio=valor))
    await sesion.commit()

    leido = (await sesion.exec(text("SELECT precio FROM practica"))).scalar_one()

    assert isinstance(leido, Decimal)
    assert leido == esperado
    assert str(leido) == str(esperado)


async def test_fecha_con_desplazamiento_conserva_el_instante(padres, sesion):
    local = datetime(2026, 11, 12, 10, 30, tzinfo=timezone(timedelta(hours=-3)))
    sesion.add(Turno(mascota_id=1, fecha=local, motivo="con zona", total=Decimal("0")))
    await sesion.commit()

    leida = (
        await sesion.exec(text("SELECT fecha FROM turno WHERE motivo = 'con zona'"))
    ).scalar_one()

    assert leida.tzinfo is not None
    assert leida == local
    assert leida.astimezone(timezone.utc) == datetime(2026, 11, 12, 13, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "sql,tabla",
    [
        ("INSERT INTO mascota (nombre, especie) VALUES ('Toby', 'perro')", "mascota"),
        ("INSERT INTO duenio (nombre) VALUES ('Ana')", "duenio"),
    ],
)
async def test_columna_obligatoria_ausente_se_rechaza_con_not_null(esquema_vacio, sql, tabla):
    with pytest.raises(IntegrityError) as info:
        await ejecutar(esquema_vacio, sql)

    assert error_postgres(info.value).sqlstate == "23502"
    assert await contar(esquema_vacio, tabla) == 0


INSERTAR_LINEA = (
    "INSERT INTO turno_practica (turno_id, practica_id, precio_unitario) VALUES (:t, :p, 100)"
)


async def test_misma_practica_dos_veces_en_un_turno_se_rechaza(padres):
    esquema_vacio = padres
    await ejecutar(esquema_vacio, INSERTAR_LINEA, t=1, p=1)

    with pytest.raises(IntegrityError) as info:
        await ejecutar(esquema_vacio, INSERTAR_LINEA, t=1, p=1)

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23505", "turno_practica_pkey")
    assert await contar(esquema_vacio, "turno_practica") == 1


@pytest.mark.parametrize("segundo", [(2, 1), (1, 2)])
async def test_misma_practica_en_dos_turnos_o_dos_practicas_en_un_turno_se_acepta(
    padres, segundo
):
    esquema_vacio = padres
    await ejecutar(esquema_vacio, INSERTAR_LINEA, t=1, p=1)

    await ejecutar(esquema_vacio, INSERTAR_LINEA, t=segundo[0], p=segundo[1])

    assert await contar(esquema_vacio, "turno_practica") == 2


ALTA_FICHA = "INSERT INTO ficha_duenio (duenio_id, telefono, direccion) VALUES (:d, 't', 'x')"
ALTA_PRACTICA = "INSERT INTO practica (nombre, precio) VALUES (:n, 1)"
ALTA_DUENIO = "INSERT INTO duenio (nombre, email) VALUES ('Ana', :e)"

REPETIDOS = [
    ("duenio", ALTA_DUENIO, {"e": "ana@example.com"}, "uq_duenio_email"),
    ("practica", ALTA_PRACTICA, {"n": "Consulta"}, "uq_practica_nombre"),
    ("ficha_duenio", ALTA_FICHA, {"d": 1}, "uq_ficha_duenio_duenio_id"),
]
DISTINTOS = {
    "duenio": {"e": "otro@example.com"},
    "practica": {"n": "Vacuna"},
    "ficha_duenio": {"d": 2},
}


@pytest.mark.parametrize(
    "tabla,sql,datos,restriccion", REPETIDOS, ids=[r[3] for r in REPETIDOS]
)
async def test_valor_repetido_se_rechaza_con_la_restriccion_unique(
    padres, tabla, sql, datos, restriccion
):
    await ejecutar(padres, sql, **datos)
    antes = await contar(padres, tabla)

    with pytest.raises(IntegrityError) as info:
        await ejecutar(padres, sql, **datos)

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23505", restriccion)
    assert await contar(padres, tabla) == antes


@pytest.mark.parametrize(
    "tabla,sql,datos,restriccion", REPETIDOS, ids=[r[3] for r in REPETIDOS]
)
async def test_valor_distinto_se_acepta(padres, tabla, sql, datos, restriccion):
    await ejecutar(padres, sql, **datos)
    antes = await contar(padres, tabla)

    await ejecutar(padres, sql, **DISTINTOS[tabla])

    assert await contar(padres, tabla) == antes + 1


ALTA_PRACTICA_PRECIO = "INSERT INTO practica (nombre, precio) VALUES ('p', :v)"
ALTA_TURNO_TOTAL = (
    "INSERT INTO turno (mascota_id, fecha, motivo, total) "
    "VALUES (1, '2026-11-10T09:00:00-03:00', 'm', :v)"
)

# (sql, valor rechazado, restricción, valor aceptado)
LIMITES = [
    (ALTA_PRACTICA_PRECIO, "0", "ck_practica_precio_positivo", "0.01"),
    (ALTA_PRACTICA_PRECIO, "-1", "ck_practica_precio_positivo", "0.01"),
    (
        INSERTAR_LINEA.replace("100", ":v"),
        "0",
        "ck_turno_practica_precio_unitario_positivo",
        "0.01",
    ),
    (ALTA_TURNO_TOTAL, "-0.01", "ck_turno_total_no_negativo", "0"),
]


def _parametros(sql, valor):
    return {"v": Decimal(valor), **({"t": 1, "p": 1} if ":t" in sql else {})}


@pytest.mark.parametrize("sql,malo,restriccion,bueno", LIMITES, ids=lambda v: str(v)[:40])
async def test_valor_fuera_de_rango_se_rechaza_con_su_check(
    padres, sql, malo, restriccion, bueno
):
    with pytest.raises(IntegrityError) as info:
        await ejecutar(padres, sql, **_parametros(sql, malo))

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23514", restriccion)


@pytest.mark.parametrize("sql,malo,restriccion,bueno", LIMITES, ids=lambda v: str(v)[:40])
async def test_valor_limite_valido_se_acepta(padres, sql, malo, restriccion, bueno):
    tabla = sql.split()[2]
    antes = await contar(padres, tabla)

    await ejecutar(padres, sql, **_parametros(sql, bueno))

    assert await contar(padres, tabla) == antes + 1


async def test_update_de_precio_a_cero_se_rechaza_y_no_modifica_nada(esquema_vacio):
    await ejecutar(esquema_vacio, "INSERT INTO practica (nombre, precio) VALUES ('Consulta', 15000)")

    with pytest.raises(IntegrityError) as info:
        await ejecutar(esquema_vacio, "UPDATE practica SET precio = 0 WHERE id = 1")

    assert error_postgres(info.value).constraint_name == "ck_practica_precio_positivo"
    async with esquema_vacio.connect() as conn:
        precio = (await conn.execute(text("SELECT precio FROM practica WHERE id = 1"))).scalar_one()
    assert precio == Decimal("15000.00")


FK_INEXISTENTES = [
    (
        "INSERT INTO mascota (nombre, especie, duenio_id) VALUES ('X', 'perro', 999)",
        "mascota_duenio_id_fkey",
    ),
    (
        "INSERT INTO ficha_duenio (duenio_id, telefono, direccion) VALUES (999, 't', 'd')",
        "ficha_duenio_duenio_id_fkey",
    ),
    (
        "INSERT INTO turno (mascota_id, fecha, motivo, total) "
        "VALUES (999, '2026-11-10T09:00:00-03:00', 'm', 0)",
        "turno_mascota_id_fkey",
    ),
    (
        "INSERT INTO turno_practica (turno_id, practica_id, precio_unitario) VALUES (1, 999, 1)",
        "turno_practica_practica_id_fkey",
    ),
    (
        "INSERT INTO turno_practica (turno_id, practica_id, precio_unitario) VALUES (999, 1, 1)",
        "turno_practica_turno_id_fkey",
    ),
]


@pytest.mark.parametrize("sql,restriccion", FK_INEXISTENTES, ids=[f[1] for f in FK_INEXISTENTES])
async def test_clave_foranea_a_fila_inexistente_se_rechaza(padres, sql, restriccion):
    tabla = sql.split()[2]
    antes = await contar(padres, tabla)

    with pytest.raises(IntegrityError) as info:
        await ejecutar(padres, sql)

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23503", restriccion)
    assert await contar(padres, tabla) == antes
