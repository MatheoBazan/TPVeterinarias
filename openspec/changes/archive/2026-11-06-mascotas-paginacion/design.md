## Context

Motivación y alcance en `proposal.md`; comportamiento exigido en `specs/mascotas/spec.md`. Los contratos transversales (cuerpo de 404/409, rechazos sin consultas previas, 409 genérico, formato de los 422, id de ruta) ya están en la spec principal `contrato-de-errores` y este change los cumple sin cambiarlos.

Estado de partida (leído en disco al escribir este design):

- **C-01, C-02 y C-03 archivados** (`openspec/changes/archive/2026-11-05-*`). Patrón de referencia: `openspec/changes/archive/2026-11-05-duenios-fichas/design.md` (D-1 traducción de rechazos con mapa por operación, D-3 cuerpo `{"detail": ...}`, D-4 el service lanza `HTTPException`, D-6 404 con la misma lectura que arma la respuesta, D-13 `IdRuta`, D-14 router delgado, D-15 el service devuelve DTO, D-16 un `commit` por escritura y `rollback` ante el rechazo, D-17 tests con `sentencias_app`, D-19 `.http` ejecutado por pytest).
- **`app/modules/mascotas/models.py`** (C-02): `Mascota` (`id`, `nombre`, `especie`, `duenio_id` con `foreign_key="duenio.id"`, `ondelete="RESTRICT"`, `index=True`), relaciones `Mascota.duenio` ↔ `Duenio.mascotas` y `Mascota.turnos`. FK con nombre `mascota_duenio_id_fkey` (fijado por los tests de introspección de C-02).
- **`app/modules/mascotas/schemas.py`** (C-03, D-11): sólo `MascotaRead(SQLModel)` con `id`, `nombre`, `especie`, `duenio_id`; lo usa `GET /duenios/{id}/mascotas` (`app/modules/duenios/service.py` y `router.py` lo importan). No hay `service.py` ni `router.py` de mascotas.
- **Reutilizable sin editar**: `app/core/errores.py` (`Rechazo`, `traducir_rechazo`, `MensajeError`), `app/core/parametros.py` (`IdRuta`, `ENTERO_MAXIMO`), `app/core/database.py` (`SessionDep`), `app/modules/duenios/schemas.py` (`ENTRADA = ConfigDict(extra="forbid", str_strip_whitespace=True)`, `DuenioRead`). Tests: `tests/conftest.py` (`app`, `client`, `esquema_vacio`, `base_con_seed`, `sesion`, `sentencias_app`), `tests/soporte.py` (`bloques_http`). Seed: dueño 1 Ana Gómez (mascotas 1 Toby/perro y 2 Mishi/gato), dueño 2 Carlos Ruiz (mascota 3 Luna/perro).
- **Versiones** (`.venv`): `fastapi==0.162.0`, `sqlmodel==0.0.48`, SQLAlchemy 2.0 async, `asyncpg`, PostgreSQL 16.
- **Change en paralelo**: C-05 `practicas-catalogo` también agrega un `include_router` en `crear_app()`; ningún otro archivo en común.

**Verificado antes de decidir** (código instalado en `.venv/Lib/site-packages` y texto del PDF):

