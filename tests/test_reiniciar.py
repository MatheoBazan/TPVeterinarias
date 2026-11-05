from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion


async def filas(motor, sql):
    async with motor.connect() as conn:
        return [tuple(f) for f in (await conn.execute(text(sql))).all()]


async def test_datos_iniciales_cargan_exactamente_las_filas_esperadas(sesion, esquema_vacio):
    from reiniciar import cargar_datos_iniciales

    await cargar_datos_iniciales(sesion)

    assert await filas(esquema_vacio, "SELECT id, nombre, email FROM duenio ORDER BY id") == [
        (1, "Ana Gómez", "ana.gomez@example.com"),
        (2, "Carlos Ruiz", "carlos.ruiz@example.com"),
    ]
    assert [f[1] for f in await filas(esquema_vacio, "SELECT id, duenio_id FROM ficha_duenio")] == [1]
    assert await filas(
        esquema_vacio, "SELECT id, nombre, especie, duenio_id FROM mascota ORDER BY id"
    ) == [(1, "Toby", "perro", 1), (2, "Mishi", "gato", 1), (3, "Luna", "perro", 2)]
    assert await filas(esquema_vacio, "SELECT id, nombre, precio FROM practica ORDER BY id") == [
        (1, "Consulta", Decimal("15000.00")),
        (2, "Desparasitación", Decimal("8000.00")),
        (3, "Vacuna antirrábica", Decimal("12000.00")),
        (4, "Vacuna quíntuple", Decimal("14000.00")),
    ]


async def test_turno_inicial_con_precios_copiados_y_total_calculado(base_con_seed):
    turno = await filas(base_con_seed, "SELECT id, mascota_id, fecha, motivo, total FROM turno")
    lineas = await filas(
        base_con_seed,
        "SELECT turno_id, practica_id, precio_unitario FROM turno_practica ORDER BY practica_id",
    )

    assert [(t[0], t[1], t[3], t[4]) for t in turno] == [
        (1, 2, "Control y desparasitación", Decimal("23000.00"))
    ]
    assert turno[0][2] == datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    assert lineas == [(1, 1, Decimal("15000.00")), (1, 2, Decimal("8000.00"))]
    assert turno[0][4] == sum((l[2] for l in lineas), start=Decimal("0"))


async def test_carga_que_falla_a_mitad_de_camino_no_deja_nada(sesion, esquema_vacio):
    from sqlalchemy.exc import IntegrityError

    from reiniciar import cargar_datos_iniciales
    from soporte import error_postgres

    async with esquema_vacio.begin() as conn:
        await conn.execute(
            text("INSERT INTO duenio (nombre, email) VALUES ('Previa', 'ana.gomez@example.com')")
        )

    with pytest.raises(IntegrityError) as info:
        await cargar_datos_iniciales(sesion)
    await sesion.rollback()

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23505", "uq_duenio_email")
    for tabla in ("practica", "mascota", "ficha_duenio", "turno", "turno_practica"):
        assert await filas(esquema_vacio, f"SELECT 1 FROM {tabla}") == []
    assert await filas(esquema_vacio, "SELECT id, nombre FROM duenio") == [(1, "Previa")]


async def test_cargar_dos_veces_sin_recrear_se_rechaza_sin_cambios(base_con_seed, motor_test):
    from sqlalchemy.exc import IntegrityError

    from app.core.database import crear_fabrica_sesiones
    from reiniciar import cargar_datos_iniciales
    from soporte import error_postgres

    tablas = ("duenio", "ficha_duenio", "mascota", "practica", "turno", "turno_practica")
    antes = [await filas(base_con_seed, f"SELECT count(*) FROM {t}") for t in tablas]

    async with crear_fabrica_sesiones(motor_test)() as otra:
        with pytest.raises(IntegrityError) as info:
            await cargar_datos_iniciales(otra)

    assert error_postgres(info.value).sqlstate == "23505"
    assert [await filas(base_con_seed, f"SELECT count(*) FROM {t}") for t in tablas] == antes
    assert [a[0][0] for a in antes] == [2, 1, 3, 4, 1, 2]


