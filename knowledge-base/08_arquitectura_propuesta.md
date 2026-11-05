# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde | Por qué |
|--------|-------|---------|
| Módulo funcional (vertical slice) | `app/modules/<módulo>/` con `models.py`, `schemas.py`, `service.py`, `router.py` | Estructura obligatoria de la consigna, igual en todos los módulos |
| Service con sesión por parámetro | `service.py` | Lógica fuera del router; sin repositorios ni Unit of Work (fuera de alcance) |
| Inyección de dependencias | `Depends(get_session)` | Una sesión por petición |
| Lifespan | `main.py` | Motor y fábrica de sesiones creados y cerrados con la app, en `app.state` |
| DTO separados de modelos de tabla | `schemas.py` vs `models.py` | Contratos Create/Update/Read; los de alta sin `id`; precio/total fuera del DTO de turno |
| "Escribir y atrapar" | services | La base garantiza integridad; `IntegrityError` → rollback → 409 (sin pre-chequeos) |
| Carga anticipada | services | `joinedload` (a-uno), `selectinload` (colecciones) |
| Offload de código bloqueante | `laboratorio/router.py` | `asyncio.to_thread` / `run_in_threadpool` |

## Estructura de directorios

```
ProyectoVeterinaria/
├── app/
│   ├── main.py                 # app, lifespan, registro de routers
│   ├── core/
│   │   ├── config.py           # lee DATABASE_URL del entorno
│   │   └── database.py         # motor, fábrica de sesiones, get_session
│   └── modules/
│       ├── health/             # router (+ service si hace falta)
│       ├── duenios/            # models (Duenio, FichaDuenio), schemas, service, router
│       ├── mascotas/
│       ├── practicas/
│       ├── turnos/             # models (Turno, TurnoPractica)
│       └── laboratorio/
│           └── cliente.py      # PROVISTO POR LA CÁTEDRA — NO MODIFICAR
├── reiniciar.py                # drop_all + create_all + seed
├── test/                       # ENTREGABLE de la cátedra: .http (+ .sql de C-08)
├── tests/                      # pytest + httpx del equipo (TDD estricto)
├── docker-compose.yml          # postgres:16 (dev) [+ veterinaria_test]
├── docker/initdb/              # 01-crear-base-test.sql (crea veterinaria_test)
├── pytest.ini                  # asyncio_mode=auto, marker integracion
├── env.example                 # forma de DATABASE_URL, sin secretos
├── .env                        # NO versionado
├── requirements.txt
├── requirements-dev.txt        # pytest, pytest-asyncio, httpx
├── README.md
├── knowledge-base/  docs/  openspec/
```

`test/` (singular, `.http`) y `tests/` (plural, pytest) son carpetas distintas y ambas existen a propósito.

## Seguridad

- Autenticación / autorización: **ninguna** (fuera de alcance).
- Validación de input: DTO de Pydantic/SQLModel (tipos, `min_length`, `gt=0`); parámetros de ruta tipados (`int`) → 422.
- Integridad: delegada en la base (FK, UNIQUE, CHECK, ON DELETE).
- Secretos: `DATABASE_URL` solo en `.env` (en `.gitignore`); `env.example` sin credenciales reales. Credenciales reales en el repo = proyecto no corregido.
- Errores 409: mensaje propio, sin filtrar el SQL ni el detalle del driver.

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Conexión async a la base de desarrollo | `postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria` | Sí (en `.env`; `env.example` con placeholders) |
| `TEST_DATABASE_URL` | Base separada para pytest (**decisión del equipo**) | `postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria_test` | Sí |
| `SQL_ECHO` (opcional, confirmada, PA-08) | `1` o `true` activa `echo=True` del motor para la evidencia C-07; apagada por defecto | `1` | No |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Usuario y clave del contenedor `postgres:16` (las lee `docker-compose.yml`, sin valores por defecto) | `<usuario>` / `<clave>` | Sí |
| `POSTGRES_DB` | Base de desarrollo del contenedor | `veterinaria` | No |
| `POSTGRES_PORT` | Puerto del host (5433 por defecto: el 5432 suele estar ocupado por un PostgreSQL local) | `5433` | No |

## Convenciones de código

- Todos los handlers `async def`; ninguna llamada bloqueante en el bucle de eventos.
- Dinero `Decimal` (`NUMERIC`), nunca `float`.
- `fecha`: `TIMESTAMP WITH TIME ZONE`; salida en UTC con `Z`.
- Cada relación con `back_populates` en ambos extremos; `Duenio.ficha` con `uselist=False`; los cinco lados "uno" con `passive_deletes="all"` (no `True`: con hijas cargadas el ORM igual las tocaría; ver D-7 de `openspec/changes/modelos-esquema-seed/design.md`).
- PATCH con `model_dump(exclude_unset=True)`.
- Commits: Conventional Commits, sin líneas de co-autor de IA. Repo privado en GitHub.

## Pruebas (estrategia del equipo)

TDD estricto con pytest + httpx `AsyncClient(transport=ASGITransport(app))` contra `veterinaria_test`; cada caso C-01..C-09 se cubre con un test automatizado y además con su `.http` en `test/`. El `.http` de C-09 y la evidencia C-07 se generan manualmente (consola con `echo=True`).