1. PDF, Ej. 2: "El listado de mascotas. Devuelve el envoltorio de la sección 2.9, `{ items, total, page, size, pages }`. `size` vale 20 por defecto y va de 1 a 100. Una página más allá de `pages` responde 422; la primera página siempre responde, aunque no haya resultados." Endpoints de referencia: `POST /mascotas/` `MascotaCreate` → `MascotaRead` (201, 409, 422); `GET /mascotas/` `page`, `size` → "Envoltorio con mascotas" (200, 422); `GET /mascotas/{id}` → "Mascota con su dueño" (200, 404). Ej. 4: "El alta de una mascota recibe el `duenio_id` de un dueño que ya existe: en la agregación viaja un id." El PDF **no fija** el valor de `pages` con `total = 0`, el orden del listado ni el cuerpo del 422 de página fuera de rango.
2. `fastapi/exception_handlers.py` (0.162): `http_exception_handler` responde `JSONResponse({"detail": exc.detail}, status_code=...)` con `detail` de cualquier tipo serializable; `request_validation_exception_handler` responde `{"detail": jsonable_encoder(exc.errors())}`. Un `HTTPException(422, detail=[{...}])` produce entonces la misma forma `{"detail": [ ... ]}` que un error de validación.
3. `sqlmodel` 0.0.48 reexporta `func` (`hasattr(sqlmodel, "func")`); `select(func.count()).select_from(Mascota)` ejecutado con `session.exec(...)` devuelve el escalar con `.one()`.
4. FastAPI resuelve y valida los parámetros de query **antes** de ejecutar el handler (D-5 punto 5 de C-03): `size=0`, `page=abc` → 422 sin sentencias SQL.
5. Pydantic 2 en modo laxo acepta `true` y `"1"` para un `int` (`TypeAdapter(int).validate_python(True) == 1`); igual que en C-03, no se endurece (ver Non-Goals).

## Goals / Non-Goals

**Goals:**
- Cumplir el contrato de paginación del PDF con reglas de borde explícitas y probadas (vacío, borde exacto, última página incompleta, fuera de rango) y un 422 de página fuera de rango con el **mismo formato** que cualquier otro 422 de FastAPI.
- Alta de mascota que copie literalmente el patrón de C-03: escribir, atrapar `IntegrityError`, `rollback`, 409 con mensaje propio; ninguna consulta "¿existe el dueño?".
- Número fijo de sentencias medido con `sentencias_app`: alta 1, detalle 1, listado 2 (1 si está fuera de rango).
- No romper `GET /duenios/{id}/mascotas`: `MascotaRead` queda idéntico.

**Non-Goals:**
- `PATCH`/`DELETE` de mascotas, filtros, orden configurable, cursores o `Link` headers (la consigna no los pide).
- Un envoltorio genérico `Pagina[T]` reutilizable por otros recursos: sólo se pagina `mascotas` (YAGNI; extraerlo es mecánico si un change futuro lo necesita).
- Rechazar parámetros de query desconocidos (`?pagina=2` se ignora, comportamiento por defecto de FastAPI).
- Validación estricta de tipos (`"duenio_id": "1"` o `true` se aceptan como `1`, como en todo el proyecto); lista cerrada de especies; largo máximo de textos (C-02 no los limita).
- Consistencia transaccional entre el conteo y la página (ver Riesgos).

## Decisions

### Decisión 1 — ⚠ PA-05: `pages = ceil(total / size)` (0 sin mascotas) y página válida si `page ≤ max(pages, 1)`
- **Aprobada por Lautaro Mejias el 2026-11-06.**
- `pages = (total + size - 1) // size` (división entera hacia arriba, sin `float`): `total = 0` → `pages = 0`; 3 mascotas con `size = 2` → 2; con `size = 3` → 1.
- `page = 1` responde **siempre** (200), aun con `total = 0` (`items: []`): lo exige el PDF ("la primera página siempre responde, aunque no haya resultados").
- `page > max(pages, 1)` → **422** (Decisión 4). Con `total = 0`, `page = 2` ya es 422.
- **Por qué `pages = 0` y no 1**: `pages` informa cuántas páginas **con resultados** hay; con 0 mascotas no hay ninguna, y `ceil(0 / size) = 0` es la fórmula natural (la del envoltorio de `fastapi-pagination` y la que la KB propone). Que la página 1 responda con `pages = 0` es la excepción que el PDF manda explícitamente, y se expresa con `max(pages, 1)` en la regla de rango, no falseando el dato.

**Alternativas**: `pages = max(1, ceil(total/size))` (hace "siempre responde la primera" automático, pero miente: dice que hay una página cuando no hay resultados, y un cliente que itera `range(1, pages+1)` pediría una página vacía; descartada); `page > pages` → 422 sin excepción (con `total = 0` la página 1 daría 422, contra el PDF; descartada); página fuera de rango → 200 con `items: []` (contra el PDF, que pide 422; descartada).

