from pathlib import Path

import pytest
from soporte import bloques_http

pytestmark = pytest.mark.integracion

RUTA = Path(__file__).resolve().parent.parent / "test" / "laboratorio.http"


def test_laboratorio_http_documenta_el_caso_c09():
    assert RUTA.exists(), "falta test/laboratorio.http"
    texto = RUTA.read_text(encoding="utf-8")

    assert "Caso C-09" in texto
    bloques = texto.split("\n### ")[1:]
    assert bloques
    for bloque in bloques:
        assert "# Esperado:" in bloque, bloque.splitlines()[0]


async def test_laboratorio_http_corre_en_orden_con_los_codigos_esperados(client):
    bloques = bloques_http(RUTA)

    assert len(bloques) == 4
    for bloque in bloques:
        url = bloque.url.replace("{{base}}", "")
        r = await client.request(bloque.metodo, url, headers=bloque.cabeceras, content=bloque.cuerpo)
        assert r.status_code == bloque.codigo_esperado, f"{bloque.titulo}: {r.status_code} {r.text}"
