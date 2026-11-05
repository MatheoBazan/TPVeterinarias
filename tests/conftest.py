import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from soporte import abrir_servidor_mudo, cliente_de, levantar_app, validar_url_de_test


@pytest.fixture
def url_base_test(monkeypatch: pytest.MonkeyPatch) -> str:
    """URL de `veterinaria_test` validada; la deja como DATABASE_URL del proceso."""
    url = validar_url_de_test(os.environ.get("TEST_DATABASE_URL"))
    monkeypatch.setenv("DATABASE_URL", url)
    return url


@pytest.fixture
async def app(url_base_test: str, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    async with levantar_app(url_base_test, monkeypatch) as aplicacion:
        yield aplicacion


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with cliente_de(app) as cliente:
        yield cliente


@pytest.fixture
async def servidor_mudo() -> AsyncIterator[int]:
    """Puerto de un servidor TCP que acepta conexiones y nunca contesta."""
    servidor, escritores = await abrir_servidor_mudo()
    try:
        yield servidor.sockets[0].getsockname()[1]
    finally:
        for escritor in list(escritores):
            escritor.close()
        servidor.close()
        await servidor.wait_closed()