### Decisión 2 — PA-12: orden por `id` ascendente
`select(Mascota).order_by(Mascota.id).offset((page - 1) * size).limit(size)`. Sin `ORDER BY`, PostgreSQL no garantiza el orden, y con `OFFSET`/`LIMIT` una mascota podría repetirse o saltearse entre páginas. `id` es la clave primaria: orden **total** (sin empates), estable entre peticiones e indexado. Coincide con el orden de `GET /duenios/{id}/mascotas` (D-10 de C-03).

**Alternativas**: por `nombre` (no es único: con empates el orden entre páginas vuelve a ser indeterminado salvo desempate por `id`; la consigna no lo pide; descartada); orden configurable con `?orden=` (fuera de alcance; descartada).

### Decisión 3 — Parámetros de query con `Annotated` y `Query`, declarados en el router
```python
# app/modules/mascotas/router.py
Pagina = Annotated[int, Query(ge=1, description="Número de página, desde 1")]
TamanioPagina = Annotated[int, Query(ge=1, le=TAMANIO_MAXIMO, description="Mascotas por página (1 a 100)")]

@router.get("/", status_code=200, response_model=PaginaMascotas, responses={422: ...})
async def listar_mascotas(session: SessionDep, page: Pagina = 1, size: TamanioPagina = TAMANIO_POR_DEFECTO) -> PaginaMascotas:
    return await service.listar_mascotas(session, page, size)
```
- Los nombres `page` y `size` son los de la consigna (y del envoltorio). Default en la asignación, no `Query(default=...)` (estilo `Annotated` de la skill `fastapi`, igual que `SessionDep`/`IdRuta`).
- `size` fuera de 1..100, `page < 1` o no enteros → 422 de FastAPI con `loc` `["query", ...]`, **sin ejecutar el handler ni consultar la base** (verificado, punto 4).
- `page` no tiene cota superior en el `Query`: el límite real depende de `total` y lo resuelve la Decisión 4 en Python, **antes** de cualquier `OFFSET` (así un `page` enorme nunca llega a la base ni desborda `OFFSET`).
- Constantes `TAMANIO_POR_DEFECTO: Final = 20` y `TAMANIO_MAXIMO: Final = 100` en `app/modules/mascotas/schemas.py` (son parte del contrato; las usan router y tests).
- Los alias viven en el router de `mascotas` porque sólo ese módulo pagina; `app/core/parametros.py` queda para lo compartido.

**Alternativas**: un modelo Pydantic de query (`Annotated[ParamsPagina, Query()]`, FastAPI ≥ 0.115; permite `extra="forbid"` sobre la query, pero rechazar parámetros desconocidos no lo pide nadie y agrega una forma que el resto del proyecto no usa; descartada); `page: int = Query(1, ge=1)` (estilo anterior a `Annotated`; descartada por la skill `fastapi`); alias en `app/core/parametros.py` (prematuro con un solo uso; descartada).

