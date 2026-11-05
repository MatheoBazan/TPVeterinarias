## Context

Repositorio sin código: sólo `docs/` (consigna), `knowledge-base/`, `openspec/`, `AGENTS.md` / `CLAUDE.md` y `CHANGES.md`. Motivación y alcance en `proposal.md`; comportamiento exigido en `specs/conexion-y-ciclo-de-vida/spec.md` y `specs/salud-del-servicio/spec.md`.

Restricciones que condicionan el diseño:

- **Consigna (manda el PDF)**: estructura `app/main.py` (aplicación, lifespan y routers), `app/core/config.py` (lectura de `DATABASE_URL`), `app/core/database.py` (motor, fábrica de sesiones y `get_session`); motor y fábrica creados en el lifespan y guardados en `app.state`; `Depends(get_session)` con `expire_on_commit=False`; `/health/live` sin base, `/health/ready` con `SELECT 1` y 503. Mínimos: Python ≥3.12, FastAPI ≥0.111, SQLModel ≥0.0.24, SQLAlchemy 2.0 async, asyncpg ≥0.30, python-dotenv ≥1.0, uvicorn de `fastapi[standard]`, PostgreSQL 16.
- **Reglas duras de `AGENTS.md`** aplicables: 2 (todo `async def`, nada bloqueante en el loop), 5 (router delgado), 6 (DTO en `schemas.py`), 8 (snake_case, type hints, nombres en español sin ñ), 9 (PostgreSQL real, sin SQLite ni mocks de sesión), 11 (sin secretos), 12 (commits sin IA).
- **Entorno verificado**: en la PC de Matheo el puerto 5432 lo ocupa un PostgreSQL 18 local (servicio de Windows); Docker Desktop 29.8.2 corriendo; Python 3.14.7; git con `core.autocrlf=true`. Versiones en PyPI consultadas el 2026-11-05 (ver Decisión 12).
- **Estrategia de tests del equipo (decidida)**: pytest + httpx `AsyncClient(transport=ASGITransport(app=app))`, TDD estricto en `tests/`, base real `veterinaria_test` (`TEST_DATABASE_URL`); `.http` de la cátedra en `test/`.

## Goals / Non-Goals

**Goals:**
- Dejar fijado el contrato que usan todos los changes siguientes: `SessionDep` desde `app.core.database`, registro de routers en `crear_app()`, fixtures `app` / `client` en `tests/conftest.py`.
- Que la suite de tests pruebe el ciclo de vida real (lifespan ASGI de verdad, motor real, PostgreSQL real), sin dobles de prueba de la sesión.
- Que `GET /health/ready` nunca cuelgue la petición, aunque la base no conteste.
- Que un integrante nuevo pase de `git clone` a `pytest` verde siguiendo sólo el README.

**Non-Goals:**
- Tolerancia a fallos de la base más allá de la sonda (sin `pool_pre_ping`, sin reintentos, sin timeout de conexión global): si la base cae, los endpoints de negocio fallan como falle SQLAlchemy.
- Logging estructurado o configuración de logging propia (sólo el eco de SQL de la Decisión 4 y un `warning` en la sonda).
- Empaquetado (`pyproject.toml`, instalación como paquete) y lockfile de dependencias transitivas.
- Cualquier tabla, `reiniciar.py`, o módulo distinto de `health` (ver "Fuera de alcance" en `proposal.md`).

## Decisions

### Decisión 1 — Secretos y Docker Compose: credenciales sólo en `.env`, sin valores por defecto
`docker-compose.yml` define un servicio `db` con `image: postgres:16` y toma todo del `.env` (Compose lo carga solo desde la raíz del proyecto):

- `POSTGRES_USER: ${POSTGRES_USER:?…}`, `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?…}` → **sin default**: si falta el `.env`, Compose aborta con un mensaje claro en vez de levantar una base con una clave inventada escrita en el repo.
- `POSTGRES_DB: ${POSTGRES_DB:-veterinaria}` (el nombre de la base no es secreto).
- `ports: "${POSTGRES_PORT:-5433}:5432"` → por defecto **5433** en el host (el 5432 está ocupado por el PostgreSQL 18 local de Matheo); cada integrante lo cambia en su `.env`.
- Volumen con nombre `datos_postgres:/var/lib/postgresql/data`.
- `./docker/initdb:/docker-entrypoint-initdb.d:ro` con **`docker/initdb/01-crear-base-test.sql`** = `CREATE DATABASE veterinaria_test;` (se ejecuta como `POSTGRES_USER`, que queda dueño).
- `healthcheck` con `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` para que `docker compose up -d --wait` (o `docker compose ps`) indique cuándo está lista.

