## Context

Motivación y alcance en `proposal.md`; comportamiento exigido en `specs/catalogo-de-practicas/spec.md`.

Estado de partida (leído en disco al escribir este design):

- **C-02 archivado**: `app/modules/practicas/models.py` define `Practica` (`id`, `nombre: str`, `precio: Decimal` con `Numeric(10, 2)`) con `UniqueConstraint("nombre", name="uq_practica_nombre")` y `CheckConstraint("precio > 0", name="ck_practica_precio_positivo")`, y la relación `turnos` (`passive_deletes="all"`). `reiniciar.py` carga 4 prácticas: 1 Consulta 15000.00, 2 Desparasitación 8000.00, 3 Vacuna antirrábica 12000.00, 4 Vacuna quíntuple 14000.00. `test/c08_check_precio.sql` ya existe con sus notas de ejecución y lo prueba `tests/test_reiniciar.py` (SQLSTATE `23514`, `ck_practica_precio_positivo`, precio intacto).
- **C-03 archivado** (`openspec/changes/archive/2026-11-05-duenios-fichas/`), patrón de referencia: `app/core/errores.py` (`Rechazo`, `traducir_rechazo` por `constraint_name`, `MensajeError`, 409 genérico `RECHAZO_GENERICO` + `logger.warning` para lo no previsto), `app/modules/duenios/{schemas,service,router}.py` (router de una línea por ruta que llama `service.<funcion>`; service que escribe, atrapa `IntegrityError`, hace `rollback` y lanza la `HTTPException` traducida; devuelve DTO con `XRead.model_validate(obj)`), `ENTRADA = ConfigDict(extra="forbid", str_strip_whitespace=True)` definido en `duenios/schemas.py`. Tests: fixtures `app`, `client`, `esquema_vacio`, `base_con_seed`, `sesion`, `sentencias_app` (en `tests/conftest.py`) y `bloques_http` (en `tests/soporte.py`), que ejecuta en orden los bloques `###` de un `.http` y compara el primer código de `# Esperado:`.
- **Versiones instaladas** (`.venv`, Python 3.13): `fastapi==0.162.0`, `pydantic==2.14.3`, `sqlmodel==0.0.48`.

**Verificado antes de decidir** (prototipo en el venv, sin tocar el repo, con `precio: Decimal = Field(gt=0, max_digits=10, decimal_places=2)`):

1. `"0"` y `-1` → `greater_than`; `"0.001"` y `"12.345"` → `decimal_max_places`; `"100000000.00"` → `decimal_whole_digits`; `"NaN"` e `"Infinity"` → `finite_number`; `true` y `null` → `decimal_type`; `"99999999.99"` aceptado.
2. Pydantic conserva la escala recibida: `15000` → `Decimal('15000')`, `"12.10"` → `Decimal('12.10')`, `"1e2"` → `Decimal('1E+2')`, `"12.100"` aceptado (los ceros finales no cuentan como decimales) → `Decimal('12.100')`. En JSON, `Decimal('15000.00')` se serializa `"15000.00"` pero `Decimal('15000')` se serializa `"15000"`.
3. Con un `field_validator("precio")` (modo `after`) que hace `valor.quantize(Decimal("0.01"))`: `15000` → `15000.00`, `"1e2"` → `100.00`, `"12.100"` → `12.10`, `0.1` (número JSON) → `0.10`, `15000.5` → `15000.50`. Como `decimal_places=2` ya rechazó lo que tiene más de 2 decimales significativos, el `quantize` nunca redondea: sólo fija la escala.
4. Después del `INSERT`, SQLAlchemy sólo trae del servidor el `id` (por `RETURNING`); el resto de los atributos queda con el valor de Python que se envió y, con `expire_on_commit=False`, no se recarga. Por eso, sin el punto 3, `POST` con `15000` respondería `"15000"` mientras `GET` (que lee `NUMERIC(10,2)`) respondería `"15000.00"`.