### Decisión 4 — ⚠ Página fuera de rango: contar primero y lanzar `HTTPException(422)` con el formato de validación
- **Aprobada por Lautaro Mejias el 2026-11-06.**
```python
# app/modules/mascotas/service.py
async def listar_mascotas(session: AsyncSession, page: int, size: int) -> PaginaMascotas:
    total = (await session.exec(select(func.count()).select_from(Mascota))).one()
    pages = (total + size - 1) // size
    if page > max(pages, 1):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"type": "pagina_fuera_de_rango", "loc": ["query", "page"],
                     "msg": PAGINA_INEXISTENTE, "input": page, "ctx": {"pages": pages}}],
        )
    consulta = select(Mascota).order_by(Mascota.id).offset((page - 1) * size).limit(size)
    mascotas = (await session.exec(consulta)).all()
    return PaginaMascotas(items=[MascotaRead.model_validate(m) for m in mascotas],
                          total=total, page=page, size=size, pages=pages)
```
- **Contar primero**: el rango depende de `total`, así que el conteo es imprescindible; hacerlo antes permite cortar con 422 sin ejecutar la consulta de la página (1 sentencia en vez de 2) y garantiza que el `OFFSET` enviado a la base es siempre `< total` (o 0).
- **Cuerpo**: `{"detail": [{"type", "loc", "msg", "input", "ctx"}]}`, la misma forma que los 422 de FastAPI (verificado, punto 2), como exige el requisito "Cuerpo de los errores" de `contrato-de-errores` ("Las respuestas 422 SHALL conservar el formato de validación de FastAPI"). `type` propio `pagina_fuera_de_rango`; `loc` apunta al parámetro culpable; `msg` fijo `"La página pedida no existe"` (constante `PAGINA_INEXISTENTE`); `ctx: {"pages": n}` le dice al cliente hasta dónde puede pedir, igual que Pydantic pone `{"ge": 1}` en `ctx`. El cliente procesa todos los 422 igual.
- El service lanza `HTTPException` (D-4 de C-03): el router no tiene `if`. Es el service el que conoce `total`.
- `status.HTTP_422_UNPROCESSABLE_CONTENT` es el nombre vigente (verificado en el venv: existe y vale 422 sin advertencias; el anterior `HTTP_422_UNPROCESSABLE_ENTITY` está deprecado).

**Alternativas**: `raise RequestValidationError([...])` desde el service (produce exactamente el mismo cuerpo por el manejador de FastAPI, pero es una excepción pensada para la validación de la petición y su firma exige el formato interno de errores de Pydantic; `HTTPException` es lo que el patrón de C-03 ya usa; descartada); `HTTPException(422, detail="La página pedida no existe")` con `detail` texto (rompe la forma de lista que el contrato fija para los 422; descartada); consultar la página primero y contar después (con página fuera de rango se gasta una consulta con un `OFFSET` arbitrario; descartada); `count(*) OVER ()` en la misma consulta de la página (una sentencia, pero con una página vacía no hay filas y no se conoce `total`: haría falta un segundo conteo justo en el caso de error, y el número de consultas dejaría de ser fijo; descartada); dependencia de FastAPI que valide la página (necesita la sesión y la consulta de conteo: lógica del service fuera del service; descartada).

### Decisión 5 — Número fijo de consultas del listado: 2 (conteo + página); `items` sin el dueño
- Listado en rango: exactamente 2 sentencias (`SELECT count(*) FROM mascota` y `SELECT ... FROM mascota ORDER BY mascota.id LIMIT .. OFFSET ..`), con `size` 1, 3 o 20. Fuera de rango: 1.
- `items` son `MascotaRead` (con `duenio_id`, sin el objeto dueño): el PDF dice "Envoltorio con mascotas" y reserva "Mascota con su dueño" para el detalle. Así el listado no toca ninguna relación y no hay N+1 posible ni carga anticipada que declarar.
- El `ORDER BY id LIMIT/OFFSET` se resuelve con el índice de la clave primaria; el `OFFSET` está acotado por la Decisión 4.

**Alternativas**: `items` con el dueño anidado (`joinedload(Mascota.duenio)` en la consulta de la página: seguiría siendo 2 sentencias, pero cambia el contrato que la consigna nombra como "Envoltorio con mascotas" y duplica datos del dueño en cada item; descartada).

