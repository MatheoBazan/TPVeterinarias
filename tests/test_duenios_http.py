from pathlib import Path

import pytest
from soporte import bloques_http

pytestmark = pytest.mark.integracion

RUTA = Path(__file__).resolve().parent.parent / "test" / "duenios.http"


def test_duenios_http_documenta_los_casos_de_la_consigna():
    assert RUTA.exists(), "falta test/duenios.http"
    texto = RUTA.read_text(encoding="utf-8")

    assert "GET {{base}}/duenios/abc" in texto
    for caso in ("Caso C-01", "Caso C-02", "Caso C-03", "Caso C-05"):
        assert caso in texto
    bloques = texto.split("\n### ")[1:]
    assert bloques
    for bloque in bloques:
        assert "# Esperado:" in bloque, bloque.splitlines()[0]


async def test_duenios_http_corre_en_orden_con_los_codigos_esperados(base_con_seed, client):
    bloques = bloques_http(RUTA)

    assert len(bloques) == 21
    for bloque in bloques:
        url = bloque.url.replace("{{base}}", "")
        r = await client.request(bloque.metodo, url, headers=bloque.cabeceras, content=bloque.cuerpo)
        assert r.status_code == bloque.codigo_esperado, f"{bloque.titulo}: {r.status_code} {r.text}"


def test_bloques_http_separa_metodo_url_cabeceras_cuerpo_y_codigo(tmp_path):
    archivo = tmp_path / "x.http"
    archivo.write_text(
        "@base = http://h\n\n"
        "### Primero\n# Esperado: 201 {\"a\": 1}\nPOST {{base}}/x/\nContent-Type: application/json\n\n{\"a\": 1}\n\n"
        "### Segundo\n# Esperado: 204 sin cuerpo\nDELETE {{base}}/x/1\n",
        encoding="utf-8",
    )

    primero, segundo = bloques_http(archivo)

    assert (primero.titulo, primero.metodo, primero.url) == ("Primero", "POST", "{{base}}/x/")
    assert primero.cabeceras == {"Content-Type": "application/json"}
    assert primero.cuerpo == b'{"a": 1}'
    assert primero.codigo_esperado == 201
    assert (segundo.metodo, segundo.url, segundo.cabeceras, segundo.cuerpo, segundo.codigo_esperado) == (
        "DELETE",
        "{{base}}/x/1",
        {},
        None,
        204,
    )