**Los scripts de `/docker-entrypoint-initdb.d` sólo corren con el volumen vacío.** Quien ya tenía el volumen creado antes de este change no tendrá `veterinaria_test`: el README documenta las dos salidas — `docker compose exec db createdb -U <usuario> veterinaria_test` (conserva datos) o `docker compose down -v && docker compose up -d` (borra todo).

Este `.sql` de inicialización no es el `.sql` del caso C-08 de la consigna (ese va en `test/`, en C-02).

**Alternativas**: credenciales literales en el compose (descartada: es exactamente lo que la consigna penaliza); `${POSTGRES_PASSWORD:-postgres}` con default (descartada: deja una clave en el repo y oculta la falta del `.env`); `env_file: .env` (descartada: mete en el contenedor variables que no le corresponden, como `DATABASE_URL`); un segundo servicio PostgreSQL sólo para tests (descartada: duplica recursos; dos bases en el mismo servidor alcanzan); script `.sh` parametrizado con el nombre de la base de test (descartada: frágil ante finales de línea CRLF en Windows y agrega otra variable; el nombre `veterinaria_test` es una decisión del equipo).

### Decisión 2 — Forma de `env.example`: placeholders literales, valores duplicados a propósito
```
POSTGRES_USER=<usuario>
POSTGRES_PASSWORD=<clave>
POSTGRES_DB=veterinaria
POSTGRES_PORT=5433
DATABASE_URL=postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria
TEST_DATABASE_URL=postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria_test
SQL_ECHO=0
```
con comentarios: copiar a `.env` (no se versiona), reemplazar `<usuario>` y `<clave>` en las tres líneas, mantener el puerto igual en `POSTGRES_PORT` y en las URLs, y codificar en URL los caracteres especiales de la clave (`@`, `:`, `/`, `#`).

**Alternativas**: interpolación de python-dotenv (`DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@…`) — evita duplicar, pero esconde "la forma del valor" que pide la consigna y se rompe con claves con caracteres especiales; descartada. Usar `usuario` / `clave` sin corchetes (como el ejemplo de la KB 08) — funcionarían copiados tal cual y terminarían siendo las credenciales reales del equipo dentro del repo; descartada.

### Decisión 3 — `app/core/config.py`: `load_dotenv` al importar, lectura validada en el lifespan
- Al importar el módulo: `load_dotenv(RAIZ_PROYECTO / ".env")` con `RAIZ_PROYECTO = Path(__file__).resolve().parents[2]` y `override=False` (por defecto). Ruta explícita: funciona igual se ejecute desde la raíz, desde `tests/` o con `python reiniciar.py`; si el archivo no existe no falla (las variables pueden venir del entorno).
- `cargar_configuracion() -> Configuracion` (dataclass congelada con `database_url: str` y `sql_echo: bool`) lee **`os.environ` en el momento de llamarla**, y la llama el **lifespan**, no el import.
- Validaciones, todas con la excepción propia `ConfiguracionInvalida(RuntimeError)`:
  - falta o está vacía (`strip()`) → "Falta la variable de entorno DATABASE_URL. Copiá env.example a .env y completala.";
  - no se puede interpretar como URL (`sqlalchemy.engine.make_url` lanza `ArgumentError`) → mensaje equivalente;
  - `drivername != "postgresql+asyncpg"` → "DATABASE_URL debe empezar con postgresql+asyncpg:// …" (atrapa el `postgresql://` copiado de otro lado y cualquier intento de SQLite, regla dura 9).
- **Ningún mensaje incluye la URL** (contiene la clave).

