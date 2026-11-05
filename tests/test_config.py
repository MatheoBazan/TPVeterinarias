import pytest

from app.core import config
from app.core.config import ConfiguracionInvalida, cargar_configuracion

URL_VALIDA = "postgresql+asyncpg://u:p@localhost:5433/veterinaria_test"


def test_cargar_configuracion_con_database_url_devuelve_esa_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL_VALIDA)

    configuracion = cargar_configuracion()

    assert configuracion.database_url == URL_VALIDA


def test_cargar_configuracion_url_distinta_devuelve_la_otra_url(monkeypatch):
    otra = "postgresql+asyncpg://x:y@127.0.0.1:1/otra"
    monkeypatch.setenv("DATABASE_URL", otra)

    assert cargar_configuracion().database_url == otra


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_cargar_configuracion_sin_url_falla_nombrando_variable_y_env_example(
    monkeypatch, valor
):
    if valor is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", valor)

    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_configuracion()

    assert "DATABASE_URL" in str(error.value)
    assert "env.example" in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:clave_secreta@localhost/x",
        "sqlite+aiosqlite:///x.db",
        "postgresql+psycopg2://u:clave_secreta@localhost/x",
    ],
)
def test_cargar_configuracion_con_controlador_incorrecto_exige_asyncpg_sin_filtrar_clave(
    monkeypatch, url
):
    monkeypatch.setenv("DATABASE_URL", url)

    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_configuracion()

    assert "postgresql+asyncpg://" in str(error.value)
    assert "clave_secreta" not in str(error.value)


def test_cargar_configuracion_con_url_ilegible_falla_sin_filtrar_la_cadena(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "esto no es una url clave_secreta")

    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_configuracion()

    assert "DATABASE_URL" in str(error.value)
    assert "clave_secreta" not in str(error.value)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, False),
        ("0", False),
        ("false", False),
        ("", False),
        ("1", True),
        ("true", True),
        ("TRUE", True),
    ],
)
def test_cargar_configuracion_sql_echo_segun_valor(monkeypatch, valor, esperado):
    monkeypatch.setenv("DATABASE_URL", URL_VALIDA)
    if valor is None:
        monkeypatch.delenv("SQL_ECHO", raising=False)
    else:
        monkeypatch.setenv("SQL_ECHO", valor)

    assert cargar_configuracion().sql_echo is esperado


def test_configuracion_es_inmutable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", URL_VALIDA)
    configuracion = cargar_configuracion()

    with pytest.raises(AttributeError):
        configuracion.sql_echo = True  # type: ignore[misc]


def test_raiz_proyecto_contiene_env_example():
    assert (config.RAIZ_PROYECTO / "env.example").is_file()
