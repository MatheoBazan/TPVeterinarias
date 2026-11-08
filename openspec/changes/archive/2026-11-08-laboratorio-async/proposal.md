# Proposal — laboratorio-async (C-07)

## Why

El **Ej. 6 — Asincronía sin bloqueos (10 %)** pide consultar el stock de vacunas a la biblioteca del laboratorio que entrega la cátedra (`consultar_stock`, sincrónica, tarda un segundo) sin frenar al servidor: mientras hay consultas en curso, `GET /health/live` tiene que responder de inmediato (caso C-09 de la consigna). Es el único módulo que falta y no depende del esquema de datos.

## What Changes

- `app/modules/laboratorio/cliente.py` **exactamente como lo entrega la cátedra**, sin modificaciones.
- `GET /laboratorio/stock/{vacuna}` → **200** `{"vacuna": <vacuna>, "stock": <entero>}`, llamando a `consultar_stock` fuera del bucle de eventos (en un hilo aparte).
- Módulo con la misma estructura que los demás: `models.py` sólo con un docstring (no hay tablas), `schemas.py`, `service.py`, `router.py`; registro del router en `app/main.py`.
- `test/laboratorio.http` con el caso C-09 de la consigna y la forma de lanzar las tres consultas a la vez.
- Tests pytest que demuestran la concurrencia: con tres consultas al laboratorio en vuelo, `/health/live` responde en mucho menos de un segundo, y las tres terminan en ~1 s y no en ~3 s.

## Capabilities

### New Capabilities
- `laboratorio`: consulta del stock de vacunas a la biblioteca sincrónica del laboratorio sin bloquear al servidor.

### Modified Capabilities
- Ninguna.

## Reglas, casos y preguntas abiertas

- **Caso de la consigna**: C-09.
- **Reglas duras**: 2 (async sin bloqueos; no modificar `cliente.py`).
- **Preguntas abiertas**: ninguna de `10_preguntas_abiertas.md` toca este módulo.

## Impact

- **Código nuevo**: `app/modules/laboratorio/{__init__,cliente,models,schemas,service,router}.py`; una línea en `app/main.py`.
- **API**: una ruta nueva, `GET /laboratorio/stock/{vacuna}`.
- **Tests**: `tests/test_laboratorio*.py` y `test/laboratorio.http`.
- **Sin base de datos** y sin dependencias nuevas (`asyncio.to_thread` es de la biblioteca estándar).