**Por qué en el lifespan y no al importar**: los tests cambian `DATABASE_URL` con `monkeypatch.setenv` antes de levantar cada app (Decisión 13), y `import app.main` no falla en una máquina sin `.env` (herramientas, `fastapi dev`, inspección). **Por qué `load_dotenv` al importar y no dentro de `cargar_configuracion`**: si se recargara en cada llamada, un test que borra `DATABASE_URL` con `monkeypatch.delenv` la vería reaparecer desde el `.env` del integrante y no podría probar el error.

**Alternativas**: `pydantic-settings` (dependencia extra; la consigna nombra python-dotenv; descartada); constante de módulo `DATABASE_URL = os.environ[...]` (impide redirigir los tests y rompe el import sin `.env`; descartada); no validar el controlador (el error de SQLAlchemy "the asyncio extension requires an async driver" es críptico para el equipo; descartada por una línea de código).

### Decisión 4 — PA-08: eco de SQL con `SQL_ECHO`, apagado por defecto
`sql_echo = os.environ.get("SQL_ECHO", "").strip().lower() in {"1", "true"}` y el motor se crea con `echo=config.sql_echo`. Para la evidencia del caso C-07 de la consigna (C-06): `SQL_ECHO=1` en el `.env` o en la sesión de la terminal, y `uvicorn app.main:app`. Nombre `SQL_ECHO` (no `DB_ECHO`) porque es el que ya documentan `knowledge-base/08` y PA-08.

**Alternativas**: `echo=True` fijo (ensucia la consola y los tests; descartada); configurar el logger `sqlalchemy.engine` con `--log-config` de uvicorn (más archivos y más pasos para el corrector; descartada); aceptar también `si`/`yes`/`on` (sin necesidad real; descartada).

### Decisión 5 — `app/core/database.py`: fábricas puras + `get_session` + `SessionDep`
- `crear_motor(config) -> AsyncEngine` = `create_async_engine(config.database_url, echo=config.sql_echo)`. Pool por defecto (`AsyncAdaptedQueuePool`); **sin** `connect_args={"timeout": …}` ni `pool_pre_ping` (ver Non-Goals; la sonda acota su propio tiempo en la Decisión 10).
- `crear_fabrica_sesiones(engine) -> async_sessionmaker[AsyncSession]` = `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`, con **`AsyncSession` de `sqlmodel.ext.asyncio.session`** para que los services usen `await session.exec(select(...))` (el `execute` de SQLModel está marcado como obsoleto y emite advertencia).
- `async def get_session(request: Request) -> AsyncIterator[AsyncSession]`: `async with request.app.state.session_factory() as session: yield session`. El `async with` cierra la sesión (y hace rollback de lo no confirmado) al terminar la petición, también si el handler lanza.
- `SessionDep = Annotated[AsyncSession, Depends(get_session)]`: el alias que importan todos los módulos.
- Ningún motor ni sesión a nivel de módulo: `database.py` no tiene estado global.

**Alternativas**: motor global creado al importar (contradice la consigna y ata el motor al event loop del import, lo que rompe los tests con un loop por test; descartada); `AsyncSession` de SQLAlchemy (sin `exec`; descartada); `sessionmaker(class_=AsyncSession)` (API legada; `async_sessionmaker` es la de SQLAlchemy 2.0; descartada).

### Decisión 6 — Alcance de la dependencia: `Depends(get_session)` tal cual (scope por defecto)
Se usa la forma literal de la consigna. Desde FastAPI 0.121 existe `Depends(..., scope="function")`, que cierra la sesión antes de enviar la respuesta; con el scope por defecto (`"request"`) se cierra después. Para este TP no cambia nada observable (los services confirman explícitamente antes de responder) y la forma literal es la que mira el corrector. Se revisa si algún change necesita lo contrario.

### Decisión 7 — `app/main.py`: lifespan + fábrica `crear_app()` + `app` de módulo
```python
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
```
- `create_async_engine` no conecta: el arranque funciona con la base caída (`/health/live` responde igual) y no crea el esquema (lo hará `reiniciar.py`, C-02).
- `try/finally` garantiza el `dispose` aunque algo falle durante la vida de la app.
- Nombres en `app.state`: `engine` y `session_factory` (los términos de SQLAlchemy; la consigna no fija nombres).
- `uvicorn app.main:app` y `fastapi dev app/main.py` encuentran `app`. Cada change agrega su `include_router` en `crear_app()`.

