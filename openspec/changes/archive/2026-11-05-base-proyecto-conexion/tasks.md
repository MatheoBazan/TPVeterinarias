> TDD estricto (`~/.claude/CLAUDE.md` + `openspec/config.yaml`): ningún código de producción sin un test en rojo antes; cada comportamiento con al menos 2 casos; tests en verde después de cada refactor. Todo contra PostgreSQL real (`veterinaria_test`), nunca SQLite ni mocks de la sesión. Referencias "D-N" = decisiones de `design.md`. Es el primer change: no hay suite previa (red de seguridad = 0 tests).

## 0. Entorno de trabajo (archivos de infraestructura, sin código de producción)

- [x] 0.1 Crear `requirements.txt` y `requirements-dev.txt` con los pins exactos de D-12; crear `.venv` con Python 3.12–3.14 (`py -3.14 -m venv .venv`), activarlo, `pip install -r requirements-dev.txt`, y verificar `pip check` sin errores y `python -c "import fastapi, sqlmodel, sqlalchemy, asyncpg, dotenv, greenlet, asgi_lifespan, httpx"`. Si un pin no instala, bajar al patch anterior y registrar el cambio en D-12 de `design.md`.
- [x] 0.2 Crear `.gitignore` y `.gitattributes` (D-14); correr `git add --renormalize .`; verificar que `git check-ignore .env` imprime `.env` y que `.claude/`, `.atl/` y `skills-lock.json` siguen versionados.
- [x] 0.3 Crear `env.example` (D-2) y copiarlo a `.env` con usuario y clave locales reales (el `.env` nunca se agrega a git).
- [x] 0.4 Crear `docker-compose.yml` y `docker/initdb/01-crear-base-test.sql` (D-1); `docker compose up -d --wait`; verificar con `docker compose exec db psql -U <usuario> -lqt` que existen `veterinaria` y `veterinaria_test` (si el volumen ya existía: `docker compose exec db createdb -U <usuario> veterinaria_test` o `docker compose down -v`).
- [x] 0.5 Crear `pytest.ini` (D-13), los `__init__.py` vacíos de `app/`, `app/core/`, `app/modules/` y `app/modules/health/`, y la carpeta `tests/`; correr `pytest` y confirmar que carga la configuración sin errores (sale con "no tests ran", código 5).

## 1. Configuración por entorno — `app/core/config.py`, tests en `tests/test_config.py` (sin base)

- [x] 1.1 RED: `test_cargar_configuracion_con_database_url_devuelve_esa_url` (`monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5433/veterinaria_test")`); ejecutar y confirmar que falla porque `app.core.config` no existe.
- [x] 1.2 GREEN: `RAIZ_PROYECTO`, `load_dotenv(RAIZ_PROYECTO / ".env")` al importar, dataclass congelada `Configuracion(database_url, sql_echo)` y `cargar_configuracion()` mínima que lee `os.environ`; ejecutar → verde.
- [x] 1.3 TRIANGULAR errores (`@pytest.mark.parametrize`): `DATABASE_URL` ausente (`monkeypatch.delenv`), `""` y `"   "` → `ConfiguracionInvalida` cuyo mensaje contiene `DATABASE_URL` y `env.example`; `postgresql://u:clave_secreta@localhost/x` y `sqlite+aiosqlite:///x.db` → `ConfiguracionInvalida` que exige `postgresql+asyncpg://` y cuyo mensaje NO contiene `clave_secreta`. Generalizar con `make_url` / `ArgumentError` hasta que pasen todos.
- [x] 1.4 TRIANGULAR `SQL_ECHO` (parametrize): ausente, `"0"`, `"false"`, `""` → `sql_echo is False`; `"1"`, `"true"`, `"TRUE"` → `sql_echo is True` (D-4).
- [x] 1.5 REFACTOR: mensajes como constantes del módulo, type hints en todas las firmas; `pytest tests/test_config.py` en verde.

## 2. Infraestructura de tests contra `veterinaria_test` — `tests/soporte.py`, `tests/conftest.py`, `tests/test_soporte.py`