Restricciones que condicionan el diseño: reglas duras 1 (esquema intocable), 2 (async), 3 (la base es el garante, sin pre-chequeos; nunca `float` para dinero), 5 (router delgado), 6 (DTO separados), 7 (`extra="forbid"`), 9 (PostgreSQL real) y 10 (tests + `.http`) de `AGENTS.md`.

## Goals / Non-Goals

**Goals:**
- Replicar el patrón de C-03 sin modificar su código: el módulo `practicas` sólo agrega archivos y una línea en `app/main.py`.
- Que el contrato del dinero sea el mismo en el alta y en el listado (string con 2 decimales) y que ningún precio que la base no pueda guardar llegue a la base (todo se corta con 422 en el DTO).
- Que RN-02 se demuestre mirando las sentencias SQL: el 409 sale de un único `INSERT`.
- Que `test/practicas.http` corra de arriba abajo después de `python reiniciar.py` y que un test lo ejecute.

**Non-Goals:**
- `GET /practicas/{id}`, `PATCH` o `DELETE` de prácticas: la consigna no los define (filas 12 y 13 de la tabla de endpoints).
- Paginación o filtros del catálogo (el envoltorio de paginación es de `GET /mascotas/`, C-04).
- Unicidad del nombre insensible a mayúsculas o acentos (la consigna sólo pide UNIQUE; ver Riesgos).
- Mover `ENTRADA` u otra pieza de C-03 a `app/core/` (Decisión 4).

## Decisions

### Decisión 1 — DTO de `practicas` (`app/modules/practicas/schemas.py`)
| DTO | Campos | Configuración |
|-----|--------|---------------|
| `PracticaCreate` | `nombre: str = Field(min_length=1)`, `precio: Decimal = Field(gt=0, max_digits=10, decimal_places=2)` + `field_validator("precio")` que fija la escala a 2 decimales | `ENTRADA` = `ConfigDict(extra="forbid", str_strip_whitespace=True)` |
| `PracticaRead` | `id: int`, `nombre: str`, `precio: Decimal` | salida (sin `extra="forbid"`) |

- Heredan de `SQLModel` sin `table=True`, igual que los DTO de C-03; no comparten clase base con `Practica`.
- **Sin `id`** en el alta (Ej. 2); con `extra="forbid"`, mandarlo responde 422 `extra_forbidden`.
- **`nombre` con `str_strip_whitespace` + `min_length=1`** (mismo criterio que `DuenioCreate`, D-12 de C-03): `"   "` → 422; `"  Ecografía  "` se guarda `"Ecografía"`, y `" Consulta "` choca con `Consulta` (409). Sin largo máximo: la columna es `VARCHAR` sin largo (C-02) y nada lo pide.
- **`PracticaRead.precio: Decimal`**: FastAPI/Pydantic lo serializa como string JSON (verificado, punto 2), que es el formato de dinero de la KB (09 §formato: `"27000.00"`). No se agrega un serializador propio: la escala la garantizan la Decisión 2 (alta) y `NUMERIC(10,2)` (lecturas).

**Alternativas**: un único DTO `Practica` reutilizado como entrada y salida (contradice la regla dura 6; descartada); `precio: float` o `condecimal` con `float` en el JSON Schema (regla dura 3; descartada); `PracticaRead` con `PlainSerializer` que formatee a 2 decimales (arregla la salida pero deja guardar en memoria un valor con otra escala que el de la base, y es un segundo mecanismo para lo mismo; descartada).