**Por qué la fábrica**: los tests de sesión (Decisión 13) agregan una ruta sonda a una app nueva; con una sola `app` global esa ruta quedaría registrada para todos los tests y para producción. Es una función de tres líneas; no agrega capas. Nombre en español por coherencia con `cargar_configuracion`, `crear_motor`, etc.; `get_session` queda en inglés porque lo fija la consigna.

**Alternativas**: sólo `app` de módulo (descartada por lo anterior); `@app.on_event("startup")` (obsoleto en FastAPI; descartada); que el lifespan devuelva un `dict` de estado (lifespan state de Starlette) — la consigna dice explícitamente `app.state`; descartada.

### Decisión 8 — Estructura del módulo `health`: `models.py`, `schemas.py`, `service.py`, `router.py` (APROBADA por Matheo, 2026-11-05)
- `models.py`: **sólo un docstring** que explica que `health` no tiene tablas (no define clases ni importa nada). Existe para cumplir al pie de la letra "la organización es por módulo funcional, con la misma estructura en todos" (consigna, Estructura del proyecto) y el criterio "Estructura" del Ej. 1.
- `schemas.py`: `EstadoSalud(SQLModel)` con `estado: str` — DTO de salida (regla dura 6; no lleva `extra="forbid"` porque no es de entrada).
- `service.py`: `base_disponible(session) -> bool` (Decisión 10).
- `router.py`: `APIRouter(prefix="/health", tags=["health"])` con los dos handlers `async def`.
- `__init__.py` vacíos en `app/`, `app/core/`, `app/modules/`, `app/modules/health/`.

**Alternativa descartada**: omitir `models.py` porque `health` no tiene tablas (archivo "vacío" = ruido). Se descarta: un corrector estricto puede marcar la estructura distinta, y el costo de cumplirla es una línea. **Aplica igual a `laboratorio` en C-07.**

### Decisión 9 — PA-06: cuerpos de `/health/ready` y forma del 503
- 200 → `{"estado": "listo"}`; 503 → `{"estado": "sin base"}` (propuesta de DD-16, mismo esquema que `/health/live`).
- El handler recibe `response: Response` y, si la base no está disponible, hace `response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE` y devuelve `EstadoSalud(estado="sin base")`.
- Se declara `response_model=EstadoSalud` y `responses={503: {"model": EstadoSalud, "description": "La base no contesta"}}` para que OpenAPI muestre los dos códigos.
- El cuerpo no lleva detalle del error, del controlador ni de la URL.

**Alternativas**: `raise HTTPException(503, detail=...)` → cuerpo `{"detail": "..."}`, distinto del de 200 (dos formas para la misma ruta; descartada; el formato `{"detail": ...}` de errores de negocio lo define C-03 en PA-11); cuerpo más rico (`{"estado": ..., "base": ..., "latencia_ms": ...}`) — nada lo pide y expone más información; descartada.

