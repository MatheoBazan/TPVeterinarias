"""Parámetros de ruta compartidos por los módulos con `{id}`."""
from typing import Annotated, Final

from fastapi import Path

ENTERO_MAXIMO: Final = 2_147_483_647  # mayor valor de INTEGER (SERIAL) en PostgreSQL

# Sólo cota superior: evita el desborde int32 de asyncpg (500). 0 y negativos llegan a la base (404).
IdRuta = Annotated[int, Path(le=ENTERO_MAXIMO, description="Id entero (máximo 2147483647)")]
