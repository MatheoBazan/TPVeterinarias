> **Governance BAJO**: catálogo con dos endpoints que replican el patrón de C-03; autonomía completa si los tests pasan. Las decisiones del `design.md` no requieren aprobación previa.
>
> **TDD estricto** (contra PostgreSQL real `veterinaria_test`, nunca SQLite ni mocks de la sesión): cada grupo sigue RED → GREEN → TRIANGULATE → REFACTOR y se ejecuta `pytest` en cada paso. Si un test pasa de entrada porque el código de un grupo anterior (o FastAPI/Pydantic) ya cubre la propiedad, comprobar que falla rompiendo temporalmente esa propiedad (mutación) y registrarlo en la evidencia TDD. Los módulos de test nuevos declaran `pytestmark = pytest.mark.integracion` y usan `base_con_seed` + `client` (seed de C-02: prácticas 1 Consulta 15000.00, 2 Desparasitación 8000.00, 3 Vacuna antirrábica 12000.00, 4 Vacuna quíntuple 14000.00).
>
> **Entregable en `test/`**: `test/practicas.http` (grupo 5) con el caso C-02 (nombre de práctica repetido) y las notas de ejecución del caso C-08.

## 0. Entorno y línea base

- [x] 0.1 Verificar que C-03 `duenios-fichas` está archivado (`openspec list --json` sin él; existe `openspec/changes/archive/2026-11-05-duenios-fichas/`) y que existen `app/core/errores.py` (`Rechazo`, `traducir_rechazo`, `MensajeError`), las fixtures `base_con_seed`, `esquema_vacio`, `sesion`, `sentencias_app` y el helper `bloques_http`
- [x] 0.2 `docker compose up -d --wait`; la base `veterinaria_test` responde; `pip check` sin errores
- [x] 0.3 Safety net: `pytest` completo en verde; anotar la línea base "N tests passing" (se modificará `app/main.py`)

## 1. Listado del catálogo (`GET /practicas/`, D-7, D-8)

- [x] 1.1 RED: `tests/test_practicas.py::test_listar_practicas_responde_el_catalogo_inicial` (`GET /practicas/` → 200 con el cuerpo exacto del escenario "Catálogo inicial", precios como string `"15000.00"`, etc.) → falla con 404 (la ruta no existe)
- [x] 1.2 GREEN: `app/modules/practicas/schemas.py` con `PracticaRead` (`id: int`, `nombre: str`, `precio: Decimal`; D-1); `app/modules/practicas/service.py` con `listar_practicas(session)` (`select(Practica).order_by(Practica.id)`, devuelve `list[PracticaRead]`); `app/modules/practicas/router.py` con `APIRouter(prefix="/practicas", tags=["practicas"])` y `GET /` de una línea que llama `service.listar_practicas` por el módulo; `include_router(practicas_router)` en `crear_app()` → verde
- [x] 1.3 TRIANGULATE: `test_listar_practicas_con_catalogo_vacio_responde_lista_vacia` (con `esquema_vacio` → 200 `[]`); `test_listar_practicas_ordena_por_id` (insertar con `sesion` dos prácticas cuyo orden alfabético es inverso al de `id`, p. ej. "Zeta" y luego "Alfa" → aparecen en orden de `id`)
- [x] 1.4 RED/GREEN: `test_listar_practicas_usa_una_sola_consulta` parametrizado por catálogo de 4 y de 6 prácticas (las 2 extra insertadas con `sesion`): tras `sentencias_app.clear()`, exactamente 1 sentencia, un `SELECT` sobre `practica` → pasa de entrada por 1.2: mutación agregando temporalmente una segunda consulta en el service (p. ej. un `select(func.count())`) → rojo, y registrarla
- [x] 1.5 REFACTOR: anotaciones de tipo y nombres según D-7/D-8; `status_code=200` y `response_model=list[PracticaRead]` explícitos en la ruta; tests en verde

## 2. Alta válida y formato del dinero (`POST /practicas/`, D-1, D-2, D-6)

