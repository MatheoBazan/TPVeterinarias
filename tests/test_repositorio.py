import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import RAIZ_PROYECTO

VARIABLES = [
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "SQL_ECHO",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_PORT",
]
FORMA_URL = re.compile(
    r"^postgresql\+asyncpg://<usuario>:<clave>@localhost:\d+/[a-z_]+$"
)


def leer_variables(ruta: Path) -> dict[str, str]:
    variables: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            nombre, valor = linea.split("=", 1)
            variables[nombre] = valor
    return variables


def test_env_example_declara_todas_las_variables():
    declaradas = leer_variables(RAIZ_PROYECTO / "env.example")

    assert set(VARIABLES) <= set(declaradas)


def test_leer_variables_detecta_una_variable_faltante(tmp_path):
    archivo = tmp_path / "env.example"
    archivo.write_text("DATABASE_URL=x\n# SQL_ECHO=0\n", encoding="utf-8")

    assert not set(VARIABLES) <= set(leer_variables(archivo))


@pytest.mark.parametrize("variable", ["DATABASE_URL", "TEST_DATABASE_URL"])
def test_env_example_urls_tienen_la_forma_con_placeholders(variable):
    valor = leer_variables(RAIZ_PROYECTO / "env.example")[variable]

    assert FORMA_URL.match(valor)


def test_forma_de_url_rechaza_credenciales_literales():
    assert not FORMA_URL.match("postgresql+asyncpg://admin:secreta@localhost:5433/x")


@pytest.mark.parametrize("archivo", ["env.example", "docker-compose.yml"])
def test_clave_real_no_aparece_en_archivos_versionados(archivo):
    clave = os.environ.get("POSTGRES_PASSWORD")
    if not clave:
        pytest.skip("POSTGRES_PASSWORD no está definida en el entorno")

    assert clave not in (RAIZ_PROYECTO / archivo).read_text(encoding="utf-8")


def test_docker_compose_no_da_valores_por_defecto_a_usuario_ni_clave():
    texto = (RAIZ_PROYECTO / "docker-compose.yml").read_text(encoding="utf-8")

    assert "${POSTGRES_USER:?" in texto
    assert "${POSTGRES_PASSWORD:?" in texto
    assert "${POSTGRES_PASSWORD:-" not in texto
    assert "${POSTGRES_USER:-" not in texto


def test_env_no_se_versiona():
    if shutil.which("git") is None:
        pytest.skip("git no está instalado")

    resultado = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], cwd=RAIZ_PROYECTO, check=False
    )

    assert resultado.returncode == 0
