from pathlib import Path

import pytest
from soporte import bloques_http

pytestmark = pytest.mark.integracion

RUTA = Path(__file__).resolve().parent.parent / "test" / "turnos.http"


def test_turnos_http_documenta_los_casos_de_la_consigna():
    assert RUTA.exists(), "falta test/turnos.http"
    texto = RUTA.read_text(encoding="utf-8")

    for caso in ("Caso C-04", "Caso C-05", "Caso C-06", "Caso C-07", "SQL_ECHO"):
        assert caso in texto
    bloques = texto.split("\n### ")[1:]
    assert bloques
    for bloque in bloques:
        assert "# Esperado:" in bloque, bloque.splitlines()[0]


async def test_turnos_http_corre_en_orden_con_los_codigos_esperados(base_con_seed, client):
    bloques = bloques_http(RUTA)

    assert len(bloques) == 12
    for bloque in bloques:
        url = bloque.url.replace("{{base}}", "")
        r = await client.request(bloque.metodo, url, headers=bloque.cabeceras, content=bloque.cuerpo)
        assert r.status_code == bloque.codigo_esperado, f"{bloque.titulo}: {r.status_code} {r.text}"