### Decisión 10 — La sonda `SELECT 1`: sesión por `Depends`, tiempo máximo y qué se considera "no contesta"
```python
TIMEOUT_READY_SEGUNDOS: float = 2.0

async def base_disponible(session: AsyncSession) -> bool:
    try:
        async with asyncio.timeout(TIMEOUT_READY_SEGUNDOS):
            resultado = await session.exec(text("SELECT 1"))
            return resultado.scalar_one() == 1
    except Exception as exc:  # CancelledError es BaseException: se propaga
        logger.warning("La base no contesta a SELECT 1 (%s)", type(exc).__name__)
        return False
```
- **Usa `SessionDep`** (no el motor directo): deja en C-01 un handler real con `Depends(get_session)`, que es lo que evalúa el criterio del Ej. 1, y prueba la cadena completa lifespan → fábrica → sesión → base.
- **`text("SELECT 1")` con `session.exec`**: el `exec` de SQLModel acepta cualquier `Executable` en tiempo de ejecución (los overloads de tipado no listan `TextClause`; el proyecto no corre mypy). Si una versión futura lo rechazara, `select(1)` genera el mismo SQL.
- **`asyncio.timeout` envuelve todo** (préstamo de conexión del pool, conexión de asyncpg y la consulta): acota también el caso "acepta la conexión y nunca contesta", que el timeout de conexión de asyncpg (60 s por defecto) no cubriría a tiempo. 2 s: holgado para una base local y suficientemente corto para que la petición no "cuelgue". Constante de módulo leída en cada llamada, para que los tests la bajen con `monkeypatch.setattr(service, "TIMEOUT_READY_SEGUNDOS", 0.5)`.
- **`except Exception` (no una tupla)**: al conectar, SQLAlchemy no envuelve los errores de asyncpg; llegan crudos `ConnectionRefusedError` / `socket.gaierror` (`OSError`), `TimeoutError`, `asyncpg.InvalidCatalogNameError` / `InvalidPasswordError` (`asyncpg.PostgresError`, no es `OSError` ni `SQLAlchemyError`), y durante la consulta `sqlalchemy.exc.DBAPIError`. Para una sonda cuyo único contrato es "¿la base contesta `SELECT 1`?", cualquier excepción significa "no lista". `asyncio.CancelledError` hereda de `BaseException`, así que la cancelación de la petición no se traga (regla de async-python-patterns). Se registra sólo el tipo de excepción, nunca el mensaje (puede incluir usuario o host).
- La sesión se cierra en `get_session` aunque la conexión haya fallado; el pool de SQLAlchemy repone su contador ante la excepción, así que un 503 no deja la app inutilizada.

**Alternativas**: tupla `(OSError, SQLAlchemyError)` (un `InvalidCatalogNameError` o `InvalidPasswordError` terminaría en 500 en lugar de 503; descartada); `engine.connect()` directo en el service sin sesión (más simple, pero no demuestra `Depends(get_session)`; descartada); `connect_args={"timeout": 2}` en el motor en lugar de `asyncio.timeout` (no acota una consulta colgada y afecta a todos los endpoints; descartada); timeout configurable por variable de entorno (nadie lo necesita cambiar fuera de los tests; descartada).

### Decisión 11 — `/health/live` sin dependencias
`async def live() -> EstadoSalud: return EstadoSalud(estado="vivo")`. Sin `SessionDep` ni ninguna otra dependencia: no hay forma de que toque la base, y no depende de que el pool tenga conexiones libres (lo que el caso C-09 de la consigna necesita: responde de inmediato aunque haya consultas lentas en curso).

### Decisión 12 — PA-04: versiones exactas para las dependencias directas, línea SQLAlchemy 2.0
**Recomendación: fijar con `==` las dependencias directas** (no las transitivas). Versiones consultadas en PyPI el 2026-11-05; todas tienen wheels `win_amd64` para cp312, cp313 y cp314 o son puro Python:

`requirements.txt`
```
fastapi[standard]==0.162.0
sqlmodel==0.0.48
sqlalchemy[asyncio]==2.0.57
asyncpg==0.32.0
python-dotenv==1.2.4
```
`requirements-dev.txt`
```
-r requirements.txt
pytest==9.2.0
pytest-asyncio==1.4.1.post1
httpx==0.28.1
asgi-lifespan==2.1.0
```
- Python soportado: **3.12, 3.13 y 3.14** (sqlmodel 0.0.48 pide ≥3.10; SQLAlchemy 2.0.57, asyncpg 0.32.0, greenlet 3.5.6 y pydantic-core 2.50.4 publican wheels para las tres).
- **`sqlalchemy[asyncio]`** y no `sqlalchemy` a secas: garantiza `greenlet` en cualquier plataforma (sin él, el modo async falla con `ValueError: the greenlet library is required`).
- **Línea 2.0** (no 2.1.8, la más nueva): la consigna dice "SQLAlchemy 2.0" y sus secciones usan esa API; 2.1 salió en septiembre de 2026 y no aporta nada al TP. sqlmodel 0.0.48 admite `>=2.0.14,<2.2`.
- `httpx` se lista aunque ya lo traiga `fastapi[standard]`, porque los tests lo importan directamente; `asgi-lifespan` es la herramienta que recomienda la documentación de FastAPI para correr el lifespan con `AsyncClient` (Decisión 13).
- uvicorn llega con `fastapi[standard]` (como dice la consigna); no se fija aparte.

