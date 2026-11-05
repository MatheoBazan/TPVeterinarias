# Descripción General

## Stack tecnológico

Mínimos de la consigna ("Requisitos técnicos") y decisiones del equipo.

| Capa | Tecnología | Versión mínima (PDF) | Uso (PDF) |
|------|-----------|----------------------|-----------|
| Lenguaje | Python | 3.12 | Lenguaje. Desarrollo local del equipo con 3.14 (ver DD-02 y `10`) |
| Framework web | FastAPI | 0.111 | Todos los handlers `async def` |
| Modelos | SQLModel | 0.0.24 | Modelos de tabla y contratos |
| ORM / sesión | SQLAlchemy | 2.0, asincrónico | Motor, sesión y carga anticipada |
| Driver | asyncpg | 0.30 | Controlador asincrónico de PostgreSQL |
| Base de datos | PostgreSQL | 16 | Base de datos |
| Config | python-dotenv | 1.0 | Lectura del archivo `.env` |
| Servidor | uvicorn | el que instala `fastapi[standard]` | Servidor ASGI |

Herramientas del equipo (no exigidas por el PDF): Docker (`postgres:16` vía `docker-compose.yml`), pytest + httpx (`AsyncClient` con `ASGITransport`), `requirements-dev.txt`, OpenSpec (OPSX/SDD), TDD estricto, GitHub privado.

## Arquitectura general

API monolítica por módulo funcional, sin repositorios ni Unit of Work. La lógica vive en el `service.py` de cada módulo, que recibe la sesión como parámetro; el `router.py` recibe, delega y declara la respuesta.

```
Cliente HTTP (.http / recepción)
        │
        ▼
   FastAPI (app/main.py: lifespan + routers)
        │  Depends(get_session): una sesión por petición, expire_on_commit=False
        ▼
 router.py ──► service.py ──► SQLModel/SQLAlchemy 2.0 async ──► asyncpg ──► PostgreSQL 16
                                   │ IntegrityError → rollback → 409
                                   └ joinedload / selectinload (sin lazy loading)

 laboratorio/cliente.py (sincrónico, 1 s, provisto por la cátedra) ──► hilo aparte (threadpool)
```

Decisiones de alto nivel clave (detalle en `08` y `09`):
- Motor asincrónico y fábrica de sesiones creados en el `lifespan`, guardados en `app.state`; el motor se cierra (`dispose`) al apagar.
- La base garantiza integridad (FK, UNIQUE, CHECK, ON DELETE); el service no hace consultas previas "¿ya existe?", escribe y traduce `IntegrityError` a 409.
- Dinero siempre `Decimal` (nunca `float`).

## Integraciones externas

| Servicio | Propósito | Tipo |
|----------|-----------|------|
| PostgreSQL 16 | Persistencia | Driver asyncpg (SQLAlchemy async) |
| Biblioteca del laboratorio (`app/modules/laboratorio/cliente.py`) | Stock de vacunas; función `consultar_stock(vacuna: str) -> int` sincrónica, `time.sleep(1)`, devuelve `10 + len(vacuna)`. **Entregada por la cátedra, no se modifica** | Módulo Python local bloqueante |

No hay otras integraciones (sin auth, sin colas, sin servicios de terceros).

## API REST — endpoints de referencia

Tabla copiada de la consigna ("Endpoints de referencia"). Son 17 endpoints.

| # | Método | Ruta | Cuerpo | Respuesta | Códigos |
|---|--------|------|--------|-----------|---------|
| 1 | GET | `/health/live` | Sin cuerpo | `{"estado": "vivo"}` | 200 |
| 2 | GET | `/health/ready` | Sin cuerpo | Estado de la base | 200, 503 |
| 3 | POST | `/duenios/` | `DuenioCreate` | `DuenioRead` | 201, 409, 422 |
| 4 | GET | `/duenios/{id}` | Sin cuerpo | Dueño con su ficha | 200, 404, 422 |
| 5 | PATCH | `/duenios/{id}` | `DuenioUpdate` | Dueño con su ficha | 200, 404, 409, 422 |
| 6 | DELETE | `/duenios/{id}` | Sin cuerpo | Sin cuerpo | 204, 404, 409 |
| 7 | POST | `/duenios/{id}/ficha` | `FichaCreate` | `FichaRead` | 201, 404, 409 |
| 8 | GET | `/duenios/{id}/mascotas` | Sin cuerpo | Mascotas del dueño | 200, 404 |
| 9 | POST | `/mascotas/` | `MascotaCreate` | `MascotaRead` | 201, 409, 422 |
| 10 | GET | `/mascotas/` | `page`, `size` | Envoltorio con mascotas | 200, 422 |
| 11 | GET | `/mascotas/{id}` | Sin cuerpo | Mascota con su dueño | 200, 404 |
| 12 | POST | `/practicas/` | `PracticaCreate` | `PracticaRead` | 201, 409, 422 |
| 13 | GET | `/practicas/` | Sin cuerpo | Catálogo de prácticas | 200 |
| 14 | POST | `/turnos/` | `TurnoCreate` con `practicas` | Turno con mascota y prácticas | 201, 409, 422 |
| 15 | GET | `/turnos/{id}` | Sin cuerpo | Turno con mascota y prácticas | 200, 404 |
| 16 | DELETE | `/turnos/{id}` | Sin cuerpo | Sin cuerpo | 204, 404 |
| 17 | GET | `/laboratorio/stock/{vacuna}` | Sin cuerpo | Stock informado por el laboratorio (`{"vacuna": ..., "stock": ...}`) | 200 |

Códigos generales (Ej. 2): 201 al crear, 204 al borrar, 404 si el recurso no existe, 409 si la base rechaza la escritura, 422 si cuerpo o parámetros no cumplen el contrato.

## Entorno de desarrollo y pruebas (decisión del equipo)

- Base de desarrollo: Docker `postgres:16` con `docker-compose.yml` en el repo. `DATABASE_URL` sale de un `.env` no versionado; el repo trae `env.example` con la forma del valor y sin secretos.
- Pruebas automáticas del equipo: **pytest + httpx** con TDD estricto, en `tests/`, contra una base separada `veterinaria_test` (`TEST_DATABASE_URL`). Dependencias en `requirements-dev.txt`.
- Pruebas exigidas por la cátedra: archivos **`.http`** (+ un `.sql` para C-08) en **`test/`** (singular). **No confundir**: `tests/` = pytest del equipo; `test/` = entregable de la consigna.
