# Design — laboratorio-async (C-07)

## Context

- `consultar_stock` es sincrónica y hace `time.sleep(1)`. Llamarla directamente desde un handler `async def` congela el bucle de eventos un segundo por llamada: ninguna otra petición (ni `/health/live`) avanza mientras tanto.
- La regla dura 2 prohíbe modificar `cliente.py` y exige sacar lo bloqueante del bucle.
- Estructura de módulos (decisión D-8 de C-01): `models.py`, `schemas.py`, `service.py`, `router.py`, también en módulos sin tablas, como `health`.

## Goals / Non-Goals

**Goals:** demostrar con tests automáticos (y con el `.http`) que el servidor no se bloquea y que las consultas corren en paralelo.

**Non-Goals:** caché del stock, timeouts o reintentos contra el laboratorio, validar el nombre de la vacuna (la consigna no define un catálogo de vacunas; cualquier texto de la ruta es válido).

## Decisions

### D-1 — `asyncio.to_thread` en el service

`service.consultar_stock(vacuna)` es `async def` y hace `await asyncio.to_thread(cliente.consultar_stock, vacuna)`. El router sólo lo espera y arma la respuesta.

- **Por qué `asyncio.to_thread` y no `run_in_threadpool`**: los dos sacan la llamada a un hilo. `to_thread` es de la biblioteca estándar (no ata el service a Starlette) y es el que nombra la KB (DD-17). Su pool por defecto (`min(32, núcleos + 4)` hilos) alcanza de sobra para el caso C-09 (3 consultas).
- **Alternativa descartada**: declarar el handler con `def` para que FastAPI lo corra en su threadpool. La regla dura 2 exige `async def` en todos los handlers.
- **Alternativa descartada**: reescribir la función con `asyncio.sleep`. Prohibido: `cliente.py` no se modifica.
- La función se llama a través del módulo (`cliente.consultar_stock`), no se importa suelta, para que un test pueda reemplazarla si algún día hace falta. Hoy los tests usan la real (1 s), porque lo que se demuestra es justamente su efecto.

### D-2 — Contrato

`StockRead {vacuna: str, stock: int}` en `schemas.py`. `vacuna` es un parámetro de ruta `str` sin restricciones adicionales.

### D-3 — `models.py` sólo con docstring

Igual que `health`: explica que el módulo no tiene tablas. No se registra en `app/core/modelos.py`.

### D-4 — Cómo se prueba la concurrencia

Con `httpx.AsyncClient` + `ASGITransport`, las peticiones lanzadas con `asyncio.create_task` corren en el mismo bucle que la app, así que un bloqueo del bucle se ve igual que en uvicorn:

1. Se lanzan tres `GET /laboratorio/stock/...` como tareas y se cede el control (`await asyncio.sleep(0.1)`) para que entren al handler.
2. Se mide `GET /health/live`: tiene que tardar < 0,5 s y las tres consultas todavía tienen que estar en curso (`not t.done()`).
3. Se esperan las tres: todas 200, y el tiempo total desde el lanzamiento es < 2 s.

Mutación esperada: llamar a `cliente.consultar_stock(vacuna)` directo en el service → el `live` tarda ~3 s y las consultas terminan en serie → rojo.

Las pruebas no usan la base: no piden `base_con_seed`, pero sí el fixture `client`, que levanta la app con su lifespan sobre `veterinaria_test`.

### D-5 — `test/laboratorio.http`

Un cliente `.http` manda las peticiones de a una, así que el archivo trae los bloques (tres consultas y el `live`) y, en un comentario, cómo lanzarlas a la vez desde Git Bash:

```bash
for v in rabia moquillo parvovirus; do curl -s 127.0.0.1:8000/laboratorio/stock/$v & done; curl -s -w " live: %{time_total}s\n" 127.0.0.1:8000/health/live; wait
```

El `time_total` del `live` es de milisegundos (medido: 7 ms, igual que sin consultas en curso) aunque las tres consultas tarden un segundo. Se usa `127.0.0.1` porque en Windows `localhost` suma ~0,2 s por conexión, tanto con carga como sin ella.

## Risks / Trade-offs

- [Los tiempos de los tests dependen de la máquina] → los márgenes son amplios (0,5 s contra un bloqueo de ≥1 s; 2 s contra 3 s en serie).
- [Las pruebas suman ~1 s cada una por el `time.sleep(1)` real] → aceptado: es lo que el caso C-09 demuestra.