async def test_ejemplo_del_ejercicio_4_produce_el_turno_2_con_total_27000(base_con_seed, motor_test):
    from sqlmodel import select

    from app.core.database import crear_fabrica_sesiones
    from app.core.modelos import Practica, Turno, TurnoPractica

    async with crear_fabrica_sesiones(motor_test)() as s:
        catalogo = (await s.exec(select(Practica).where(Practica.id.in_([1, 3])))).all()
        lineas = [TurnoPractica(practica=p, precio_unitario=p.precio) for p in catalogo]
        turno = Turno(
            mascota_id=1,
            fecha=datetime(2026, 11, 12, 10, 30, tzinfo=timezone.utc),
            motivo="Vacunación",
            total=sum((tp.precio_unitario for tp in lineas), start=Decimal("0")),
            practicas=lineas,
        )
        s.add(turno)
        await s.commit()
        nuevo_id, total = turno.id, turno.total

    assert (nuevo_id, total) == (2, Decimal("27000.00"))
    assert await filas(
        base_con_seed,
        "SELECT practica_id, precio_unitario FROM turno_practica WHERE turno_id = 2 ORDER BY 1",
    ) == [(1, Decimal("15000.00")), (3, Decimal("12000.00"))]


@pytest.mark.parametrize(
    "tabla,sql,esperado",
    [
        ("duenio", "INSERT INTO duenio (nombre, email) VALUES ('N', 'n@x') RETURNING id", 3),
        (
            "mascota",
            "INSERT INTO mascota (nombre, especie, duenio_id) VALUES ('N', 'gato', 1) RETURNING id",
            4,
        ),
        ("practica", "INSERT INTO practica (nombre, precio) VALUES ('N', 1) RETURNING id", 5),
    ],
)
async def test_las_secuencias_continuan_despues_de_los_datos_iniciales(
    base_con_seed, tabla, sql, esperado
):
    async with base_con_seed.begin() as conn:
        nuevo = (await conn.execute(text(sql))).scalar_one()

    assert nuevo == esperado


import asyncio  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

from sqlalchemy.engine import make_url  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.core.config import RAIZ_PROYECTO  # noqa: E402