- [x] 2.1 RED: `tests/test_soporte.py` (sin base) con `validar_url_de_test` parametrizado: `None` → `pytest.fail` con mensaje que nombra `TEST_DATABASE_URL` y `env.example`; `.../veterinaria` → `pytest.fail` que exige el sufijo `_test`; `.../veterinaria_test` → devuelve la URL. Ejecutar → rojo (no existe `tests/soporte.py`).
- [x] 2.2 GREEN: `tests/soporte.py` con `validar_url_de_test` (usa `make_url(url).database`); ejecutar → verde.
- [x] 2.3 Escribir en `tests/conftest.py` las fixtures de scope function `url_base_test` (lee `TEST_DATABASE_URL`, la valida y hace `monkeypatch.setenv("DATABASE_URL", url)`), `app` (`crear_app()` dentro de `LifespanManager`, devuelve la `FastAPI`) y `client` (`AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`), más en `soporte.py` el helper async para levantar una app con una URL arbitraria (D-13). Todavía no se ejecuta: depende de `app.main` (sección 3).

## 3. Lifespan, motor y fábrica de sesiones — `app/core/database.py`, `app/main.py`, tests en `tests/test_lifespan.py` (`pytestmark = pytest.mark.integracion`)

- [x] 3.1 RED: `test_lifespan_guarda_motor_y_fabrica_en_app_state` con la fixture `app`: `isinstance(app.state.engine, AsyncEngine)`, `isinstance(app.state.session_factory, async_sessionmaker)` y `app.state.engine.url.database == make_url(TEST_DATABASE_URL).database` (prueba además que el entorno del proceso prevalece sobre el `.env`); ejecutar → rojo (no existe `app.main`).
- [x] 3.2 GREEN: `crear_motor(config)` y `crear_fabrica_sesiones(engine)` (`async_sessionmaker(engine, class_=AsyncSession de sqlmodel, expire_on_commit=False)`) en `database.py`; `lifespan` (config → motor → `app.state.engine` / `app.state.session_factory` → `yield` → `await engine.dispose()` en `finally`), `crear_app()` y `app = crear_app()` en `main.py` (D-5, D-7); ejecutar → verde.
- [x] 3.3 TRIANGULAR eco: con `SQL_ECHO=1` → `app.state.engine.echo is True`; sin `SQL_ECHO` → `False` (parametrize).
- [x] 3.4 TRIANGULAR arranque: con `DATABASE_URL=postgresql+asyncpg://nadie:nada@127.0.0.1:1/inexistente` el `LifespanManager` arranca y apaga sin error (el arranque no conecta); sin `DATABASE_URL`, entrar al `LifespanManager` lanza `ConfiguracionInvalida`.
- [x] 3.5 RED → GREEN apagado: `test_lifespan_al_apagar_cierra_el_motor_y_sus_conexiones` — dentro del lifespan registrar `event.listen(engine.sync_engine, "engine_disposed", ...)`, abrir y devolver una conexión real (`async with engine.connect()` + `SELECT 1`), guardar `pool = engine.pool` y verificar `pool.checkedin() == 1`; al salir, el evento se disparó una vez y `pool.checkedin() == 0`. Si estuviera en verde de entrada, comprobar que falla quitando temporalmente el `dispose` (el test no es tautológico) y restaurarlo.
- [x] 3.6 REFACTOR: `database.py` sin estado global, type hints (`AsyncIterator[None]`, `async_sessionmaker[AsyncSession]`); suite en verde.

## 4. Una sesión por petición — `get_session` y `SessionDep`, tests en `tests/test_sesion.py` (integracion)

- [x] 4.1 RED: fixture local que arma `crear_app()`, le agrega una ruta sonda `async def` (recibe `SessionDep` y una dependencia que también pide `SessionDep`, guarda las sesiones en una lista, ejecuta `SELECT 1` y responde si ambas referencias son la misma) y la levanta con `LifespanManager` (D-13.6); `test_get_session_dos_peticiones_reciben_sesiones_distintas` → rojo (no existen `get_session` / `SessionDep`).
- [x] 4.2 GREEN: `async def get_session(request: Request) -> AsyncIterator[AsyncSession]` con `async with request.app.state.session_factory() as session: yield session` y `SessionDep = Annotated[AsyncSession, Depends(get_session)]`; ejecutar → verde.
- [x] 4.3 TRIANGULAR: dentro de una petición ambas referencias son la misma (`is`); la sesión tiene `sync_session.expire_on_commit is False` y es instancia de `sqlmodel.ext.asyncio.session.AsyncSession`; después de la respuesta `app.state.engine.pool.checkedout() == 0`.
- [x] 4.4 REFACTOR: nombres y type hints; suite en verde.

