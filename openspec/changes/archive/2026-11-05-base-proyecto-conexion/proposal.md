## Why

Todo el TP cuelga de una base que todavía no existe: sin motor asincrónico, sin fábrica de sesiones y sin `get_session`, ningún módulo (dueños, mascotas, prácticas, turnos) puede escribir ni leer, y sin `DATABASE_URL` en un `.env` no versionado el proyecto "no levanta" o expone credenciales, dos condiciones por las que la consigna directamente **no corrige** la entrega. Este change cubre el **Ejercicio 1 — Proyecto, conexión y ciclo de vida (10 % de la nota)**, cuyo criterio es "Estructura, lifespan, `Depends`, `.env` y `env.example`", y deja lista la infraestructura de tests (pytest contra `veterinaria_test`) que el resto de los changes reutiliza con TDD estricto.

## What Changes

- **Estructura obligatoria de la consigna**: `app/main.py` (aplicación, lifespan y registro de routers), `app/core/config.py` (lectura de `DATABASE_URL` desde el entorno con `python-dotenv`), `app/core/database.py` (motor, fábrica de sesiones y dependencia `get_session`) y el módulo `app/modules/health/`.
- **Lifespan**: el motor asincrónico (`create_async_engine` con asyncpg) y la fábrica de sesiones (`expire_on_commit=False`) se crean al arrancar, se guardan en `app.state` y el motor se cierra (`dispose`) al apagar. El esquema **no** se crea en el arranque (lo hará `reiniciar.py` en C-02).
- **Sesión por petición**: `get_session` entrega una sesión por petición vía `Depends(get_session)`, expuesta como alias `SessionDep` para todos los módulos.
- **Salud del servicio** (rutas y códigos exactos de la consigna):
  - `GET /health/live` → **200** `{"estado": "vivo"}`, sin tocar la base.
  - `GET /health/ready` → ejecuta `SELECT 1`; **200** `{"estado": "listo"}` si la base contesta, **503** `{"estado": "sin base"}` si no contesta (con tiempo máximo acotado, sin colgar la petición).
- **Configuración por entorno sin secretos**: `DATABASE_URL` (obligatoria, con error claro si falta o no usa `postgresql+asyncpg`), `TEST_DATABASE_URL` (tests), `SQL_ECHO` (opcional, apagada por defecto, para la evidencia del caso C-07 de la consigna) y las variables `POSTGRES_*` que lee Docker Compose. `env.example` versionado con placeholders; `.env` excluido por `.gitignore`.
- **Entorno reproducible**: `docker-compose.yml` con `postgres:16` publicado por defecto en el puerto **5433** del host (configurable; el 5432 suele estar ocupado por un PostgreSQL local) y un script de inicialización que crea `veterinaria_test`; `requirements.txt` y `requirements-dev.txt` con versiones fijadas; `.gitattributes` para finales de línea LF idénticos en todo el equipo.
- **Infraestructura de tests**: `pytest.ini` (`asyncio_mode = auto`), `tests/conftest.py` con la app levantada con su lifespan real contra `veterinaria_test` y un cliente `httpx.AsyncClient` + `ASGITransport`.
- **Entregable de la cátedra**: primer archivo `.http` en `test/` (`test/health.http`) con la respuesta esperada en un comentario.
- **`README.md` esqueleto** con los pasos desde cero (entorno virtual, dependencias, `.env`, `docker compose up -d`, `python reiniciar.py`, arranque del servidor, `pytest`) y secciones marcadas que completan los changes siguientes.

**Fuera de alcance** (lo hacen otros changes): modelos de tabla y restricciones (C-02), `reiniciar.py` y el seed (C-02), el `.sql` del caso C-08 de la consigna (C-02), la explicación del índice de `turno_practica.turno_id` en el README (C-02), los módulos `duenios`, `mascotas`, `practicas`, `turnos` y `laboratorio` (cada change crea el suyo; no se dejan esqueletos vacíos), el 422 de ruta no entera del caso C-01 de la consigna (C-03). Sin autenticación, repositorios, Unit of Work ni Alembic.

## Capabilities

### New Capabilities
- `conexion-y-ciclo-de-vida`: configuración por entorno (`DATABASE_URL`, `SQL_ECHO`, `env.example` sin secretos), motor y fábrica de sesiones creados y cerrados en el lifespan y guardados en `app.state`, y una sesión por petición vía `Depends(get_session)` con `expire_on_commit=False`.
- `salud-del-servicio`: `GET /health/live` (sin base) y `GET /health/ready` (`SELECT 1`, 200 / 503 acotado en tiempo).

### Modified Capabilities
- (ninguna: es el primer change del proyecto y no hay specs principales en `openspec/specs/`)

## Impact

- **Ejercicio / peso**: Ej. 1 — Proyecto, conexión y ciclo de vida, **10 %**.
- **Reglas de negocio**: ninguna RN-XX (el Ej. 1 es infraestructura).
- **Casos de la consigna**: ninguno se cierra acá; habilita el caso C-09 (`GET /health/live` responde sin depender de la base; el resto llega con C-07) y el caso C-07 (bandera `SQL_ECHO` para la evidencia de consola que se produce en C-06). Habilita la condición de corrección "el proyecto levanta" y "sin credenciales reales en el repositorio".
- **Preguntas abiertas resueltas**: **PA-04** (Python 3.12–3.14 con versiones exactas fijadas), **PA-06** (cuerpos exactos de `/health/ready` 200 y 503) y **PA-08** (`echo=True` por la variable de entorno `SQL_ECHO`, apagada por defecto).
- **Código nuevo**: `app/` (`main.py`, `core/config.py`, `core/database.py`, `modules/health/{schemas,service,router}.py`), `tests/` (`conftest.py` y tests de config, lifespan, sesión y health), `test/health.http`.
- **Archivos de repo nuevos**: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `docker-compose.yml`, `docker/initdb/01-crear-base-test.sql`, `env.example`, `.gitignore`, `.gitattributes`, `README.md`.
- **Dependencias**: `fastapi[standard]`, `sqlmodel`, `sqlalchemy[asyncio]`, `asyncpg`, `python-dotenv`; de desarrollo `pytest`, `pytest-asyncio`, `httpx`, `asgi-lifespan`.
- **Contrato para los changes siguientes**: todos los módulos reciben la sesión con `SessionDep` (de `app.core.database`), registran su router en `app/main.py` y escriben sus tests con las fixtures `app` / `client` de `tests/conftest.py`.