- [x] 2.1 RED: `test_crear_practica_valida_responde_201` (`{"nombre": "Castración", "precio": "30000.00"}` → 201 `{"id": 5, "nombre": "Castración", "precio": "30000.00"}` exacto; `GET /practicas/` la incluye como último elemento) → falla con 405
- [x] 2.2 GREEN: `PracticaCreate` con `model_config = ENTRADA` (redefinida en `practicas/schemas.py`, D-4), `nombre: str = Field(min_length=1)`, `precio: Decimal = Field(gt=0, max_digits=10, decimal_places=2)`; `service.crear_practica` (`Practica.model_validate(datos)`, `add`, `commit`, `PracticaRead.model_validate`); ruta `POST /` con `status_code=201` y `response_model=PracticaRead` → verde
- [x] 2.3 RED: `test_crear_practica_devuelve_el_precio_con_dos_decimales` parametrizado (`9000` número JSON → `"9000.00"`; `"4500.5"` → `"4500.50"`; comparando el string crudo de `r.json()["precio"]` y el mismo string en `GET /practicas/`) → falla: el 201 devuelve `"9000"` / `"4500.5"` (verificado, punto 4 del design)
- [x] 2.4 GREEN: `field_validator("precio")` en `PracticaCreate` que devuelve `valor.quantize(Decimal("0.01"))` (D-2) → verde
- [x] 2.5 TRIANGULATE: `test_crear_practica_guarda_el_nombre_sin_espacios` (`"  Ecografía  "` → 201 `"nombre": "Ecografía"`); `"1e2"` → `"100.00"` agregado al parametrizado de 2.3
- [x] 2.6 REFACTOR: tests en verde

## 3. Contrato de entrada: 422 (RN-04, D-1, D-2)

- [x] 3.1 RED/GREEN: `test_crear_practica_con_precio_no_positivo_responde_422` parametrizado (`"0"`, `"-100.00"`): 422, error en `["body", "precio"]` con `type == "greater_than"` y `practica` sigue con 4 filas → pasa de entrada por 2.2: mutación quitando temporalmente `gt=0` (el `"0"` llega a la base, el CHECK lo rechaza y responde el 409 genérico → rojo), y registrarla
- [x] 3.2 RED/GREEN: `test_crear_practica_con_precio_fuera_de_numeric_10_2_responde_422` parametrizado (`"12.345"` → `decimal_max_places`; `"100000000.00"` → `decimal_whole_digits`), 4 filas → pasa de entrada por 2.2: mutación quitando `max_digits`/`decimal_places` (`"100000000.00"` termina en error del servidor por `numeric field overflow`; `"12.345"` se guarda como `12.35`) → rojo, y registrarla
- [x] 3.3 TRIANGULATE: `test_crear_practica_con_precio_no_numerico_responde_422` parametrizado (`"abc"`, `"NaN"`) → 422 con error en `["body", "precio"]`
- [x] 3.4 TRIANGULATE: `test_crear_practica_con_cuerpo_invalido_responde_422` parametrizado (`{"precio": "100.00"}` → `nombre`; `{"nombre": "Sin precio"}` → `precio`; `{"nombre": "   ", "precio": "100.00"}` → `nombre`; `{"id": 9, "nombre": "Con id", "precio": "100.00"}` → `id` con `type == "extra_forbidden"`): 422 con el `loc` del campo culpable y 4 filas
- [x] 3.5 REFACTOR: tests en verde

## 4. Nombre único sin consulta previa (RN-02, caso C-02, D-3, D-5, D-6)