### Decisión 2 — Validación del precio en el DTO: `gt=0`, `max_digits=10`, `decimal_places=2` y escala fija
- **`gt=0`** es la mitad de RN-04 que le toca al contrato ("Garante: CHECK en la base **y** validación del DTO", KB 05): `0` y negativos → **422** `greater_than` sin llegar a la base.
- **`max_digits=10, decimal_places=2`** reproduce `NUMERIC(10,2)` en el contrato. Sin esto, `"100000000.00"` llega a la base y PostgreSQL lo rechaza con `numeric field overflow` (`22003`, un `DataError`, no un `IntegrityError`), que el service no traduce → **500**; y `"12.345"` se guardaría redondeado a `12.35` sin avisar. Con las cotas, los dos son **422** con un error en `["body", "precio"]` (verificado, punto 1).
- **Escala fija a 2 decimales** con `field_validator("precio")` → `valor.quantize(Decimal("0.01"))` después de las cotas: el valor que se guarda y se devuelve en el `201` es el mismo que devuelve después el `GET` (`"9000.00"` y no `"9000"`; verificado, puntos 3 y 4). El `quantize` no redondea nunca porque `decimal_places=2` ya rechazó lo que no entra.
- `NaN`, `Infinity`, `true`, `null` y textos no numéricos → 422 por la validación de `Decimal` de Pydantic (punto 1). Se aceptan string (`"30000.00"`, recomendado en el `.http`) y número JSON (`9000`): Pydantic convierte el número a `Decimal` sin pasar por aritmética de `float`.

**Alternativas**: sólo `gt=0` (deja el 500 por desborde y el redondeo silencioso; descartada); `strict=True` para aceptar sólo strings (más estricto que lo que pide la consigna y rompe a un cliente que manda `9000`; descartada); `session.refresh(practica)` después del `commit` para leer el valor normalizado por la base (una sentencia `SELECT` más por alta sólo para formatear; descartada).

### Decisión 3 — El CHECK de precio no se declara en el mapa de rechazos
`RECHAZOS_ALTA` declara sólo `uq_practica_nombre`. `ck_practica_precio_positivo` es inalcanzable desde la API (el DTO corta antes con 422, Decisión 2); si algún día se alcanzara (por un defecto en el DTO), `traducir_rechazo` ya responde el 409 genérico de C-03 (D-2) y deja un `logger.warning` con la restricción y el SQLSTATE: el defecto queda visible sin un mensaje inventado para un camino que no existe.

**Alternativas**: declararlo como `Rechazo(422, "El precio debe ser mayor que cero")` (un 422 que no sale de la validación de FastAPI mezclaría dos formatos de `detail` para el mismo código y exige un test que saltee el DTO con `model_construct`; código defensivo sin camino real; descartada); declararlo como 409 con mensaje propio (esconde el defecto que el `warning` hace visible; descartada).

### Decisión 4 — `ENTRADA` se redefine en `practicas/schemas.py`, no se importa de `duenios` ni se mueve a `app/core`
`ENTRADA = ConfigDict(extra="forbid", str_strip_whitespace=True)` se declara también en `app/modules/practicas/schemas.py` (una línea).
- Importarla de `app.modules.duenios.schemas` acopla el catálogo al módulo de dueños sin relación de dominio.
- Moverla a `app/core/` modifica código de un change archivado (C-03) para ahorrar una línea, y obliga a tocar sus imports; es un refactor que puede hacer C-08 si C-04 y C-06 repiten la línea.
- Tener `extra="forbid"` escrito en cada `schemas.py` deja la regla dura 7 a la vista de quien corrige el módulo.

**Alternativas**: las dos primeras viñetas (descartadas por lo dicho).

### Decisión 5 — Mensaje propio y mapa de rechazos
| Situación | Código | `detail` |
|-----------|--------|----------|
| Nombre repetido (`uq_practica_nombre`) — RN-02, caso C-02 | 409 | `Ya existe una práctica con ese nombre` |

```python
RECHAZOS_ALTA: Final[Mapping[str, Rechazo]] = {
    "uq_practica_nombre": Rechazo(status.HTTP_409_CONFLICT, "Ya existe una práctica con ese nombre"),
}
```
Mensaje fijo, sin el nombre enviado ni SQL (spec `contrato-de-errores`); constante en `app/modules/practicas/service.py`, reutilizada por los tests y el `.http`.

### Decisión 6 — Alta: un `INSERT` y la base decide el 409
```python
async def crear_practica(session: AsyncSession, datos: PracticaCreate) -> PracticaRead:
    practica = Practica.model_validate(datos)
    session.add(practica)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_ALTA) from exc
    return PracticaRead.model_validate(practica)
```
Idéntico a `crear_duenio` (D-1 de C-03): una sentencia `INSERT INTO practica ... RETURNING practica.id`, sin `SELECT` previo. El rechazo consume igual un valor de la secuencia (D-16 de C-03), y el `.http` lo refleja.

