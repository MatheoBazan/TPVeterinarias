import pytest
from sqlalchemy import inspect, text

from app.core.modelos import Duenio, FichaDuenio, Mascota, Practica, Turno, TurnoPractica

pytestmark = pytest.mark.integracion

TABLAS = {"duenio", "ficha_duenio", "mascota", "practica", "turno", "turno_practica"}


async def consultar(motor, sql, **parametros):
    async with motor.connect() as conn:
        return (await conn.execute(text(sql), parametros)).all()


async def test_crear_esquema_deja_exactamente_las_seis_tablas(esquema_vacio):
    filas = await consultar(
        esquema_vacio,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'",
    )

    nombres = {f[0] for f in filas}
    assert nombres == TABLAS
    assert "fichaduenio" not in nombres and "turnopractica" not in nombres


async def test_recrear_esquema_sobre_tablas_con_datos_las_deja_vacias_con_ids_desde_1(
    esquema_vacio,
):
    from reiniciar import recrear_esquema

    async with esquema_vacio.begin() as conn:
        await conn.execute(text("INSERT INTO practica (nombre, precio) VALUES ('x', 1)"))

    await recrear_esquema(esquema_vacio)

    assert await consultar(esquema_vacio, "SELECT id FROM practica") == []
    async with esquema_vacio.begin() as conn:
        nuevo = (
            await conn.execute(
                text("INSERT INTO practica (nombre, precio) VALUES ('y', 2) RETURNING id")
            )
        ).scalar_one()
    assert nuevo == 1


async def test_recrear_esquema_dos_veces_seguidas_no_falla(esquema_vacio):
    from reiniciar import recrear_esquema

    await recrear_esquema(esquema_vacio)
    await recrear_esquema(esquema_vacio)

    filas = await consultar(
        esquema_vacio,
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'",
    )
    assert filas[0][0] == 6


COLUMNAS = {
    "duenio": {"id", "nombre", "email"},
    "ficha_duenio": {"id", "duenio_id", "telefono", "direccion"},
    "mascota": {"id", "nombre", "especie", "duenio_id"},
    "practica": {"id", "nombre", "precio"},
    "turno": {"id", "mascota_id", "fecha", "motivo", "total"},
    "turno_practica": {"turno_id", "practica_id", "precio_unitario"},
}


@pytest.mark.parametrize("tabla", sorted(COLUMNAS))
async def test_columnas_de_cada_tabla_son_las_de_la_consigna(esquema_vacio, tabla):
    filas = await consultar(
        esquema_vacio,
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t",
        t=tabla,
    )

    assert {f[0] for f in filas} == COLUMNAS[tabla]
    assert {f[1] for f in filas} == {"NO"}


TIPOS = [
    ("practica", "precio", "numeric", 10, 2),
    ("turno_practica", "precio_unitario", "numeric", 10, 2),
    ("turno", "total", "numeric", 12, 2),
    ("turno", "fecha", "timestamp with time zone", None, None),
    ("duenio", "nombre", "character varying", None, None),
    ("duenio", "email", "character varying", None, None),
    ("mascota", "especie", "character varying", None, None),
    ("ficha_duenio", "telefono", "character varying", None, None),
    ("ficha_duenio", "direccion", "character varying", None, None),
    ("turno", "motivo", "character varying", None, None),
]


@pytest.mark.parametrize("tabla,columna,tipo,precision,escala", TIPOS)
async def test_tipos_de_columna(esquema_vacio, tabla, columna, tipo, precision, escala):
    filas = await consultar(
        esquema_vacio,
        "SELECT data_type, numeric_precision, numeric_scale FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c",
        t=tabla,
        c=columna,
    )

    assert filas[0][0] == tipo
    if precision is not None:
        assert (filas[0][1], filas[0][2]) == (precision, escala)


@pytest.mark.parametrize(
    "tabla", ["duenio", "ficha_duenio", "mascota", "practica", "turno"]
)
async def test_id_es_entero_autoincremental(esquema_vacio, tabla):
    filas = await consultar(
        esquema_vacio,
        "SELECT data_type, column_default FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = 'id'",
        t=tabla,
    )

    assert filas[0][0] == "integer"
    assert filas[0][1].startswith("nextval(")


async def test_clave_primaria_de_turno_practica_es_compuesta_y_empieza_por_turno_id(
    esquema_vacio,
):
    filas = await consultar(
        esquema_vacio,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'public.turno_practica'::regclass AND contype = 'p'",
    )

    assert [f[0] for f in filas] == ["PRIMARY KEY (turno_id, practica_id)"]


@pytest.mark.parametrize("tabla", sorted(COLUMNAS))
async def test_claves_primarias_se_llaman_tabla_pkey(esquema_vacio, tabla):
    filas = await consultar(
        esquema_vacio,
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = ('public.' || :t)::regclass AND contype = 'p'",
        t=tabla,
    )

    assert [f[0] for f in filas] == [f"{tabla}_pkey"]