### Decisión 6 — Alta: un `INSERT` y la clave foránea decide el 409 (caso C-04)
```python
DUENIO_INDICADO_INEXISTENTE: Final = "No existe el dueño indicado"
RECHAZOS_ALTA: Final[Mapping[str, Rechazo]] = {
    "mascota_duenio_id_fkey": Rechazo(status.HTTP_409_CONFLICT, DUENIO_INDICADO_INEXISTENTE),
}

async def crear_mascota(session: AsyncSession, datos: MascotaCreate) -> MascotaRead:
    mascota = Mascota.model_validate(datos)
    session.add(mascota)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_ALTA) from exc
    return MascotaRead.model_validate(mascota)
```
- Es la misma forma que `crear_duenio` de C-03 (D-1, D-16): `traducir_rechazo` con el mapa **propio** de esta operación. La misma restricción `mascota_duenio_id_fkey` significa otra cosa al **borrar** un dueño (`RECHAZOS_BORRADO` de C-03, RN-08): por eso el mapa es por operación (D-1 de C-03).
- **409 y no 404**: el dueño viaja en el **cuerpo**; el recurso de la ruta (`/mascotas/`) existe. La consigna fija 409 para este caso (caso C-04; "409 si la base rechaza la escritura"; KB 05 "no 404/422"). Contrasta con la ficha de C-03, donde el dueño está en la ruta → 404 (PA-01).
- Una sola sentencia (`INSERT INTO mascota ... RETURNING mascota.id`); con `expire_on_commit=False` la respuesta se arma sin releer. Un `INSERT` rechazado consume un valor de la secuencia (D-16 de C-03): el `.http` lo refleja.
- `duenio_id` `0` o negativo llega a la base (no hay `ge=1`, igual que `IdRuta` en D-13 de C-03) y la FK lo rechaza → 409. `duenio_id > 2147483647` se corta en el DTO (Decisión 7) porque asyncpg no puede codificarlo como `int4` y terminaría en 500.

**Alternativas**: `session.get(Duenio, datos.duenio_id)` → 404/409 antes del `INSERT` (pre-chequeo prohibido por la consigna y con ventana de carrera; descartada); mensaje igual al 404 de C-03 `"No existe el dueño"` (mismo texto con otro código confunde; "indicado" deja claro que el problema es el `duenio_id` enviado; descartada).

### Decisión 7 — ⚠ DTO de `mascotas`: `MascotaRead` intacto y tres DTO nuevos a su lado
- **Aprobada por Lautaro Mejias el 2026-11-06.**
| DTO | Campos | Configuración |
|-----|--------|---------------|
| `MascotaRead` (C-03, **sin cambios**) | `id: int`, `nombre: str`, `especie: str`, `duenio_id: int` | salida |
| `MascotaCreate` | `nombre: str = Field(min_length=1)`, `especie: str = Field(min_length=1)`, `duenio_id: int = Field(le=ENTERO_MAXIMO)` | `ENTRADA` (`extra="forbid"`, `str_strip_whitespace=True`) |
| `MascotaConDuenioRead(MascotaRead)` | `+ duenio: DuenioRead` | salida |
| `PaginaMascotas` | `items: list[MascotaRead]`, `total: int`, `page: int`, `size: int`, `pages: int` | salida |

- **`MascotaRead` no se toca**: lo usa `GET /duenios/{id}/mascotas` (D-11 de C-03) y su contrato está en la spec `duenios-y-fichas`; agregarle campos cambiaría esa respuesta. Los nuevos DTO se agregan en el mismo archivo.
- **`MascotaConDuenioRead` hereda de `MascotaRead`** (como `DuenioConFichaRead(DuenioRead)` en C-03) y anida `DuenioRead` (`id`, `nombre`, `email`, sin ficha): "Mascota con su dueño" del PDF. Conserva `duenio_id` (redundante con `duenio.id`, pero el detalle es un superconjunto del item del listado). `duenio` no es opcional: la FK es `NOT NULL`, toda mascota tiene dueño.
- **Reutiliza `ENTRADA` y `DuenioRead` importándolos de `app/modules/duenios/schemas.py`** sin editar ese archivo. No hay ciclo: `duenios.schemas` no importa nada de `mascotas` (sólo `duenios.service`/`router` importan `MascotaRead`).
- **`min_length=1` + `str_strip_whitespace`** en `nombre` y `especie`: `"   "` → 422 en vez de guardar un texto vacío (mismo criterio que D-12 de C-03). `especie` es texto libre: el PDF no fija un catálogo (el seed usa "perro" y "gato").
- **`duenio_id` con `le=ENTERO_MAXIMO`** (reutiliza la constante de `app/core/parametros.py`, como D-13 de C-03 anticipaba para los ids del cuerpo): evita el desborde `int4` → 500; sin cota inferior (Decisión 6).
- Constantes de contrato en el mismo archivo: `TAMANIO_POR_DEFECTO = 20`, `TAMANIO_MAXIMO = 100` (Decisión 3).