### Decisión 7 — Listado: una consulta ordenada por `id`, sin relaciones
```python
async def listar_practicas(session: AsyncSession) -> list[PracticaRead]:
    practicas = (await session.exec(select(Practica).order_by(Practica.id))).all()
    return [PracticaRead.model_validate(p) for p in practicas]
```
- **Orden por `id`** en la base (`ORDER BY practica.id`): estable, coincide con el orden del seed y con el criterio que C-03 (D-10) y C-04 (PA-12) usan para listas; el último alta aparece al final.
- **Una sola sentencia** con cualquier tamaño de catálogo: `PracticaRead` no incluye la relación `turnos`, así que no hay nada que precargar ni riesgo de carga perezosa (`MissingGreenlet`). Lo prueba `sentencias_app`.
- Sin `commit`: es una lectura (D-16 de C-03).

**Alternativas**: orden por `nombre` (más cómodo para leer, pero el orden del catálogo no es un requisito de la consigna y por `id` es el mismo criterio de todo el TP; descartada); sin `ORDER BY` (PostgreSQL no garantiza orden y los tests de cuerpo exacto serían frágiles; descartada).

### Decisión 8 — Router delgado (`app/modules/practicas/router.py`) y registro
- `router = APIRouter(prefix="/practicas", tags=["practicas"])`; las dos rutas son `"/"` (las URL exactas de la consigna, con barra final).
- `POST`: `status_code=201`, `response_model=PracticaRead`, `responses={409: {"model": MensajeError, "description": "Ya existe una práctica con ese nombre"}}`; cuerpo `return await service.crear_practica(session, datos)`.
- `GET`: `status_code=200`, `response_model=list[PracticaRead]`; cuerpo `return await service.listar_practicas(session)`.
- `from app.modules.practicas import service` (llamadas por el módulo, igual que `duenios` y `health`).
- `app/main.py`: `aplicacion.include_router(practicas_router)` después de `duenios_router` en `crear_app()`. `Practica` ya está registrada por `app.core.modelos`.

### Decisión 9 — Tests: archivos y cómo se prueba cada propiedad
Todos con `pytestmark = pytest.mark.integracion`, contra `veterinaria_test` (`base_con_seed` o `esquema_vacio`) con `client`; nunca mocks de la sesión ni de la base.
- **`tests/test_practicas.py`** — un test por escenario de la spec, parametrizando cuerpos inválidos (≥2 casos por comportamiento: precio `0` y `-100.00`; `12.345` y `100000000.00`; `abc` y `NaN`; faltantes, nombre vacío e `id`). Las comprobaciones de "no se escribió nada" usan `GET /practicas/` (4 elementos) o una consulta con `sesion`. El formato del dinero se comprueba comparando el JSON crudo (`r.json()["precio"] == "9000.00"`, string).
- **Sin pre-chequeos y número de consultas** (mismo archivo, con `sentencias_app`): `POST` repetido → una sola sentencia y empieza con `INSERT INTO practica`; `GET /practicas/` con 4 y con 6 prácticas → una sola sentencia `SELECT` en cada caso.
- **`tests/test_practicas_http.py`** — igual que `test_duenios_http.py`: el archivo existe, contiene `Caso C-02` y `Caso C-08`, cada bloque `###` tiene `# Esperado:`, y se ejecuta en orden con `bloques_http` sobre `base_con_seed` comparando el código de estado y la cantidad de bloques.
- El rechazo del CHECK por SQL directo (caso C-08) ya lo prueba `tests/test_reiniciar.py` (C-02); no se duplica.

### Decisión 10 — `test/practicas.http`: casos en orden, después de `python reiniciar.py`
Mismo formato que `test/duenios.http`. El comentario inicial indica: correr en orden y una sola vez después de `python reiniciar.py`; las peticiones **[modifica]** cambian el estado; los `POST` rechazados (409) consumen un id. Incluye además las **notas del caso C-08**: correr `test/c08_check_precio.sql` con los comandos `docker compose cp` / `docker compose exec ... psql` que ya documenta ese archivo (sin credenciales: `<usuario>` es `POSTGRES_USER` del `.env`), y luego el bloque de verificación por HTTP.