async def correr(args, **entorno):
    """Ejecuta `python <args>` en la raíz del proyecto con el entorno dado (sin el .env pisando)."""
    env = {**os.environ, "PYTHONUTF8": "1", **entorno}
    return await asyncio.to_thread(
        subprocess.run,
        [sys.executable, *args],
        cwd=RAIZ_PROYECTO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


async def borrar_todo(motor):
    async with motor.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


async def test_reiniciar_py_sobre_base_sin_tablas(motor_test, url_base_test):
    await borrar_todo(motor_test)

    resultado = await correr(["reiniciar.py"], DATABASE_URL=url_base_test, SQL_ECHO="0")

    assert resultado.returncode == 0, resultado.stderr
    assert await filas(motor_test, "SELECT id, nombre FROM practica ORDER BY id") == [
        (1, "Consulta"),
        (2, "Desparasitación"),
        (3, "Vacuna antirrábica"),
        (4, "Vacuna quíntuple"),
    ]
    assert "Datos iniciales" in resultado.stdout


async def test_reiniciar_py_dos_veces_seguidas_deja_el_mismo_estado_y_los_mismos_ids(
    motor_test, url_base_test
):
    await borrar_todo(motor_test)
    primera = await correr(["reiniciar.py"], DATABASE_URL=url_base_test, SQL_ECHO="0")
    estado = await filas(motor_test, "SELECT id, nombre, email FROM duenio ORDER BY id")
    async with motor_test.begin() as conn:
        await conn.execute(text("INSERT INTO duenio (nombre, email) VALUES ('Extra', 'e@x')"))
        await conn.execute(
            text(
                "INSERT INTO turno (mascota_id, fecha, motivo, total) "
                "VALUES (1, '2026-11-12T10:00:00-03:00', 'm', 0)"
            )
        )

    segunda = await correr(["reiniciar.py"], DATABASE_URL=url_base_test, SQL_ECHO="0")

    assert (primera.returncode, segunda.returncode) == (0, 0), segunda.stderr
    assert primera.stdout == segunda.stdout
    assert await filas(motor_test, "SELECT id, nombre, email FROM duenio ORDER BY id") == estado
    assert await filas(motor_test, "SELECT id FROM turno") == [(1,)]


@pytest.mark.parametrize("valor", ["", "postgresql://u:clave-secreta@localhost/x"])
async def test_reiniciar_py_con_database_url_invalida_falla_sin_mostrar_la_clave(
    motor_test, url_base_test, valor
):
    await borrar_todo(motor_test)

    resultado = await correr(["reiniciar.py"], DATABASE_URL=valor, SQL_ECHO="0")

    assert resultado.returncode != 0
    assert "DATABASE_URL" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert "clave-secreta" not in resultado.stderr + resultado.stdout
    clave_real = make_url(url_base_test).password
    assert clave_real not in resultado.stderr + resultado.stdout
    async with motor_test.connect() as conn:  # no se modificó ninguna base
        tablas = (
            await conn.execute(
                text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
            )
        ).scalar_one()
    assert tablas == 0


SEIS_TABLAS = ["duenio", "ficha_duenio", "mascota", "practica", "turno", "turno_practica"]


async def test_importar_app_main_registra_las_seis_tablas_y_resuelve_las_relaciones(url_base_test):
    codigo = (
        "import app.main\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "from sqlmodel import SQLModel\n"
        "configure_mappers()\n"
        "print(sorted(SQLModel.metadata.tables))\n"
    )

    resultado = await correr(["-c", codigo], DATABASE_URL=url_base_test)

    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == str(SEIS_TABLAS)


async def test_importar_un_solo_modulo_de_modelos_no_alcanza_para_configurar_las_relaciones(
    url_base_test,
):
    codigo = (
        "import app.modules.duenios.models\n"
        "from sqlalchemy.exc import InvalidRequestError\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "try:\n"
        "    configure_mappers()\n"
        "except InvalidRequestError as exc:\n"
        "    print('FALLA', exc)\n"
        "    raise SystemExit(3)\n"
    )

    resultado = await correr(["-c", codigo], DATABASE_URL=url_base_test)

    assert resultado.returncode == 3, resultado.stderr
    assert "Mascota" in resultado.stdout


RUTA_C08 = RAIZ_PROYECTO / "test" / "c08_check_precio.sql"


def sentencias_del_sql(ruta):
    """Sentencias del archivo sin las líneas de comentario `--`, separadas por `;`."""
    lineas = [l for l in ruta.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("--")]
    return [s.strip() for s in "\n".join(lineas).split(";") if s.strip()]


async def test_sql_del_caso_c08_es_rechazado_por_el_check(base_con_seed):
    from sqlalchemy.exc import IntegrityError

    from soporte import error_postgres

    actualizar, consultar = sentencias_del_sql(RUTA_C08)

    async with base_con_seed.connect() as conn:
        with pytest.raises(IntegrityError) as info:
            await conn.execute(text(actualizar))
        await conn.rollback()
        precio = (await conn.execute(text(consultar))).one()

    error = error_postgres(info.value)
    assert (error.sqlstate, error.constraint_name) == ("23514", "ck_practica_precio_positivo")
    assert tuple(precio) == (1, "Consulta", Decimal("15000.00"))
    assert actualizar.upper().startswith("UPDATE PRACTICA SET PRECIO = 0")


@pytest.mark.parametrize(
    "fragmento",
    [
        "python reiniciar.py",
        "docker compose cp",
        "docker compose exec db psql",
        "ck_practica_precio_positivo",
    ],
)
def test_sql_del_caso_c08_documenta_precondicion_ejecucion_y_error(fragmento):
    comentarios = "\n".join(
        l for l in RUTA_C08.read_text(encoding="utf-8").splitlines() if l.startswith("--")
    )

    assert fragmento in comentarios


def test_sql_del_caso_c08_no_contiene_la_clave_real():
    clave = os.environ.get("POSTGRES_PASSWORD")
    if not clave:
        pytest.skip("POSTGRES_PASSWORD no está definida en el entorno")

    assert clave not in RUTA_C08.read_text(encoding="utf-8")