**Alternativas**: extender `MascotaRead` con `duenio: DuenioRead | None = None` (un solo DTO para item y detalle, pero cambia `GET /duenios/{id}/mascotas` y el listado con un `"duenio": null` engañoso; descartada); nombre `MascotaDetalle` (la convención del proyecto es `<Entidad>Con<Relacion>Read`, como `DuenioConFichaRead`; descartada); mover `ENTRADA` a `app/core/` (más limpio, pero edita código archivado de C-03 sin necesidad; queda como refactor posible; descartada); `PaginaMascotas` genérico `Pagina[T]` (Non-Goals).

### Decisión 8 — Detalle: `joinedload(Mascota.duenio)` en la misma consulta; 404 con mensaje propio
```python
MASCOTA_INEXISTENTE: Final = "No existe la mascota"

async def obtener_mascota(session: AsyncSession, mascota_id: int) -> MascotaConDuenioRead:
    consulta = select(Mascota).where(Mascota.id == mascota_id).options(joinedload(Mascota.duenio))
    mascota = (await session.exec(consulta)).one_or_none()
    if mascota is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MASCOTA_INEXISTENTE)
    return MascotaConDuenioRead.model_validate(mascota)
```
- Una sola sentencia (`SELECT ... FROM mascota LEFT OUTER JOIN duenio ...`) para la mascota y su dueño (relación "a uno" → `joinedload`, Ej. 5); `None` → 404 con la misma consulta, sin "¿existe?" separado (D-6 de C-03).
- `MascotaConDuenioRead.model_validate` dentro del service (D-15 de C-03): si alguien quita el `joinedload`, falla en el test con `MissingGreenlet`, nunca con carga perezosa silenciosa.
- `{id}` con `IdRuta` (D-13 de C-03): `abc` y `2147483648` → 422 sin handler; `0`, `-1` → 404.

**Alternativas**: `joinedload(..., innerjoin=True)` (válido porque la FK es `NOT NULL`, pero el `LEFT OUTER JOIN` por defecto da el mismo resultado y es la forma que usa C-03; descartada); `selectinload` (2 sentencias para una relación "a uno"; contra la guía del Ej. 5; descartada); `session.get(Mascota, id, options=[joinedload(...)])` (equivalente; la consulta explícita se lee igual que la de C-03; descartada).

### Decisión 9 — Mensajes propios (texto exacto)
| Situación | Código | Cuerpo |
|-----------|--------|--------|
| Alta con dueño inexistente (`mascota_duenio_id_fkey`) — caso C-04 | 409 | `{"detail": "No existe el dueño indicado"}` |
| Mascota inexistente (`GET /mascotas/{id}`) | 404 | `{"detail": "No existe la mascota"}` |
| Página más allá de `pages` | 422 | `{"detail": [{"type": "pagina_fuera_de_rango", "loc": ["query", "page"], "msg": "La página pedida no existe", "input": <page>, "ctx": {"pages": <pages>}}]}` |
| Cualquier otro rechazo de la base no declarado | 409 | `{"detail": "La base rechazó la escritura"}` (D-2 de C-03) |

Constantes `DUENIO_INDICADO_INEXISTENTE`, `MASCOTA_INEXISTENTE`, `PAGINA_INEXISTENTE` y `RECHAZOS_ALTA` en `app/modules/mascotas/service.py`. Sin SQL, nombres de restricciones ni tablas.