| # | Petición | Esperado (comentario) |
|---|----------|-----------------------|
| 1 | `GET /practicas/` | 200 con las 4 prácticas del seed, precios `"15000.00"`, `"8000.00"`, `"12000.00"`, `"14000.00"` |
| 2 | **[modifica]** `POST /practicas/` `{"nombre": "Castración", "precio": "30000.00"}` | 201 `{"id": 5, "nombre": "Castración", "precio": "30000.00"}` |
| 3 | **Caso C-02** `POST /practicas/` `{"nombre": "Consulta", "precio": "20000.00"}` | 409 `{"detail": "Ya existe una práctica con ese nombre"}` (consume el id 6) |
| 4 | `POST /practicas/` `{"nombre": "Gratis", "precio": "0"}` | 422 `greater_than` en `["body", "precio"]` (RN-04) |
| 5 | `POST /practicas/` `{"nombre": "Negativa", "precio": "-100.00"}` | 422 `greater_than` en `["body", "precio"]` (RN-04) |
| 6 | `POST /practicas/` `{"nombre": "Fracción", "precio": "12.345"}` | 422 en `["body", "precio"]` (más de 2 decimales) |
| 7 | `POST /practicas/` `{"id": 9, "nombre": "Con id", "precio": "100.00"}` | 422 `extra_forbidden` en `["body", "id"]` |
| 8 | **[modifica]** `POST /practicas/` `{"nombre": "Control", "precio": 9000}` | 201 `{"id": 7, "nombre": "Control", "precio": "9000.00"}` (número JSON, devuelto como string con 2 decimales) |
| 9 | `GET /practicas/` | 200 con 6 prácticas: las 4 del seed, Castración (5) y Control (7) |
| 10 | **Caso C-08 (verificación)** `GET /practicas/` — después de correr `test/c08_check_precio.sql` | 200; la práctica 1 Consulta sigue en `"15000.00"` (el CHECK rechazó el `UPDATE`) |

## Risks / Trade-offs

- [Unicidad sensible a mayúsculas y acentos: `consulta` y `Consulta` son prácticas distintas para el UNIQUE] → es lo que garantiza la restricción de C-02 y lo único que pide RN-02; normalizar (índice sobre `lower(nombre)`) cambiaría el esquema de otro change. Queda documentado en la spec ("sensible a mayúsculas").
- [Los ids del `.http` y de los tests dependen del orden: el 409 consume un valor de la secuencia (Control es 7, no 6)] → los tests arrancan siempre de `base_con_seed` y fijan los ids esperados; el `.http` lo explica en su comentario inicial (misma convención que `test/duenios.http`; PA-07 la cierra C-08).
- [El bloque 10 del `.http` no ejecuta el `.sql`: si nadie lo corre antes, la verificación pasa igual] → el `.http` sólo demuestra el resultado por HTTP; la prueba de que la base rechaza la sentencia está en `tests/test_reiniciar.py` y la evidencia para la cátedra es la salida de `psql` documentada en `test/c08_check_precio.sql`.
- [`ENTRADA` duplicada en dos (y luego cuatro) `schemas.py`] → una línea idéntica, sin lógica; si C-04/C-06 la repiten, C-08 puede consolidarla en `app/core/` (Decisión 4).
- [Un precio con más de 8 dígitos enteros o más de 2 decimales se rechaza aunque el cliente "quisiera" redondear] → preferible a guardar un valor distinto del enviado; el error de 422 dice qué campo y por qué.

## Migration Plan

Sin migración de datos: el esquema y el seed son de C-02 y no cambian. Puesta en marcha: `docker compose up -d`, `python reiniciar.py`, `uvicorn app.main:app`. Vuelta atrás: los archivos del change son nuevos salvo `app/main.py` (un import y una línea), que se revierten con git.