**Por qué fijar**: "un proyecto que no levanta no se corrige", y la corrección puede ocurrir semanas después de la entrega. FastAPI (0.x) y SQLModel (0.0.x) no prometen compatibilidad entre versiones menores, así que un rango `>=` deja abierta una rotura ajena al equipo; con `==` los tres integrantes y el corrector instalan lo mismo. Actualizar es un cambio explícito (editar el pin, `pip install -r`, `pytest`).

**Alternativas**: rangos `>=mínimo_del_PDF` (máxima flexibilidad, cero reproducibilidad; descartada); rangos acotados `>=x,<y` (en paquetes 0.x el techo no protege; descartada); lockfile completo con pip-tools o uv (fija también las transitivas, pero suma una herramienta que el corrector no tiene por qué conocer; descartada para un TP); SQLAlchemy 2.1.8 (descartada por fidelidad a la consigna).

### Decisión 13 — Infraestructura de tests
**`pytest.ini`** (sin `pyproject.toml`):
```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
asyncio_default_test_loop_scope = function
addopts = --strict-markers
markers =
    integracion: necesita el PostgreSQL de test (docker compose up -d)
```
`pythonpath = .` porque `tests/` no es paquete y `import app` necesita la raíz en `sys.path`.

**Problemas conocidos y cómo se resuelven**:
1. **`ASGITransport` no ejecuta el lifespan** (lo advierte la documentación de FastAPI) → las fixtures envuelven la app en `asgi_lifespan.LifespanManager`, que dispara el startup/shutdown ASGI reales. Como el lifespan no devuelve estado (usa `app.state`), el transporte recibe la propia `FastAPI` y los tests pueden leer `app.state`.
2. **Un motor asyncpg queda atado al event loop que lo creó** → todas las fixtures async son de scope `function` (y el loop también, por la configuración de arriba): cada test crea su app, su motor y su loop, y el `dispose` ocurre en el mismo loop. Crear un motor no conecta, así que el costo es mínimo. Ninguna fixture de `session` / `module` comparte motor.
3. **Apuntar a `veterinaria_test`** → la fixture `url_base_test` lee `TEST_DATABASE_URL` (cargada del `.env` por `app.core.config` al importarse), falla con `pytest.fail` si falta o si `make_url(url).database` no termina en `_test`, y hace `monkeypatch.setenv("DATABASE_URL", url)` **antes** de entrar al lifespan (que lee la config en ese momento, Decisión 3). El guard protege la base de desarrollo de los `drop_all` que vendrán en C-02. La validación vive en una función pura `validar_url_de_test(url: str | None) -> str` (llama a `pytest.fail`) en `tests/soporte.py`, que importan `conftest.py` y el test del guard (`from soporte import ...`: con el modo de import por defecto de pytest, `tests/` está en `sys.path`), para probarla sin base con `pytest.raises(pytest.fail.Exception)`. Ahí viven también los helpers para levantar una app con una URL arbitraria y el servidor mudo del punto 4.
4. **Probar el 503 rápido** → un helper `levantar_app(url)` en `tests/soporte.py` (y la fixture `servidor_mudo`) para tres URLs:
   - `postgresql+asyncpg://nadie:nada@127.0.0.1:1/inexistente` — nada escucha (`127.0.0.1` explícito, no `localhost`, para no intentar también `::1`);
   - un **servidor mudo**: `asyncio.start_server(manejador, "127.0.0.1", 0)` en el mismo loop del test, cuyo manejador lee hasta EOF y nunca escribe; la fixture cierra los `writer` pendientes antes de `server.close()` / `await server.wait_closed()` (desde Python 3.12 `wait_closed` espera a que se cierren las conexiones);
   - el servidor de test con una base inexistente: `make_url(TEST_DATABASE_URL).set(database="base_inexistente_test")`.
   En los tres, `monkeypatch.setattr(service, "TIMEOUT_READY_SEGUNDOS", 0.5)` y se mide con `time.perf_counter()` que la respuesta llegue antes de `timeout + 1 s` (en Windows un "connection refused" en localhost puede tardar ~2 s; con 0.5 s gana el timeout y el resultado es 503 igual).