# (tabla, nombre de la FK, columna, tabla referida, confdeltype)
CLAVES_FORANEAS = [
    ("mascota", "mascota_duenio_id_fkey", "duenio_id", "duenio", "r"),
    ("turno_practica", "turno_practica_turno_id_fkey", "turno_id", "turno", "c"),
    ("ficha_duenio", "ficha_duenio_duenio_id_fkey", "duenio_id", "duenio", "c"),
    ("turno", "turno_mascota_id_fkey", "mascota_id", "mascota", "r"),
    ("turno_practica", "turno_practica_practica_id_fkey", "practica_id", "practica", "r"),
]


@pytest.mark.parametrize(
    "tabla,nombre,columna,referida,regla", CLAVES_FORANEAS, ids=[c[1] for c in CLAVES_FORANEAS]
)
async def test_reglas_de_borrado_de_las_claves_foraneas(
    esquema_vacio, tabla, nombre, columna, referida, regla
):
    filas = await consultar(
        esquema_vacio,
        "SELECT conname, confdeltype::text, confrelid::regclass::text, "
        "pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = ('public.' || :t)::regclass AND contype = 'f' AND conname = :n",
        t=tabla,
        n=nombre,
    )

    assert len(filas) == 1
    assert filas[0][1] == regla  # nunca 'a' (NO ACTION)
    assert filas[0][2] == referida
    assert f"FOREIGN KEY ({columna})" in filas[0][3]


async def test_hay_exactamente_cinco_claves_foraneas(esquema_vacio):
    filas = await consultar(
        esquema_vacio,
        "SELECT conname FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace",
    )

    assert {f[0] for f in filas} == {c[1] for c in CLAVES_FORANEAS}


INDICES = {
    "duenio": {"duenio_pkey", "uq_duenio_email"},
    "ficha_duenio": {"ficha_duenio_pkey", "uq_ficha_duenio_duenio_id"},
    "mascota": {"mascota_pkey", "ix_mascota_duenio_id"},
    "practica": {"practica_pkey", "uq_practica_nombre"},
    "turno": {"turno_pkey", "ix_turno_mascota_id"},
    "turno_practica": {"turno_practica_pkey", "ix_turno_practica_practica_id"},
}


@pytest.mark.parametrize("tabla", sorted(INDICES))
async def test_indices_de_cada_tabla_son_exactamente_los_esperados(esquema_vacio, tabla):
    filas = await consultar(
        esquema_vacio,
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = :t",
        t=tabla,
    )

    assert {f[0] for f in filas} == INDICES[tabla]


async def test_turno_practica_turno_id_no_tiene_indice_propio(esquema_vacio):
    filas = await consultar(
        esquema_vacio,
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
        "AND tablename = 'turno_practica' AND indexdef LIKE '%(turno_id%'",
    )

    assert [f[0] for f in filas] == ["turno_practica_pkey"]


# (lado "uno", atributo, lado "muchos", atributo inverso, la colección es lista)
RELACIONES = [
    (Duenio, "ficha", FichaDuenio, "duenio", False),
    (Duenio, "mascotas", Mascota, "duenio", True),
    (Mascota, "turnos", Turno, "mascota", True),
    (Turno, "practicas", TurnoPractica, "turno", True),
    (Practica, "turnos", TurnoPractica, "practica", True),
]
IDS_RELACIONES = [f"{r[0].__name__}.{r[1]}" for r in RELACIONES]


@pytest.mark.parametrize("uno,en_uno,muchos,en_muchos,es_lista", RELACIONES, ids=IDS_RELACIONES)
def test_cada_relacion_tiene_su_extremo_opuesto(uno, en_uno, muchos, en_muchos, es_lista):
    lado_uno = inspect(uno).relationships[en_uno]
    lado_muchos = inspect(muchos).relationships[en_muchos]

    assert lado_uno.mapper.class_ is muchos
    assert lado_uno.back_populates == en_muchos
    assert lado_muchos.mapper.class_ is uno
    assert lado_muchos.back_populates == en_uno
    assert lado_muchos.uselist is False


def test_duenio_ficha_no_es_una_lista():
    assert inspect(Duenio).relationships["ficha"].uselist is False


@pytest.mark.parametrize("uno,en_uno,muchos,en_muchos,es_lista", RELACIONES, ids=IDS_RELACIONES)
def test_las_colecciones_son_listas(uno, en_uno, muchos, en_muchos, es_lista):
    assert inspect(uno).relationships[en_uno].uselist is es_lista


@pytest.mark.parametrize("uno,en_uno,muchos,en_muchos,es_lista", RELACIONES, ids=IDS_RELACIONES)
def test_lados_uno_tienen_passive_deletes_all_sin_cascada_delete(
    uno, en_uno, muchos, en_muchos, es_lista
):
    lado_uno = inspect(uno).relationships[en_uno]
    lado_muchos = inspect(muchos).relationships[en_muchos]

    assert lado_uno.passive_deletes == "all"
    assert not lado_uno.cascade.delete and not lado_uno.cascade.delete_orphan
    assert lado_uno.cascade.save_update
    assert lado_muchos.passive_deletes is False
