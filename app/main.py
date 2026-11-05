from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core import modelos  # noqa: F401  (registra las seis tablas antes de la primera consulta)
from app.core.config import cargar_configuracion
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.modules.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = cargar_configuracion()
    engine = crear_motor(config)
    app.state.engine = engine
    app.state.session_factory = crear_fabrica_sesiones(engine)
    try:
        yield
    finally:
        await engine.dispose()


def crear_app() -> FastAPI:
    aplicacion = FastAPI(title="Veterinaria", lifespan=lifespan)
    aplicacion.include_router(health_router)
    return aplicacion


app = crear_app()
