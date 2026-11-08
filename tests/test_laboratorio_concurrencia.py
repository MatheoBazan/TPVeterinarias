import asyncio
import time

import pytest

pytestmark = pytest.mark.integracion

VACUNAS = ("rabia", "moquillo", "parvovirus")


async def lanzar_consultas(client) -> list[asyncio.Task]:
    tareas = [asyncio.create_task(client.get(f"/laboratorio/stock/{v}")) for v in VACUNAS]
    await asyncio.sleep(0.1)  # que las tres entren al handler antes de medir
    return tareas


async def test_caso_c09_health_responde_con_tres_consultas_en_curso(client):
    tareas = await lanzar_consultas(client)

    inicio = time.perf_counter()
    r = await client.get("/health/live")
    duracion = time.perf_counter() - inicio

    assert r.status_code == 200
    assert r.json() == {"estado": "vivo"}
    assert duracion < 0.5
    assert not any(t.done() for t in tareas)
    await asyncio.gather(*tareas)


async def test_tres_consultas_simultaneas_no_se_encolan(client):
    inicio = time.perf_counter()
    respuestas = await asyncio.gather(*await lanzar_consultas(client))
    duracion = time.perf_counter() - inicio

    assert [r.status_code for r in respuestas] == [200, 200, 200]
    assert [r.json()["stock"] for r in respuestas] == [10 + len(v) for v in VACUNAS]
    assert duracion < 2