## 5. `GET /health/live` — `app/modules/health/{schemas,router}.py`, tests en `tests/test_health.py`

- [x] 5.1 RED: `test_live_responde_200_estado_vivo` con `client` → espera 200 `{"estado": "vivo"}`; ejecutar → rojo (404, no hay router).
- [x] 5.2 GREEN: `models.py` con sólo un docstring ("el módulo health no tiene tablas", D-8); `schemas.py` con `EstadoSalud(SQLModel)` (`estado: str`); `router.py` con `APIRouter(prefix="/health", tags=["health"])` y `async def live() -> EstadoSalud` sin dependencias (D-8, D-11); `include_router` en `crear_app()`; ejecutar → verde.
- [x] 5.3 TRIANGULAR: con la app levantada hacia `127.0.0.1:1`, `GET /health/live` → 200 `{"estado": "vivo"}` en menos de 1 s (`time.perf_counter()`); con la app de test recién arrancada, después de `GET /health/live` el pool tiene `checkedin() == 0` y `checkedout() == 0`.
- [x] 5.4 REFACTOR; suite en verde.

## 6. `GET /health/ready` — `app/modules/health/service.py` + router, tests en `tests/test_health.py`

- [x] 6.1 RED: `test_ready_con_base_disponible_responde_200_listo` → rojo (404).
- [x] 6.2 GREEN: `service.base_disponible(session)` que ejecuta `await session.exec(text("SELECT 1"))` y devuelve `scalar_one() == 1`; handler `async def ready(session: SessionDep, response: Response) -> EstadoSalud` que devuelve `{"estado": "listo"}`; ejecutar → verde.
- [x] 6.3 RED: `test_ready_sin_base_responde_503_sin_base` con la app hacia `127.0.0.1:1` → rojo (hoy sale 500 / excepción).
- [x] 6.4 GREEN: `TIMEOUT_READY_SEGUNDOS = 2.0`, `async with asyncio.timeout(TIMEOUT_READY_SEGUNDOS)` alrededor de la consulta, `except Exception` → `logger.warning` sólo con el tipo de excepción → `False`; en el router `response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE` y `{"estado": "sin base"}` (D-9, D-10); ejecutar → verde.
- [x] 6.5 TRIANGULAR (parametrize con `monkeypatch.setattr(service, "TIMEOUT_READY_SEGUNDOS", 0.5)`): nada escucha (`127.0.0.1:1`), servidor mudo (fixture `servidor_mudo` con `asyncio.start_server` que lee hasta EOF y nunca escribe, cerrando los writers antes de `wait_closed`) y base inexistente en el servidor de test (`make_url(TEST_DATABASE_URL).set(database="base_inexistente_test")`) → 503 con cuerpo exactamente `{"estado": "sin base"}` en menos de `0.5 + 1` s.
- [x] 6.6 TRIANGULAR: tras un 503, `GET /health/live` → 200 y otro `GET /health/ready` → 503 (la app sigue atendiendo); con la base de test, dos `GET /health/ready` → 200/200 y `checkedout() == 0` tras cada uno; contraste del pool: tras `GET /health/ready` `checkedin() == 1` (complementa 5.3).
- [x] 6.7 TRIANGULAR contrato: `GET /openapi.json` declara `200` y `503` en `/health/ready` y `200` en `/health/live`; agregar `response_model=EstadoSalud` y `responses={503: {"model": EstadoSalud, "description": "La base no contesta"}}` hasta que pase.
- [x] 6.8 REFACTOR: router delgado (sólo elige el código y delega en el service), todo `async def`, type hints, `logger = logging.getLogger(__name__)`; suite completa en verde.

## 7. Higiene del repositorio — `tests/test_repositorio.py` (sin base, tests `def`)

