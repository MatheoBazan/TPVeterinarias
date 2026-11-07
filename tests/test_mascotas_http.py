from pathlib import Path

import pytest
from soporte import bloques_http

pytestmark = pytest.mark.integracion

RUTA = Path(__file__).resolve().parent.parent / "test" / "mascotas.http"


def test_mascotas_http_documenta_el_caso_c04():
    assert RUTA.exists(), "falta test/mascotas.http"
    texto = RUTA.read_text(encoding="utf-8")

    assert "Caso C-04" in texto
    assert "POST {{base}}/mascotas/" in texto
    bloques = texto.split("\n### ")[1:]
    assert bloques
    for bloque in bloques:
        assert "# Esperado:" in bloque, bloque.splitlines()[0]


async def test_mascotas_http_corre_en_orden_con_los_codigos_esperados(base_con_seed, client):
    bloques = bloques_http(RUTA)

    assert len(bloques) == 13
    for bloque in bloques:
        url = bloque.url.replace("{{base}}", "")
        r = await client.request(bloque.metodo, url, headers=bloque.cabeceras, content=bloque.cuerpo)
        assert r.status_code == bloque.codigo_esperado, f"{bloque.titulo}: {r.status_code} {r.text}"
