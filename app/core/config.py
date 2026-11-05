import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]

# Una sola vez al importar (override=False: el entorno del proceso prevalece sobre .env).
load_dotenv(RAIZ_PROYECTO / ".env")

CONTROLADOR_REQUERIDO = "postgresql+asyncpg"
VALORES_SQL_ECHO_ACTIVO = frozenset({"1", "true"})

MENSAJE_FALTA_URL = (
    "Falta la variable de entorno DATABASE_URL. Copiá env.example a .env y completala."
)
MENSAJE_URL_ILEGIBLE = (
    "DATABASE_URL no se puede interpretar como una dirección de base de datos. "
    "Revisá el formato en env.example."
)
MENSAJE_CONTROLADOR = (
    f"DATABASE_URL debe empezar con {CONTROLADOR_REQUERIDO}:// "
    "(PostgreSQL con el controlador asincrónico asyncpg). Revisá env.example."
)


class ConfiguracionInvalida(RuntimeError):
    """La configuración del entorno falta o es inválida (nunca incluye la clave)."""


@dataclass(frozen=True)
class Configuracion:
    database_url: str
    sql_echo: bool


def cargar_configuracion() -> Configuracion:
    """Lee y valida el entorno del proceso en el momento de la llamada."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ConfiguracionInvalida(MENSAJE_FALTA_URL)
    try:
        url = make_url(database_url)
    except ArgumentError:
        raise ConfiguracionInvalida(MENSAJE_URL_ILEGIBLE) from None
    if url.drivername != CONTROLADOR_REQUERIDO:
        raise ConfiguracionInvalida(MENSAJE_CONTROLADOR)

    sql_echo = os.environ.get("SQL_ECHO", "").strip().lower() in VALORES_SQL_ECHO_ACTIVO
    return Configuracion(database_url=database_url, sql_echo=sql_echo)