### Decisión 10 — Router delgado (`app/modules/mascotas/router.py`) y registro
- `router = APIRouter(prefix="/mascotas", tags=["mascotas"])`; rutas `"/"` (POST y GET) y `"/{id}"` (GET), con la barra final de la consigna en `/mascotas/`.
- Cada handler `async def`, una línea `return await service.<funcion>(...)`, `from app.modules.mascotas import service` (para poder espiar el service como en el caso C-01 de C-03). Declaran `status_code`, `response_model` y `responses` (`MensajeError` para 404/409; el 422 de página lo documenta la descripción de la ruta).
- Firmas del service: `crear_mascota(session, datos) -> MascotaRead`, `obtener_mascota(session, mascota_id) -> MascotaConDuenioRead`, `listar_mascotas(session, page, size) -> PaginaMascotas`.
- `app/main.py`: `aplicacion.include_router(mascotas_router)` después de `duenios_router`. Si C-05 ya agregó `practicas_router`, se suma la línea sin reordenar (conflicto de merge trivial).
- Transacciones (D-16 de C-03): el alta hace un `commit`; las lecturas no.

### Decisión 11 — Tests: archivos y cómo se prueba cada propiedad
Todos con `pytestmark = pytest.mark.integracion`, contra `veterinaria_test` (`base_con_seed` o `esquema_vacio`) con `client`; nunca mocks.
- **`tests/test_mascotas.py`** — alta (201 exacto, strip, 409 caso C-04 con cuerpo exacto y sin filtraciones de SQL, 409 con `duenio_id` 0/-1, alta posterior al rechazo, 422 parametrizado por cada cuerpo inválido del spec con conteo de filas), detalle (200 exactos de las mascotas 1 y 3, 404 con 999/0/2147483647, 422 con `abc`/`2147483648`) y no-regresión de `GET /duenios/1/mascotas`.
- **`tests/test_mascotas_paginacion.py`** — envoltorio por defecto exacto, última página incompleta, borde exacto (`size=3`, `page=3&size=1`), `size` 1 y 100, orden por `id` tras un `UPDATE` directo de la mascota 1 (la fila queda físicamente última en el heap de PostgreSQL), vacío con `esquema_vacio` (`page=1` 200 / `page=2` 422 con `ctx.pages == 0`), fuera de rango con cuerpo exacto, `size`/`page` inválidos parametrizados con `loc` y `type`.
- **`tests/test_mascotas_consultas.py`** — con `sentencias_app`: alta rechazada → sólo `INSERT INTO mascota`; detalle → 1 sentencia con `JOIN duenio`; listado con 25 mascotas y `size` 1/3/20 → 2 sentencias sobre `mascota` sin `duenio`; fuera de rango → 1 sentencia (`count`); parámetros inválidos y id de ruta inválido → 0 sentencias.
- **`tests/test_mascotas_http.py`** — como `test_duenios_http.py`: el archivo existe, contiene "Caso C-04" y cada bloque tiene `# Esperado:`; y lo ejecuta en orden sobre `base_con_seed` con `bloques_http`, comparando el código.
- Las propiedades que FastAPI ya cubre al escribir el test (422 de `size`/`page`) se prueban por mutación (cambiar temporalmente `le=100` → sin cota y ver el rojo), como en C-03.

### Decisión 12 — `test/mascotas.http`: casos en orden, después de `python reiniciar.py`
Mismo formato que `test/duenios.http` (comentario inicial: correr en orden y una sola vez tras `python reiniciar.py`; `[modifica]` marca las que cambian el estado; los `INSERT` rechazados consumen ids).