5. **"El lifespan crea, guarda y cierra el motor"** → con `LifespanManager` explícito en el test: dentro, `isinstance(app.state.engine, AsyncEngine)`, `isinstance(app.state.session_factory, async_sessionmaker)` y `app.state.engine.url.database` igual al de `TEST_DATABASE_URL`; se registra `event.listen(engine.sync_engine, "engine_disposed", …)`, se abre y devuelve una conexión real (`async with engine.connect() as conn: await conn.execute(text("SELECT 1"))`, así el test no depende del módulo `health`) y se guarda `pool = engine.pool` (con `pool.checkedin() == 1`); al salir del lifespan, el evento se disparó una vez y `pool.checkedin() == 0` (el pool viejo cerró su conexión; `dispose` reemplaza el pool, por eso se guarda la referencia antes).
6. **"Una sesión por petición"** → `tests/test_sesion.py` arma `crear_app()` y le agrega una ruta sonda local al test (antes del lifespan) que recibe `SessionDep` y además una dependencia que también pide `SessionDep`, guarda las sesiones en una lista (mantener las referencias evita falsos positivos por reutilización de `id()`), ejecuta `SELECT 1` y devuelve si ambas referencias son la misma. Se verifica: distinta entre dos peticiones (`is not`), la misma dentro de una (`is`), `session.sync_session.expire_on_commit is False`, `isinstance(session, sqlmodel.ext.asyncio.session.AsyncSession)` y `engine.pool.checkedout() == 0` después de la respuesta (httpx con `ASGITransport` espera a que termine toda la llamada ASGI, incluido el cierre de la dependencia).
7. **"Live no toca la base"** → con la base caída responde 200; y, con la base de test, después de `GET /health/live` el pool tiene `checkedin() == 0` y `checkedout() == 0`, mientras que después de `GET /health/ready` tiene `checkedin() == 1` (el contraste evita una aserción tautológica).

**Fixtures base en `tests/conftest.py`**: `url_base_test`, `app` (función: `crear_app()` + `LifespanManager`), `client` (`AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`) y `servidor_mudo` (puerto del servidor del punto 4); la lógica reutilizable está en `tests/soporte.py`. Los módulos con tests de base declaran `pytestmark = pytest.mark.integracion`; `pytest -m "not integracion"` corre sólo los de configuración y repositorio.

**Alternativas**: `app.router.lifespan_context(app)` en lugar de `asgi-lifespan` (sin dependencia extra, pero usa un atributo interno de Starlette y no ejercita el protocolo ASGI de lifespan; descartada); `TestClient` sincrónico de Starlette (corre el lifespan pero en otro hilo/loop, mezcla sync con la suite async; descartada); motor de scope `session` con `loop_scope="session"` (más rápido, pero acopla los tests entre sí y obliga a cuidar el loop; descartada hasta que la suite sea lenta); mocks de la sesión o SQLite (prohibidos, regla dura 9).

### Decisión 14 — Archivos de repositorio
- **`.gitignore`**: `.env`, `.env.*` (no afecta a `env.example`), `.venv/`, `venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `.mypy_cache/`, `.ruff_cache/`, `.idea/`. **No** se ignoran `.claude/`, `.atl/`, `.active-orchestrator-state.json` ni `skills-lock.json` (se versionan a propósito, ver `AGENTS.md`).
- **`.gitattributes`**: `* text=auto eol=lf` y `*.pdf binary` (más `*.png binary` / `*.jpg binary` por si se agregan capturas de la evidencia C-07). Con `core.autocrlf=true` en la PC de Matheo, se corre una vez `git add --renormalize .` en el mismo commit.
- **`test/health.http`**: variable `@base = http://localhost:8000` y un bloque `###` por caso, cada uno con un comentario `# Esperado: <código> <cuerpo>`: live (200 `{"estado": "vivo"}`), ready con la base arriba (200 `{"estado": "listo"}`), ready con la base detenida con `docker compose stop db` (503 `{"estado": "sin base"}` en menos de ~2 s). Compatible con REST Client de VS Code y el HTTP Client de JetBrains.
- **`README.md`** (esqueleto): requisitos (Python 3.12–3.14, Docker); pasos desde cero — entorno virtual (`py -3.14 -m venv .venv` / `python -m venv .venv`, activación en PowerShell y en bash), `pip install -r requirements-dev.txt` (o `requirements.txt` sólo para correr la API), copiar `env.example` a `.env` y completarlo, `docker compose up -d`, `python reiniciar.py` (marcado "disponible desde C-02 `modelos-esquema-seed`"), `uvicorn app.main:app --reload` (o `fastapi dev app/main.py`), `pytest`; tabla de variables de entorno; `tests/` vs `test/`; nota del puerto 5433 y de la base de test con volumen preexistente (Decisión 1). Secciones con encabezado propio que completan otros changes: "Índice de `turno_practica.turno_id`" (C-02), "Evidencia del caso C-07" (C-06). En el código no queda ningún `TODO`.