- [x] 4.1 RED: caso C-02 `test_crear_practica_con_nombre_repetido_responde_409` (`{"nombre": "Consulta", "precio": "20000.00"}` → 409 `{"detail": "Ya existe una práctica con ese nombre"}` exacto; 4 filas; la práctica 1 conserva `"15000.00"`) → falla: el `IntegrityError` se propaga
- [x] 4.2 GREEN: constante `RECHAZOS_ALTA` con sólo `uq_practica_nombre` (D-3, D-5); `try/except IntegrityError` → `await session.rollback()` → `raise traducir_rechazo(exc, RECHAZOS_ALTA) from exc` → verde
- [x] 4.3 TRIANGULATE: `"  Vacuna antirrábica "` → 409 (choca tras quitar espacios); `test_despues_de_un_409_la_siguiente_alta_funciona` (409 con `Consulta` y luego 201 con `Castración`, `id > 4`); el cuerpo del 409 no contiene `uq_practica_nombre`, `duplicate key`, `INSERT` ni `asyncpg`
- [x] 4.4 RED/GREEN: `test_alta_repetida_no_consulta_antes_de_escribir` (con `sentencias_app`: tras `.clear()`, el `POST` repetido envía exactamente 1 sentencia y empieza con `INSERT INTO practica`) → pasa de entrada por 4.2: mutación agregando temporalmente un `SELECT` por nombre antes del `INSERT` → rojo, y registrarla
- [x] 4.5 RED/GREEN: `test_openapi_declara_los_codigos_de_practicas` (lee `/openapi.json`: `POST /practicas/` → 201, 409, 422 con el 409 referenciando `MensajeError`; `GET /practicas/` → 200) → completar `responses={409: {"model": MensajeError, ...}}` en la ruta si falta; `test_handlers_de_practicas_son_async` (`inspect.iscoroutinefunction(route.endpoint)` en todas las rutas del router)
- [x] 4.6 REFACTOR: revisar que cada handler es una sola línea `return await service.<funcion>(...)`, sin `if` ni queries en `router.py`; tests en verde

## 5. Casos `.http` (`test/practicas.http`, casos C-02 y C-08, D-10)

- [x] 5.1 RED: `tests/test_practicas_http.py::test_practicas_http_documenta_los_casos_de_la_consigna` (el archivo existe; contiene los rótulos "Caso C-02" y "Caso C-08" y la referencia a `test/c08_check_precio.sql`; cada bloque `###` tiene `# Esperado:`; no contiene la clave real de la base) → falla porque el archivo no existe
- [x] 5.2 GREEN: escribir `test/practicas.http` con el aviso inicial (correr una vez y en orden después de `python reiniciar.py`; marcas **[modifica]**; los 409 consumen un id), las notas de ejecución del caso C-08 (comandos `docker compose cp` / `docker compose exec db psql -U <usuario> ...`, sin credenciales) y las 10 peticiones de D-10 en ese orden, cada una con su `# Esperado:` → verde
- [x] 5.3 TRIANGULATE: `test_practicas_http_corre_en_orden_con_los_codigos_esperados` (con `base_con_seed` y `bloques_http`: 10 bloques, cada uno enviado con `client` reemplazando `{{base}}`, código de estado igual al del comentario)
- [x] 5.4 REFACTOR: tests en verde

## 6. Verificación final

- [x] 6.1 `pytest` completo en verde: línea base de 0.3 + los tests nuevos, sin tests omitidos por falta de base
- [x] 6.2 Manual: `python reiniciar.py` sobre la base de desarrollo, `uvicorn app.main:app`, ejecutar cada petición de `test/practicas.http` en orden con `curl` y comparar código y cuerpo con su comentario; correr `test/c08_check_precio.sql` según sus notas y comprobar el error `ck_practica_precio_positivo` y el bloque 10; registrar la salida en el resumen del `apply` (verificado de forma equivalente con pytest+httpx: test_practicas_http corre las 10 peticiones; C-08 por tests/test_reiniciar.py; no se corrió curl/psql real)
- [x] 6.3 Revisión contra las reglas duras: handlers `async def`; ninguna consulta "¿ya existe?" antes del `INSERT`; el router no devuelve el modelo de tabla; `extra="forbid"` en `PracticaCreate`; `precio` nunca `float` en el código; `app/modules/practicas/models.py`, `reiniciar.py`, `app/core/errores.py` y `app/modules/laboratorio/cliente.py` sin tocar; sin `session.execute` ni `TODO`
- [x] 6.4 `openspec validate practicas-catalogo --strict` sin errores; completar la tabla "TDD Cycle Evidence" en el resumen del `apply`

## Workflow follow-up

- Archivar el change (`/opsx:archive practicas-catalogo`) con pytest en verde y `test/practicas.http` escrito, y marcar C-05 como hecho en `CHANGES.md`.
- Avisar a quien tome C-06: el precio del catálogo se lee como `Decimal` con escala 2 (`NUMERIC(10,2)`), y el formato de dinero en las respuestas es string con 2 decimales.
