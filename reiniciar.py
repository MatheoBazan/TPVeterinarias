"""Recrea el esquema de la base de DATABASE_URL y carga los datos iniciales."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import modelos  # noqa: F401  (registra las seis tablas en la metadata)
from app.core.config import ConfiguracionInvalida, cargar_configuracion
from app.core.database import crear_fabrica_sesiones, crear_motor
from app.core.modelos import Duenio, FichaDuenio, Mascota, Practica, Turno, TurnoPractica


async def recrear_esquema(engine: AsyncEngine) -> None:
    """Borra las tablas del modelo si existen y las crea de nuevo, en una transacción."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


async def cargar_datos_iniciales(session: AsyncSession) -> None:
    """Carga el mínimo de la consigna en una sola transacción.

    El `flush` escalonado (catálogo, dueños y mascotas, turno) fija los ids por el orden
    de las listas y no por el orden en que la cascada `save-update` agrega los objetos.
    Los ids no se asignan a mano: las secuencias tienen que avanzar.
    """
    consulta, desparasitacion, antirrabica, quintuple = (
        Practica(nombre="Consulta", precio=Decimal("15000.00")),
        Practica(nombre="Desparasitación", precio=Decimal("8000.00")),
        Practica(nombre="Vacuna antirrábica", precio=Decimal("12000.00")),
        Practica(nombre="Vacuna quíntuple", precio=Decimal("14000.00")),
    )
    session.add_all([consulta, desparasitacion, antirrabica, quintuple])
    await session.flush()

    ana = Duenio(nombre="Ana Gómez", email="ana.gomez@example.com")
    ana.ficha = FichaDuenio(telefono="11 5555-0101", direccion="Calle Falsa 123")
    carlos = Duenio(nombre="Carlos Ruiz", email="carlos.ruiz@example.com")
    toby = Mascota(nombre="Toby", especie="perro", duenio=ana)
    mishi = Mascota(nombre="Mishi", especie="gato", duenio=ana)
    luna = Mascota(nombre="Luna", especie="perro", duenio=carlos)
    session.add_all([ana, carlos, toby, mishi, luna])
    await session.flush()

    lineas = [
        TurnoPractica(practica=p, precio_unitario=p.precio)
        for p in (consulta, desparasitacion)
    ]
    turno = Turno(
        mascota=mishi,
        fecha=datetime(2026, 11, 10, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
        motivo="Control y desparasitación",
        total=sum((tp.precio_unitario for tp in lineas), start=Decimal("0")),
        practicas=lineas,
    )
    session.add(turno)
    await session.commit()


async def main() -> None:
    """Recrea el esquema de la base de `DATABASE_URL` y carga los datos iniciales."""
    engine = crear_motor(cargar_configuracion())
    try:
        await recrear_esquema(engine)
        async with crear_fabrica_sesiones(engine)() as session:
            await cargar_datos_iniciales(session)
    finally:
        await engine.dispose()
    print(
        "Esquema recreado. Datos iniciales: 2 dueños (1 con ficha), 3 mascotas, "
        "4 prácticas, 1 turno con 2 prácticas."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ConfiguracionInvalida as exc:
        raise SystemExit(str(exc)) from None