### Decisión 15 — Tests de higiene del repositorio (sin base)
`tests/test_repositorio.py` (tests `def` sincrónicos; la regla "nunca `def`" es para handlers): `env.example` declara las siete variables y sus URLs tienen la forma con `<usuario>` / `<clave>`; si `POSTGRES_PASSWORD` está definida en el entorno, su valor no aparece en `env.example` ni en `docker-compose.yml`; `git check-ignore -q .env` devuelve 0 (con `subprocess.run`; se salta con `pytest.skip` si git no está instalado). Son baratos y cubren la única condición de "no se corrige" que se puede romper con un copiar/pegar.

## Risks / Trade-offs

- [Volumen de Docker creado antes de este change → no existe `veterinaria_test`] → README con `createdb` manual o `docker compose down -v`; el test de la base falla con el error de conexión de asyncpg nombrando la base, no en silencio.
- [Un pin queda sin wheel o con un bug en la máquina de un integrante] → la tarea 0 instala en un venv limpio con 3.14 y corre `pip check`; si algo falla se baja al patch anterior y se registra en este design. Las transitivas (pydantic, starlette, pydantic-core) no están fijadas: se acepta, pydantic 2.x es semver.
- [Un integrante tiene ocupado también el 5433] → cambia `POSTGRES_PORT` y el puerto de las dos URLs en su `.env`; nada del código depende del puerto.
- [Clave con `@`, `:` o `/` rompe la URL] → comentario en `env.example` y README: codificarla en URL (o elegir una sin esos caracteres para la base local).
- [`except Exception` en la sonda puede esconder un bug propio dentro de `base_disponible`] → el bloque `try` contiene sólo la consulta; los tests de 200 detectan cualquier error propio (darían 503 en vez de 200) y el `warning` deja el tipo de excepción en la consola.
- [Tiempo de los tests de 503: hasta ~1,5 s cada uno con el timeout bajado a 0,5 s] → aceptable (tres o cuatro tests); si la suite crece se marcan aparte.
- [Conexiones viejas en el pool después de reiniciar el contenedor: el primer `/health/ready` puede dar 503 y el siguiente 200] → aceptable para una sonda; SQLAlchemy invalida la conexión rota. Si molesta, `pool_pre_ping=True` es un cambio de una línea (agrega un ping por préstamo).
- [El monkeypatch del timeout depende de que el service lea la constante del módulo en cada llamada] → el service no la copia a una variable local ni la importa por valor desde otro módulo; los tests la parchean en `app.modules.health.service`.
- [`.gitattributes` con `autocrlf=true` → diffs de finales de línea] → `git add --renormalize .` una vez; desde ahí todos ven LF.
- [Tipado: los overloads de `AsyncSession.exec` no incluyen `TextClause`] → sin efecto en ejecución; el proyecto no corre mypy.

## Migration Plan

Primer change: no hay datos ni código que migrar. Puesta en marcha: tareas de la sección 0 de `tasks.md` (venv, dependencias, `.env`, `docker compose up -d`). Vuelta atrás: `docker compose down -v` elimina contenedor y volumen; el resto son archivos nuevos que se revierten con git.