| # | Petición | Esperado (comentario) |
|---|----------|-----------------------|
| 1 | `GET /mascotas/` | 200 `{"items": [Toby, Mishi, Luna], "total": 3, "page": 1, "size": 20, "pages": 1}` |
| 2 | `GET /mascotas/?page=2&size=2` | 200 `{"items": [Luna], "total": 3, "page": 2, "size": 2, "pages": 2}` |
| 3 | `GET /mascotas/?page=3&size=2` | 422 `pagina_fuera_de_rango`, `ctx` `{"pages": 2}` |
| 4 | `GET /mascotas/?size=0` | 422 `["query", "size"]` `greater_than_equal` |
| 5 | `GET /mascotas/?size=101` | 422 `["query", "size"]` `less_than_equal` |
| 6 | `GET /mascotas/?page=0` | 422 `["query", "page"]` `greater_than_equal` |
| 7 | `GET /mascotas/1` | 200 Toby con `"duenio": {"id": 1, "nombre": "Ana Gómez", ...}` |
| 8 | `GET /mascotas/999` | 404 `{"detail": "No existe la mascota"}` |
| 9 | `GET /mascotas/abc` | 422 `["path", "id"]` `int_parsing` |
| 10 | **[modifica]** `POST /mascotas/` Rocky, perro, dueño 2 | 201 `{"id": 4, "nombre": "Rocky", "especie": "perro", "duenio_id": 2}` |
| 11 | **Caso C-04 (primera parte)** `POST /mascotas/` con `duenio_id` 999 | 409 `{"detail": "No existe el dueño indicado"}` (consume el id 5) |
| 12 | `POST /mascotas/` con `"id": 9` | 422 `extra_forbidden` en `["body", "id"]` |
| 13 | `GET /mascotas/?page=2&size=2` | 200 `{"items": [Luna, Rocky], "total": 4, "page": 2, "size": 2, "pages": 2}` |

El listado vacío no se puede mostrar en el `.http` (no hay `DELETE /mascotas/{id}` y el seed tiene mascotas): lo cubre pytest con `esquema_vacio`. El caso C-04 segunda parte (turno con práctica inexistente) va en el `.http` de C-06.

### Decisión 13 — Archivos y alcance
Nuevos: `app/modules/mascotas/service.py`, `app/modules/mascotas/router.py`, `test/mascotas.http`, `tests/test_mascotas.py`, `tests/test_mascotas_paginacion.py`, `tests/test_mascotas_consultas.py`, `tests/test_mascotas_http.py`. Modificados: `app/modules/mascotas/schemas.py` (sólo agrega), `app/main.py` (import + una línea). No se tocan: modelos, `reiniciar.py`, `app/core/*`, `app/modules/duenios/*`, `tests/conftest.py`, `tests/soporte.py`, `app/modules/laboratorio/`.

## Risks / Trade-offs

- [Conteo y página en dos sentencias bajo `READ COMMITTED`: un alta concurrente entre ambas puede dejar `total`/`pages` desfasados en uno respecto de `items`] → aceptado: el desfase es transitorio, no corrompe datos y la consigna no lo evalúa; la alternativa (`REPEATABLE READ` en la sesión del listado, o `count(*) OVER ()`) agrega complejidad o rompe el número fijo de consultas (Decisión 4). Se documenta como mejora posible.
- [`OFFSET` crece linealmente con la página] → con `size ≤ 100` y el volumen de una veterinaria de barrio es irrelevante; la paginación por cursor (keyset) está fuera de alcance.
- [El 422 de página fuera de rango usa un `type` propio (`pagina_fuera_de_rango`) que no existe en Pydantic] → es el mismo formato de lista; un cliente que sólo lee `loc`/`msg` lo trata igual. Queda fijado en el spec con el cuerpo exacto.
- [`MascotaRead` es compartido con `duenios`: un cambio futuro afecta dos respuestas] → este change no lo modifica y agrega un test de no-regresión de `GET /duenios/1/mascotas`.
- [`main.py` lo editan C-04 y C-05 en paralelo] → una línea cada uno; al integrar, conservar ambos `include_router`.
- [Los ids de los tests y del `.http` dependen del orden: el 409 consume un valor de la secuencia] → los tests arrancan de `base_con_seed`/`esquema_vacio` y fijan los ids; el `.http` documenta el salto.

## Migration Plan

Sin migración: el esquema y el seed son de C-02. Puesta en marcha: `docker compose up -d`, `python reiniciar.py`, `uvicorn app.main:app`. Vuelta atrás: los archivos son nuevos salvo `app/modules/mascotas/schemas.py` (sólo agrega) y `app/main.py` (una línea), que se revierten con git.
