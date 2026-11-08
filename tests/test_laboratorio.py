from pathlib import Path

import pytest

RUTA_CLIENTE = Path(__file__).resolve().parent.parent / "app" / "modules" / "laboratorio" / "cliente.py"

# Código del enunciado (Ej. 6): la cátedra lo entrega y no se modifica.
CODIGO_DE_LA_CATEDRA = '''import time


def consultar_stock(vacuna: str) -> int:
    """Biblioteca del laboratorio: sincrónica, tarda un segundo."""
    time.sleep(1)
    return 10 + len(vacuna)
'''


def test_cliente_es_el_de_la_catedra():
    assert RUTA_CLIENTE.read_text(encoding="utf-8") == CODIGO_DE_LA_CATEDRA


@pytest.mark.integracion
@pytest.mark.parametrize("vacuna, stock", [("rabia", 15), ("parvovirus", 20)])
async def test_stock_de_una_vacuna(client, vacuna, stock):
    r = await client.get(f"/laboratorio/stock/{vacuna}")

    assert r.status_code == 200
    assert r.json() == {"vacuna": vacuna, "stock": stock}