- [x] 7.1 Escribir `test_env_example_declara_todas_las_variables` (las siete de la spec) y `test_env_example_urls_tienen_la_forma_con_placeholders` (`postgresql+asyncpg://<usuario>:<clave>@localhost:<puerto>/<base>`); como `env.example` ya existe (0.3), probar que no son tautológicos rompiendo temporalmente una copia (p. ej. parametrizar la función de lectura con `tmp_path`) y viendo el rojo, luego verde contra el archivo real.
- [x] 7.2 `test_clave_real_no_aparece_en_archivos_versionados`: si `POSTGRES_PASSWORD` está en el entorno, su valor no aparece en `env.example` ni en `docker-compose.yml`, y `docker-compose.yml` usa `${POSTGRES_USER:?` y `${POSTGRES_PASSWORD:?` (sin default); `pytest.skip` si la variable no está.
- [x] 7.3 `test_env_no_se_versiona`: `subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=RAIZ)` devuelve 0; `pytest.skip` si git no está instalado.

## 8. Entregable de la cátedra — `test/health.http`

- [x] 8.1 Crear `test/health.http` con `@base = http://localhost:8000` y tres bloques `###`, cada uno con `# Esperado: ...`: `GET {{base}}/health/live` → 200 `{"estado": "vivo"}`; `GET {{base}}/health/ready` con la base levantada → 200 `{"estado": "listo"}`; `GET {{base}}/health/ready` tras `docker compose stop db` → 503 `{"estado": "sin base"}` en menos de ~2 s.
- [x] 8.2 Ejecutarlo a mano contra `uvicorn app.main:app` (REST Client de VS Code o HTTP Client de JetBrains), incluida la parada y vuelta (`docker compose stop db` / `docker compose start db`), y confirmar que las respuestas coinciden con los comentarios.

## 9. `README.md` (esqueleto)

- [x] 9.1 Escribir `README.md` con: requisitos (Python 3.12–3.14, Docker); pasos desde cero (venv con activación en PowerShell y bash, `pip install -r requirements-dev.txt`, copiar `env.example` a `.env` y completarlo, `docker compose up -d`, `python reiniciar.py` marcado "disponible desde C-02 `modelos-esquema-seed`", `uvicorn app.main:app --reload` o `fastapi dev app/main.py`, `pytest`); tabla de variables de entorno; diferencia `tests/` vs `test/`; puerto 5433 y cómo cambiarlo; base de test con un volumen preexistente (D-1); evidencia con `SQL_ECHO=1`; secciones con encabezado propio "Índice de `turno_practica.turno_id`" (se completa en C-02) y "Evidencia del caso C-07" (se completa en C-06).

## 10. Verificación final

- [x] 10.1 `pytest` completo en verde (anotar cantidad de tests y tiempo); `pytest -m "not integracion"` también en verde con el contenedor detenido.
- [x] 10.2 `uvicorn app.main:app` arranca; `GET /health/live` → 200 `{"estado": "vivo"}`; `GET /health/ready` → 200 `{"estado": "listo"}`; con `SQL_ECHO=1` la consola muestra el `SELECT 1`; sin `DATABASE_URL` el arranque falla con el mensaje de `ConfiguracionInvalida` (sin mostrar la clave).
- [x] 10.3 `git check-ignore .env` imprime `.env`; `git status` no lista `.env`; `grep -rn "TODO" app/ tests/` sin resultados; ningún handler definido con `def` (todos `async def`).
- [x] 10.4 Actualizar la KB con lo decidido: en `knowledge-base/10_preguntas_abiertas.md` marcar PA-04, PA-06 y PA-08 como resueltas (remitiendo a este `design.md`); en `knowledge-base/08_arquitectura_propuesta.md` actualizar la tabla de variables (puerto 5433 en los ejemplos, `POSTGRES_*`, `SQL_ECHO` confirmada) y agregar `docker/initdb/` y `pytest.ini` a la estructura.
- [x] 10.5 Dejar los cambios listos para commit con Conventional Commits y sin líneas de co-autor de IA (regla dura 12); no hacer `push` sin confirmación de Matheo.
