## Context

Motivación y alcance en `proposal.md`; comportamiento exigido en `specs/duenios-y-fichas/spec.md` y `specs/contrato-de-errores/spec.md`.

Estado de partida:

- **C-01 archivado** (`openspec/changes/archive/2026-11-05-base-proyecto-conexion/`): `app/core/config.py`, `app/core/database.py` (`crear_motor`, `crear_fabrica_sesiones` con `AsyncSession` de `sqlmodel.ext.asyncio.session` y `expire_on_commit=False`, `get_session`, `SessionDep`), `app/main.py` (`lifespan` guarda `engine` y `session_factory` en `app.state`; `crear_app()` registra routers). El módulo `health` es la referencia de forma: `router.py` importa el módulo `service` (`from app.modules.health import service`) y llama `service.base_disponible(...)`; `APIRouter(prefix=..., tags=[...])`; `status_code` + `response_model` + `responses` en cada ruta. Tests: `tests/conftest.py` (`url_base_test`, `app`, `client`), `tests/soporte.py` (`levantar_app`, `cliente_de`).
- **C-02 con design aprobado, en `apply` mientras se escribe este design** (`openspec/changes/modelos-esquema-seed/design.md`). Este change usa exactamente sus nombres: `Duenio` / `FichaDuenio` en `app/modules/duenios/models.py`, `Mascota` en `app/modules/mascotas/models.py`; relaciones `Duenio.ficha` (`uselist=False`) ↔ `FichaDuenio.duenio`, `Duenio.mascotas` ↔ `Mascota.duenio`, con `passive_deletes="all"` en los lados "uno" (D-7 de C-02); restricciones `uq_duenio_email`, `uq_ficha_duenio_duenio_id`, `ficha_duenio_duenio_id_fkey` (CASCADE), `mascota_duenio_id_fkey` (RESTRICT); registro `app/core/modelos.py` importado desde `app/main.py`; fixtures `esquema_vacio`, `base_con_seed`, `sesion`, `sentencias_sql` (sobre `motor_test`) y helper de tests `error_postgres(exc)`; datos iniciales: dueño 1 "Ana Gómez" `ana.gomez@example.com` **con** ficha 1 ("11 5555-0101", "Calle Falsa 123") y mascotas 1 "Toby" (perro) y 2 "Mishi" (gato); dueño 2 "Carlos Ruiz" `carlos.ruiz@example.com` **sin** ficha, con la mascota 3 "Luna" (perro). Al cerrar este propose, C-02 tiene sus 66 tareas marcadas (`openspec list`, sin archivar) y lo que está en disco coincide con esos nombres (leído: `app/modules/duenios/models.py` con `uq_duenio_email`, `uq_ficha_duenio_duenio_id`, `ondelete="CASCADE"`, `Duenio.ficha`/`Duenio.mascotas` con `passive_deletes="all"`; `Mascota.duenio_id` con `ondelete="RESTRICT"`; `app/main.py` importa `app.core.modelos`; fixtures `sesion`, `sentencias_sql` y `base_con_seed` en `tests/conftest.py`). La tarea 0 de este change igual exige C-02 completo y la suite en verde.
- **Versiones instaladas** (`.venv`, Python 3.14): `fastapi==0.162.0`, `starlette==1.10.0`, `sqlmodel==0.0.48`, `sqlalchemy==2.0.57`, `asyncpg==0.32.0`, `pydantic==2.14.3`, `email-validator==2.3.0`.

Las decisiones D-2 y D-13 fueron **modificadas por Matheo el 2026-11-05** (ver su encabezado); D-1, D-7, D-11, D-12 y las demás quedaron **APROBADAS por Matheo, 2026-11-05**.

Restricciones que condicionan el diseño: reglas duras 2 (async sin bloqueos), 3 (la base es el garante, sin pre-chequeos), 4 (lecturas eager), 5 (router delgado), 6 (DTO separados), 7 (`extra="forbid"`), 9 (PostgreSQL real) y 10 (tests + `.http`) de `AGENTS.md`. La tabla "Estructura del proyecto" de la consigna asigna a `service.py` "lógica, **traducción de errores** y lecturas con precarga" y a `router.py` "rutas HTTP: reciben, delegan y declaran la respuesta".

**Verificado antes de decidir** (código instalado en `.venv/Lib/site-packages` + context7):

1. `sqlalchemy/dialects/postgresql/asyncpg.py` (`AsyncAdapt_asyncpg_connection._handle_exception`, ~l. 781): la excepción de asyncpg se traduce a `AsyncAdapt_asyncpg_dbapi.IntegrityError` (mapa `_asyncpg_error_translate`: `asyncpg.exceptions.IntegrityConstraintViolationError → IntegrityError`), se le copian `pgcode` y `sqlstate` y se lanza con `raise translated_error from error`. Por lo tanto, en el `sqlalchemy.exc.IntegrityError` que ve el service: `exc.orig` es el adaptador (tiene `sqlstate`, **no** `constraint_name`) y `exc.orig.__cause__` es la excepción original de asyncpg.
2. `asyncpg/exceptions/_base.py` (`PostgresMessageMeta._field_map`): `'C' → sqlstate`, `'n' → constraint_name`, `'t' → table_name`; `asyncpg/exceptions/__init__.py`: `UniqueViolationError` (`23505`), `ForeignKeyViolationError` (`23503`), `NotNullViolationError` (`23502`), `CheckViolationError` (`23514`), todas subclases de `IntegrityConstraintViolationError`.
3. `sqlmodel/ext/asyncio/session.py` 0.0.48: `AsyncSession.exec` acepta `Select`, `SelectOfScalar` y `UpdateBase` (este último devuelve `CursorResult`, con `rowcount`); `AsyncSession.execute` está marcado `@deprecated` ("You probably want to use `session.exec()`"). `sqlmodel` reexporta `delete` (`from sqlalchemy.sql import delete`).
4. SQLAlchemy 2.0, "ORM UPDATE and DELETE with Custom WHERE Criteria": `delete(Modelo).where(...)` ejecutado en la sesión emite un único `DELETE` con ese `WHERE`, sin cargar objetos ni consultar relaciones; `synchronize_session` por defecto `"auto"`, que según `sqlalchemy/orm/bulk_persistence.py` (`_do_pre_synchronize_auto`) prueba primero `"evaluate"` (sin SQL extra) y sólo si el `WHERE` no es evaluable pasa a `"fetch"` (`RETURNING`): con `Duenio.id == x` se emite sólo el `DELETE`. `sqlalchemy/orm/query.py` (`Query.delete`, ~l. 3229) devuelve `result.rowcount` de esa misma ejecución.
5. `fastapi/dependencies/utils.py` (`solve_dependencies`, ~l. 676-760): las sub-dependencias (`get_session`) se resuelven **antes** de validar los parámetros de ruta; si hay errores, `fastapi/routing.py` lanza `RequestValidationError` y **no** llama `run_endpoint_function`. Con `/duenios/abc` se crea el objeto `AsyncSession` (sin conexión: no se envía SQL) pero el handler no se ejecuta.
6. `fastapi/routing.py` (`serialize_response`) valida la respuesta con `from_attributes=True` (`fastapi/_compat/v2.py:182`); los modelos SQLModel no-tabla tienen `model_config = SQLModelConfig(from_attributes=True)` (`sqlmodel/main.py:851`), así que `DuenioRead.model_validate(duenio)` lee atributos (y relaciones) del objeto ORM. `SQLModel.model_validate(obj, update={...})` existe (`sqlmodel/main.py:910`); `sqlmodel_update(dict)` hace `setattr` sólo de las claves recibidas (`sqlmodel/main.py:1024`).
7. `pydantic/networks.py` (`validate_email`): usa `email_validator.validate_email(..., check_deliverability=False)` y devuelve `parts.normalized`. Probado en el venv: `"Ana.Gomez@EXAMPLE.COM"` → `"Ana.Gomez@example.com"` (dominio en minúsculas, parte local intacta), `"  ana@example.com "` → `"ana@example.com"`, `example.com` aceptado (`email_validator` comenta `example.*` en `SPECIAL_USE_DOMAIN_NAMES`), `x@localhost` y `x@test` rechazados. `fastapi-0.162.0.dist-info/METADATA`: `Requires-Dist: email-validator>=2.0.0; extra == "standard"`.
8. Prototipo en memoria del `DuenioUpdate` de la Decisión 12 (sin tocar el repo): `{}` → `model_dump(exclude_unset=True) == {}`; `{"nombre": null}` y `{"email": null}` → `value_error`; `{"nombre": "  "}` → `string_too_short`; `{"x": 1}` → `extra_forbidden`.
9. `sqlalchemy/engine/create.py` (`first_connect`, ~l. 757): la conexión que inicializa el dialecto se crea con `_has_events=False`, así que las consultas de arranque del dialecto (`select pg_catalog.version()`, etc.) **no** pasan por `before_cursor_execute`: el conteo de sentencias de una petición no depende de si es la primera conexión del motor.
10. FastAPI, "Handling Errors": un `HTTPException` lanzado desde una función auxiliar llamada por el handler termina la petición con ese error; "Additional Responses in OpenAPI": `responses={404: {"model": Mensaje, "description": ...}}`. SQLAlchemy asyncio, "Preventing Implicit IO when Using AsyncSession": `selectinload` / `joinedload` en la consulta y `expire_on_commit=False` para leer atributos después del `commit`.
11. Pydantic 2.14: `"abc"` → `int_parsing` ("Input should be a valid integer, unable to parse string as an integer"); con `ge=1, le=2147483647`, `"0"` → `greater_than_equal` y `"2147483648"` → `less_than_equal`.

## Goals / Non-Goals

**Goals:**
- Un patrón que C-04..C-06 copien sin pensar: router de una línea por ruta, service que escribe primero y traduce el rechazo con un helper de `app/core/`, DTO separados, sin editar el código de este change para agregar sus restricciones.
- Que cada regla (RN-01, RN-03, RN-08) y cada 404 se demuestre en un test **mirando las sentencias SQL**: ninguna consulta "¿ya existe?" antes de una escritura.
- Que el detalle del dueño y sus mascotas tengan un número fijo de consultas, probado con un contador de sentencias del motor de la aplicación.
- Que `test/duenios.http` se pueda correr de arriba abajo después de `python reiniciar.py` y cada respuesta coincida con su comentario.

**Non-Goals:**
- Manejadores globales de excepciones (`app.exception_handler`) o un envoltorio de error propio: el formato es el de FastAPI (Decisión 3).
- Validaciones que la consigna no pide: largo máximo de textos, formato de teléfono, email insensible a mayúsculas en la parte local.
- Bloqueos (`SELECT ... FOR UPDATE`) o reintentos ante carreras entre peticiones concurrentes sobre el mismo dueño (ver Riesgos).
- Paginación o filtros en `GET /duenios/{id}/mascotas` (la consigna no los pide; la paginación es de `GET /mascotas/`, C-04).
- Endpoints de mascotas (C-04): este change sólo crea su DTO de salida (Decisión 11).

## Decisions

### Decisión 1 — ⚠ PA-01: traducción de rechazos con un helper en `app/core/errores.py` y un mapa por operación (APROBADA con cambios por Matheo, 2026-11-05: ajustada por la Decisión 2)
El service escribe; si la base rechaza, el `IntegrityError` se traduce **por el nombre de la restricción** que informa PostgreSQL, usando un mapa que declara cada operación:

```python
# app/core/errores.py
"""Traducción de los rechazos de la base (IntegrityError) a respuestas HTTP con mensaje propio."""
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

RECHAZO_GENERICO: Final = "La base rechazó la escritura"


class MensajeError(SQLModel):
    """Cuerpo de los 404/409 (el mismo formato que usa FastAPI); sólo documenta OpenAPI."""
    detail: str


@dataclass(frozen=True)
class Rechazo:
    status_code: int
    mensaje: str


def restriccion_violada(exc: IntegrityError) -> str | None:
    """Nombre de la restricción que rechazó la escritura.

    exc.orig es el error adaptado por SQLAlchemy (trae sqlstate); su __cause__ es la
    excepción de asyncpg, la única que trae constraint_name.
    """
    causa = exc.orig.__cause__ if exc.orig is not None else None
    return getattr(causa, "constraint_name", None)


def traducir_rechazo(exc: IntegrityError, rechazos: Mapping[str, Rechazo]) -> HTTPException:
    """HTTPException prevista para la restricción violada; si no está en `rechazos`, 409 genérico."""
    restriccion = restriccion_violada(exc)
    rechazo = rechazos.get(restriccion)
    if rechazo is None:
        # Sólo el nombre de la restricción y el SQLSTATE: nunca los valores ni credenciales.
        logger.warning("Rechazo no previsto de la base: restriccion=%s sqlstate=%s",
                       restriccion, getattr(exc.orig, "sqlstate", None))
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=RECHAZO_GENERICO)
    return HTTPException(status_code=rechazo.status_code, detail=rechazo.mensaje)
```

Uso en cada escritura del service (los tres pasos de la consigna quedan a la vista: atrapa, deshace, responde):

```python
RECHAZOS_EMAIL: Final[Mapping[str, Rechazo]] = {
    "uq_duenio_email": Rechazo(status.HTTP_409_CONFLICT, "Ya existe un dueño con ese email"),
}

async def crear_duenio(session: AsyncSession, datos: DuenioCreate) -> DuenioRead:
    duenio = Duenio.model_validate(datos)
    session.add(duenio)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_EMAIL) from exc
    return DuenioRead.model_validate(duenio)
```

- **Por qué la clave es el nombre de la restricción y no el SQLSTATE**: (a) el SQLSTATE solo no alcanza: en el alta de un turno (C-06) `turno_mascota_id_fkey` y `turno_practica_practica_id_fkey` dan los dos `23503` con significados distintos; (b) en PostgreSQL cada restricción con nombre produce un único SQLSTATE (UNIQUE/PK → `23505`, FK → `23503`, CHECK → `23514`), así que el nombre ya lo determina y agregarlo a la clave sería redundante; (c) los nombres son contrato fijado por los tests de introspección de C-02 (D-3 de C-02). `exc.orig.sqlstate` sigue disponible para quien quiera loguearlo.
- **Por qué un mapa por operación y no uno global**: la misma restricción significa cosas distintas según la escritura. `mascota_duenio_id_fkey` rechaza **borrar** un dueño con mascotas (RN-08, este change: 409 "tiene mascotas") y también **crear** una mascota con un dueño inexistente (C-04: 409 "no existe el dueño"); `ficha_duenio_duenio_id_fkey` al crear la ficha significa que no existe el dueño **de la ruta** → **404**. El mapa de cada operación expresa esa intención sin heurísticas (`table_name`, texto del `DETAIL`).
- **Cómo lo extienden C-04..C-06**: declaran en su propio `service.py` sus constantes `RECHAZOS_*` y llaman `traducir_rechazo`; no hay registro central ni nada que editar en `app/core/errores.py` ni en `duenios`.
- **Resuelve PA-01**: FK sobre el recurso de la ruta → 404 y UNIQUE → 409, distinguidos por `exc.orig.__cause__.constraint_name`, sin consulta previa.

**Alternativas**: un context manager `async with rechazos_de_la_base(session, RECHAZOS): ...` que haga el `rollback` y la traducción (imposible olvidar el `rollback`, pero esconde en `app/core` los tres pasos que el corrector busca en el service; descartada — además, si alguien lo olvidara, `get_session` cierra la sesión y la transacción se deshace igual); un `@app.exception_handler(IntegrityError)` global (no tiene la sesión para el `rollback` explícito y no sabe qué operación falló, así que no puede distinguir los dos usos de `mascota_duenio_id_fkey`; descartada); clave `(sqlstate, constraint_name)` (redundante por (b); descartada); distinguir por el texto del mensaje de PostgreSQL (frágil, depende del idioma del servidor; descartada).

### Decisión 2 — ⚠ Un rechazo no previsto responde 409 genérico (y se registra), no 500 (APROBADA con cambios por Matheo, 2026-11-05; reemplaza la propuesta original de relanzar → 500)
Si la restricción violada no está en el mapa de la operación (o el error no trae `constraint_name`, como un `NOT NULL` en PostgreSQL 16), `traducir_rechazo` devuelve `HTTPException(409, "La base rechazó la escritura")` (constante `RECHAZO_GENERICO`, mensaje propio, sin SQL ni nombres de restricciones) **después** del `rollback` que ya hizo el service, y registra con `logger.warning` el nombre de la restricción y el SQLSTATE (nunca los valores ni credenciales). Sólo el `IntegrityError` recibe este tratamiento; cualquier otra excepción se propaga normalmente (500).

**Por qué (decisión de Matheo)**: la consigna dice "409 si la base rechaza la escritura": una escritura que la base rechaza es un conflicto con el estado de los datos, aun cuando el change no haya declarado un mensaje específico para esa restricción. El log deja visible el defecto (restricción sin declarar) sin convertir el rechazo en un error del servidor.

**Alternativa original (descartada por Matheo)**: relanzar el `IntegrityError` → 500 para que un error de programación fuera ruidoso; contradice el "409 si la base rechaza la escritura" de la consigna.

### Decisión 3 — PA-11: cuerpo de error `{"detail": "<mensaje>"}` con `HTTPException`
404 y 409 se responden con `HTTPException(status_code, detail="<mensaje>")`, que FastAPI serializa como `{"detail": "<mensaje>"}`: el mismo formato que su 404 de ruta inexistente y que su 422 (`{"detail": [...]}`), así que el cliente lee siempre `detail`. `MensajeError` (Decisión 1) se declara en `responses={404: {"model": MensajeError, ...}, 409: {...}}` sólo para que OpenAPI documente el cuerpo. Los 422 conservan el formato de validación de FastAPI sin manejador propio.

**Alternativas**: envoltorio propio `{"error": {"codigo": ..., "mensaje": ...}}` o RFC 9457 `application/problem+json` (requieren manejadores globales y mezclan dos formatos con el 422 de FastAPI; nada en la consigna los pide; descartadas).

### Decisión 4 — El service lanza `HTTPException`; el router sólo delega
La traducción de errores vive en `service.py` (tabla "Estructura del proyecto" de la consigna) y el service "responde 409 con un mensaje propio" (texto de la consigna): por eso el service lanza `HTTPException` (404 y 409) y el router no tiene ningún `if`. FastAPI documenta lanzar `HTTPException` desde funciones auxiliares del handler (verificado, punto 10).

**Alternativas**: excepciones de dominio (`NoEncontrado`, `Conflicto`) + `app.add_exception_handler` en `crear_app()` (desacopla el service de HTTP, pero agrega una capa que el TP no necesita —el service no se usa fuera de HTTP— y obliga a cada integrante a conocer el manejador; descartada); el service devuelve `None` y el router decide el 404 (lógica en el router, contra la regla dura 5; descartada).

### Decisión 5 — Mensajes propios (texto exacto)
| Situación | Código | `detail` |
|-----------|--------|----------|
| Dueño inexistente (GET, PATCH, DELETE, ficha, mascotas) | 404 | `No existe el dueño` |
| Email repetido (POST y PATCH; `uq_duenio_email`) — RN-01, caso C-02 | 409 | `Ya existe un dueño con ese email` |
| Segunda ficha (`uq_ficha_duenio_duenio_id`) — RN-03, caso C-03 | 409 | `El dueño ya tiene una ficha` |
| Ficha de un dueño inexistente (`ficha_duenio_duenio_id_fkey`) | 404 | `No existe el dueño` |
| Borrar un dueño con mascotas (`mascota_duenio_id_fkey`) — RN-08, caso C-05 | 409 | `No se puede borrar el dueño: tiene mascotas a su nombre` |

Mensajes fijos, sin el id ni datos del cuerpo: el texto es idéntico en los tests, en el `.http` y en OpenAPI, y nunca incluye SQL ni nombres de restricciones (KB 08 §Seguridad). Se declaran como constantes en `app/modules/duenios/service.py` (`DUENIO_INEXISTENTE` y los mapas `RECHAZOS_*`), reutilizadas por los 404 y por el mapa de la ficha.

### Decisión 6 — 404 sin consultas previas: la lectura que el endpoint necesita de todos modos
- **GET `/duenios/{id}`**: `select(Duenio).where(Duenio.id == duenio_id).options(joinedload(Duenio.ficha))` → `(await session.exec(...)).one_or_none()`; `None` → 404. Es la misma (y única) consulta que arma la respuesta: no hay "¿existe?" separado.
- **PATCH, DELETE, ficha y mascotas**: Decisiones 7 a 10. En ninguna se consulta la existencia del dueño antes de escribir; donde hay `SELECT`, es la lectura que la respuesta necesita.

### Decisión 7 — ⚠ DELETE con una sentencia `delete(...)` y `rowcount`, no `session.get` + `session.delete` (APROBADA por Matheo, 2026-11-05)
```python
async def borrar_duenio(session: AsyncSession, duenio_id: int) -> None:
    try:
        resultado = await session.exec(delete(Duenio).where(Duenio.id == duenio_id))
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_BORRADO) from exc   # RN-08 → 409
    if resultado.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE)
    await session.commit()
```
- **Una sola sentencia** (`DELETE FROM duenio WHERE duenio.id = $1`), y la base decide los tres resultados: 0 filas → 404; RESTRICT por mascotas → `23503` sobre `mascota_duenio_id_fkey` → 409; si no, la ficha cae por `ON DELETE CASCADE` y se responde 204. Es "escribir y que decida la base" también para el 404.
- **Sin ventana de carrera**: con `session.get` + `session.delete`, si otra petición borra el dueño entre el `SELECT` y el `DELETE`, el ORM lanza `StaleDataError` ("expected to delete 1 row(s); Only 0 were matched") → 500. Con la sentencia única, ese caso es `rowcount == 0` → 404.
- El `DELETE` masivo del ORM no consulta las relaciones (verificado, punto 4): no depende de `passive_deletes`. Aun así, `passive_deletes="all"` de C-02 sigue siendo necesario para cualquier `session.delete(obj)` (C-02 lo prueba en `tests/test_borrados.py`).
- **Para C-06**: `DELETE /turnos/{id}` puede copiar este patrón (la cascada de `turno_practica` la hace la base, RN-09) o usar `session.delete(turno)` apoyándose en `passive_deletes="all"`; los dos cumplen "lo decide la base".

**Alternativa**: `duenio = await session.get(Duenio, id)` → `None` → 404; `await session.delete(duenio)`; `commit` → `IntegrityError` → 409 (dos sentencias; con `passive_deletes="all"` el ORM emite sólo `DELETE FROM duenio`, sin tocar fichas ni mascotas; muestra en el endpoint la configuración de relaciones del Ej. 3, pero agrega un `SELECT` previo y la carrera anterior; descartada).

### Decisión 8 — PATCH: lectura eager del dueño, `exclude_unset`, un `commit`
```python
async def actualizar_duenio(session, duenio_id: int, datos: DuenioUpdate) -> DuenioConFichaRead:
    duenio = await _duenio_con_ficha(session, duenio_id)          # SELECT ... LEFT OUTER JOIN ficha_duenio
    if duenio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE)
    duenio.sqlmodel_update(datos.model_dump(exclude_unset=True))
    try:
        await session.commit()                                       # UPDATE sólo si algo cambió
    except IntegrityError as exc:
        await session.rollback()
        raise traducir_rechazo(exc, RECHAZOS_EMAIL) from exc         # mismo mapa que el alta
    return DuenioConFichaRead.model_validate(duenio)
```
- El `SELECT` con `joinedload(Duenio.ficha)` no es un pre-chequeo: es la lectura que la respuesta ("dueño con su ficha") necesita, y de paso da el 404. La unicidad del email la sigue decidiendo el `UPDATE` (no hay `SELECT ... WHERE email = ...`).
- `model_dump(exclude_unset=True)` deja sólo los campos enviados; `sqlmodel_update` hace `setattr` de esos (verificado, punto 6). `{}` → nada cambia → el `commit` no emite `UPDATE` → 200 con los datos actuales. Mandar el propio email: SQLAlchemy no emite `UPDATE` de una columna sin cambio neto, y aunque lo emitiera no viola el UNIQUE (misma fila).
- Email de otro dueño → `UPDATE` rechazado por `uq_duenio_email` → `rollback` → 409; el `rollback` también descarta el cambio de `nombre` enviado en el mismo cuerpo (todo o nada por petición).
- Con `expire_on_commit=False` el objeto conserva sus atributos y la ficha cargada: la respuesta se arma sin un `SELECT` nuevo (dos sentencias en total: `SELECT` + `UPDATE`).
- `_duenio_con_ficha(session, duenio_id)` es la única función privada del service y la comparten GET y PATCH.

**Alternativas**: `update(Duenio).where(...).values(**datos)` + `rowcount` (no admite `{}` —un `UPDATE` sin columnas no es válido— y la respuesta necesita igual leer la ficha; descartada); `session.get(Duenio, id, options=[joinedload(...)])` (equivalente, pero la consulta explícita se lee igual que la del GET; descartada por uniformidad).

### Decisión 9 — Alta de la ficha: un `INSERT` y la base decide 404 o 409
```python
RECHAZOS_FICHA: Final[Mapping[str, Rechazo]] = {
    "uq_ficha_duenio_duenio_id": Rechazo(status.HTTP_409_CONFLICT, "El dueño ya tiene una ficha"),
    "ficha_duenio_duenio_id_fkey": Rechazo(status.HTTP_404_NOT_FOUND, DUENIO_INEXISTENTE),
}
ficha = FichaDuenio.model_validate(datos, update={"duenio_id": duenio_id})
```
`session.add(ficha)` + `commit` dentro del `try` de la Decisión 1; la respuesta es `FichaRead.model_validate(ficha)` (el `id` llega por el `RETURNING` del `INSERT`). Dueño inexistente → `23503` sobre la FK → **404** (la FK apunta al recurso de la ruta, PA-01); segunda ficha → `23505` sobre el UNIQUE → **409** (RN-03, caso C-03). Las dos situaciones no pueden darse a la vez: la FK garantiza que no hay fichas de dueños inexistentes.

**Alternativa**: leer el dueño con su ficha y responder 404 / 409 según lo leído (pre-chequeo prohibido por la consigna y con ventana de carrera; descartada).

### Decisión 10 — PA-09: mascotas del dueño con `selectinload` en la consulta del dueño
```python
duenio = (await session.exec(
    select(Duenio).where(Duenio.id == duenio_id).options(selectinload(Duenio.mascotas))
)).one_or_none()
if duenio is None: raise HTTPException(404, DUENIO_INEXISTENTE)
return [MascotaRead.model_validate(m) for m in sorted(duenio.mascotas, key=attrgetter("id"))]
```
- **Número fijo de consultas**: siempre dos (`SELECT duenio` + `SELECT mascota WHERE mascota.duenio_id IN (...)`), con 0, 1 o N mascotas; una sola si el dueño no existe (no hay padres para la segunda).
- **Distingue "no existe" (404) de "existe sin mascotas" (200 `[]`)** con la misma consulta, sin pregunta previa. Es una lectura, compatible con la regla de no pre-chequear escrituras (PA-09).
- Es la forma literal del Ej. 5: "toda respuesta que incluya datos de una relación los obtiene con carga anticipada declarada en la misma consulta … `selectinload` para colecciones".
- **Orden por `id`** en Python: `selectinload` no garantiza orden y la relación de C-02 no declara `order_by` (no se toca el modelo de C-02). Coincide con el orden por `id` que C-04 propone para `GET /mascotas/` (PA-12).

**Alternativas**: `select(Mascota).where(Mascota.duenio_id == id).order_by(Mascota.id)` y, si la lista sale vacía, una segunda consulta por el dueño para decidir 404 o `[]` (número de consultas variable según el resultado; descartada); `JOIN` manual dueño-mascota en una sola sentencia y armar la lista a mano (más código para ahorrar una consulta fija; descartada); agregar `order_by` a `Duenio.mascotas` (modifica el modelo de C-02; descartada).

### Decisión 11 — ⚠ `MascotaRead` mínimo en `app/modules/mascotas/schemas.py`, que C-04 reutiliza (APROBADA por Matheo, 2026-11-05)
"Mascotas del dueño" responde `list[MascotaRead]`, con `MascotaRead(SQLModel)`: `id: int`, `nombre: str`, `especie: str`, `duenio_id: int` (las columnas de `mascota`). Se crea **en el módulo `mascotas`** con sólo esa clase, y C-04 la reutiliza como respuesta de `POST /mascotas/` (US-007 la nombra `MascotaRead`) y como elemento de `items` del listado, agregando en el mismo archivo `MascotaCreate`, el detalle con dueño y el envoltorio.

- No se pisa con Lautaro/Uriel: C-04 arranca cuando C-03 está archivado (dependencia estricta en `CHANGES.md`), así que encuentran el archivo hecho y lo extienden.
- Un solo DTO por entidad: si C-04 cambia `MascotaRead`, cambia también esta respuesta, que es lo coherente.
- Desvío menor de D-9 de C-02 ("`schemas.py` lo crea el change de cada módulo"): este change crea el `schemas.py` de `mascotas` con un único DTO de salida, sin `service.py` ni `router.py`. Requiere el visto bueno de quien tome C-04.

**Alternativas**: un DTO local `MascotaDeDuenioRead` en `duenios/schemas.py` (duplicaría el contrato de mascota y C-04 tendría dos versiones del mismo dato; descartada); `id`, `nombre`, `especie` sin `duenio_id` (igual al anidado del turno del Ej. 4, pero ese es un DTO propio de C-06; acá `duenio_id` es redundante pero barato y hace que `MascotaRead` sirva tal cual a C-04; descartada).

### Decisión 12 — ⚠ DTO de `duenios` (`app/modules/duenios/schemas.py`) (APROBADA por Matheo, 2026-11-05)
| DTO | Campos | Configuración |
|-----|--------|---------------|
| `DuenioCreate` | `nombre: str = Field(min_length=1)`, `email: EmailStr` | `ConfigDict(extra="forbid", str_strip_whitespace=True)` |
| `DuenioUpdate` | `nombre: str \| None = Field(default=None, min_length=1)`, `email: EmailStr \| None = None` + `field_validator("nombre", "email")` que rechaza `None` | ídem |
| `DuenioRead` | `id: int`, `nombre: str`, `email: str` | salida (sin `extra="forbid"`) |
| `FichaRead` | `id: int`, `duenio_id: int`, `telefono: str`, `direccion: str` | salida |
| `DuenioConFichaRead(DuenioRead)` | `+ ficha: FichaRead \| None` | salida |
| `FichaCreate` | `telefono: str = Field(min_length=1)`, `direccion: str = Field(min_length=1)` | `ConfigDict(extra="forbid", str_strip_whitespace=True)` |

- **Todos heredan de `SQLModel` sin `table=True`** (como `EstadoSalud` de C-01) y no comparten clase base con los modelos de tabla (D-10 de C-02). Entre DTO sí hay herencia: `DuenioConFichaRead` extiende `DuenioRead`.
- **Sin `id`** en los DTO de alta (Ej. 2); `FichaCreate` tampoco lleva `duenio_id`: el dueño lo fija la ruta y, con `extra="forbid"`, mandarlo responde 422.
- **`POST /duenios/` responde `DuenioRead`** (lo que dice la tabla de endpoints) y GET/PATCH responden `DuenioConFichaRead` ("Dueño con su ficha"): un dueño recién creado no puede tener ficha, así que no se agrega un `"ficha": null` que la consigna no muestra.
- **`ficha` es objeto o `null`, nunca lista** (refleja `Duenio.ficha` con `uselist=False`).
- **`EmailStr`** (SU-05): `email-validator` ya viene con `fastapi[standard]` (verificado, punto 7), sin dependencia nueva. Normaliza el dominio a minúsculas: `ana.gomez@EXAMPLE.com` choca con `ana.gomez@example.com` (409). La parte local se conserva: `Ana.Gomez@example.com` y `ana.gomez@example.com` son emails distintos para el UNIQUE, como en el estándar (nada en la consigna pide otra cosa). En los `Read`, `email: str`: no se revalida lo que ya está guardado.
- **`str_strip_whitespace` + `min_length=1`**: `"   "` responde 422 en vez de guardar un nombre vacío; `"  Lucía  "` se guarda `"Lucía"`. Sin largo máximo (C-02 D-2 deja los textos sin largo; nada lo pide).
- **`null` explícito en el PATCH → 422**: con `str | None` a secas, `{"nombre": null}` llegaría a `setattr(None)` y la base lo rechazaría con `23502` (NOT NULL, sin `constraint_name`) → 409 genérico por la Decisión 2 (un `null` no es un conflicto con el estado de los datos, así que el contrato lo corta antes con 422). El `field_validator` sólo corre sobre valores enviados (Pydantic no valida los defaults), así que un campo omitido sigue fuera de `exclude_unset` (verificado, punto 8).

**Alternativas** para el `null`: anotar `nombre: str = Field(default=None, ...)` (Pydantic no valida el default, así que también rechaza `null` y OpenAPI muestra el campo como no anulable, pero la anotación miente para el tipado; descartada); aceptar `null` como "no cambiar" (`exclude_none`) (contradice `exclude_unset`, que la consigna nombra; descartada). Para el email: `str` con `pattern` (reinventa la validación; descartada); email en minúsculas completo (la consigna sólo pide unicidad; descartada).

### Decisión 13 — ⚠ Id de ruta `IdRuta` con cota superior 2147483647, en `app/core/parametros.py` (APROBADA con cambios por Matheo, 2026-11-05: sin `ge=1`)
```python
ENTERO_MAXIMO: Final = 2_147_483_647   # mayor valor de INTEGER (SERIAL) en PostgreSQL
IdRuta = Annotated[int, Path(le=ENTERO_MAXIMO, description="Id entero (máximo 2147483647)")]
```
- `"abc"` → 422 `int_parsing` antes del handler (caso C-01; verificado, puntos 5 y 11).
- Sin la cota superior, `/duenios/2147483648` pasa la validación de FastAPI, asyncpg no puede codificar el parámetro como `int4` y la petición termina en 500 (se confirma en el RED de la tarea 2.4). Con la cota responde 422. La cota existe únicamente para evitar ese desborde.
- **Sólo la cota superior, sin `ge=1`** (decisión de Matheo): `0` y los negativos son enteros que asyncpg codifica sin problema, así que el handler los ejecuta y la base responde sin filas → **404** `No existe el dueño`. Consecuencia visible: `/duenios/0` y `/duenios/-1` responden 404; sólo `/duenios/2147483648` (desborde de `int4`) y `/duenios/abc` responden 422.
- Vive en `app/core/` porque lo usan todos los módulos con `{id}` (C-04 `GET /mascotas/{id}`, C-06 `GET|DELETE /turnos/{id}`). `ENTERO_MAXIMO` queda disponible para los ids que viajan en el cuerpo (`duenio_id`, `mascota_id`, `practica_id`), decisión de cada change.

**Alternativas**: `id: int` a secas (más simple, pero deja el 500 por desborde; descartada); `ge=1` y `le` (`/duenios/0` → 422 sin consultar la base; propuesta original, descartada por Matheo a favor de sólo `le`); declararlo en `app/core/database.py` junto a `SessionDep` (mezcla validación HTTP con el motor y la sesión, que es lo único que la consigna asigna a ese archivo; descartada).

### Decisión 14 — Router delgado (`app/modules/duenios/router.py`) y registro
- `router = APIRouter(prefix="/duenios", tags=["duenios"])`; rutas `"/"`, `"/{id}"`, `"/{id}/ficha"`, `"/{id}/mascotas"` (las URL exactas de la consigna, con la barra final en `POST /duenios/`).
- Cada handler es `async def`, recibe `session: SessionDep`, `id: IdRuta` y, si corresponde, el DTO de entrada, y su cuerpo es una sola línea `return await service.<funcion>(session, id, ...)`. El parámetro se llama `id` (sombrea el builtin dentro del handler, sin efecto) para que OpenAPI muestre `{id}` como la consigna; el service lo recibe como `duenio_id`.
- Cada ruta declara `status_code` (201 / 200 / 204), `response_model` (y la misma anotación de retorno) y `responses` con `MensajeError` para sus 404/409. `DELETE` declara `status_code=204` y devuelve `None` (FastAPI no envía cuerpo).
- `from app.modules.duenios import service` y llamadas `service.<funcion>(...)`, igual que `health`: el test del caso C-01 reemplaza `service.obtener_duenio` con un espía vía `monkeypatch.setattr` (Decisión 17).
- `app/main.py`: `aplicacion.include_router(duenios_router)` después de `health_router` en `crear_app()`. La línea `from app.core import modelos` de C-02 sigue siendo la que registra todos los modelos antes de la primera consulta.

Firmas del service (todas `async def`, `session: AsyncSession` primero): `crear_duenio(session, datos) -> DuenioRead`, `obtener_duenio(session, duenio_id) -> DuenioConFichaRead`, `actualizar_duenio(session, duenio_id, datos) -> DuenioConFichaRead`, `borrar_duenio(session, duenio_id) -> None`, `crear_ficha(session, duenio_id, datos) -> FichaRead`, `listar_mascotas(session, duenio_id) -> list[MascotaRead]`.

### Decisión 15 — El service devuelve DTO armados dentro de la sesión
Cada función del service termina con `XRead.model_validate(obj)` (lectura por atributos, punto 6) y devuelve el DTO; el router nunca recibe un modelo de tabla. Además de cumplir "nunca devolver el modelo de tabla", hace que una relación no cargada falle **en el service, en el test**, con `MissingGreenlet` (la carga perezosa no puede ocurrir en async), en lugar de depender de cómo FastAPI serializa un objeto ORM.

### Decisión 16 — Transacciones: un `commit` por escritura, `rollback` ante el rechazo
- Cada escritura (`POST`, `PATCH`, `DELETE`, ficha) hace exactamente un `commit`; las lecturas (`GET`) no hacen `commit` (la transacción implícita se cierra al cerrar la sesión de `get_session`).
- Ante `IntegrityError`, `await session.rollback()` **antes** de responder: lo pide la consigna ("deshace la transacción") y, sin él, la sesión queda en estado `PendingRollbackError` para cualquier uso posterior en la misma petición.
- Nunca `asyncio.gather` sobre la misma sesión (`AsyncSession` no es segura para uso concurrente); cada operación es una secuencia de `await`.
- Un `INSERT` rechazado consume igual un valor de la secuencia (PostgreSQL no devuelve los `nextval`): los ids siguientes "saltan". Es esperado y se refleja en el `.http` (Decisión 19).

### Decisión 17 — Tests: archivos, fixtures y cómo se prueba cada propiedad
Todos con `pytestmark = pytest.mark.integracion`, contra `veterinaria_test` con el seed de C-02 (`base_con_seed`) y `client`; nunca mocks de la sesión ni de la base.

- **Fixture nueva `sentencias_app(app)`** en `tests/conftest.py`: lista llenada por un listener `before_cursor_execute` sobre `app.state.engine.sync_engine` (el motor de la aplicación; `sentencias_sql` de C-02 escucha `motor_test`, que la aplicación no usa), retirado en el teardown. Cada test la vacía (`.clear()`) justo antes de la petición que mide. No cuenta `BEGIN`/`COMMIT`/`ROLLBACK` (asyncpg los maneja fuera del cursor) ni la inicialización del dialecto (punto 9).
- **`tests/test_errores.py`** — el helper con errores reales de PostgreSQL (escrituras inválidas con `sesion` sobre `base_con_seed`): `restriccion_violada` devuelve `uq_duenio_email` (23505) y `ficha_duenio_duenio_id_fkey` (23503); `traducir_rechazo` con la restricción en el mapa → `HTTPException` con su código y mensaje; con un mapa que no la contiene → `HTTPException` 409 con `RECHAZO_GENERICO` y un `logger.warning` (verificado con `caplog`) que trae la restricción y el SQLSTATE pero no los valores; después del `rollback` la sesión vuelve a leer.
- **`tests/test_duenios.py`** — un test por escenario de `specs/duenios-y-fichas/spec.md`, parametrizando los cuerpos inválidos (≥2 casos por comportamiento); comprobaciones de estado con otra petición (`GET`) o con `sesion` (filas de `ficha_duenio`, `mascota`).
- **`tests/test_duenios_consultas.py`** — Ej. 5 y "sin pre-chequeos" con `sentencias_app`: detalle con y sin ficha → 1 sentencia que contiene `JOIN ficha_duenio`; mascotas con 1, 2 y 4 → 2 sentencias; PATCH → `SELECT` + `UPDATE`; POST con email repetido → sólo `INSERT INTO duenio`; ficha de dueño inexistente → sólo `INSERT INTO ficha_duenio`; DELETE (204, 404 y 409) → sólo `DELETE FROM duenio`.
- **Caso C-01 "sin ejecutar el handler"**: `monkeypatch.setattr(service, "obtener_duenio", espia)` con un espía `async` que registra las llamadas y delega en la función real; `GET /duenios/abc` → 422 y el espía sin llamadas y `sentencias_app` vacía; triangulación: `GET /duenios/1` → 200 y el espía con una llamada (prueba que el espía intercepta de verdad). Un espía sobre el service es la prueba correcta: `get_session` sí se ejecuta antes de validar la ruta (punto 5), así que "no se abrió sesión" no serviría.

### Decisión 18 — Archivos y alcance
Nuevos: `app/core/errores.py`, `app/core/parametros.py`, `app/modules/duenios/{schemas,service,router}.py`, `app/modules/mascotas/schemas.py`, `test/duenios.http`, `tests/test_errores.py`, `tests/test_duenios.py`, `tests/test_duenios_consultas.py`, `tests/test_duenios_http.py`. Modificados: `app/main.py` (una línea + import), `tests/conftest.py` (fixture `sentencias_app`), `tests/soporte.py` (helper `bloques_http`, Decisión 19). No se tocan los `models.py` de C-02, `reiniciar.py`, `app/core/database.py` ni `app/modules/laboratorio/`.

### Decisión 19 — `test/duenios.http`: casos en orden, después de `python reiniciar.py`
Mismo formato que `test/health.http` (`@base = http://localhost:8000`, `### título`, `# Esperado: ...`, cabecera `Content-Type: application/json` en los que llevan cuerpo). Un comentario inicial indica: correr **en orden y una sola vez** después de `python reiniciar.py`; las peticiones marcadas **[modifica]** cambian el estado y las siguientes dependen de ellas; volver a correrlo exige `python reiniciar.py` (supuesto SU-04; PA-07 lo cierra C-08).

| # | Petición | Esperado (comentario) |
|---|----------|-----------------------|
| 1 | **Caso C-01** `GET /duenios/abc` | 422, `detail[0]` con `"type": "int_parsing"`, `"loc": ["path", "id"]`; el handler no se ejecuta |
| 2 | `GET /duenios/1` | 200 Ana Gómez con `"ficha": {"id": 1, "duenio_id": 1, "telefono": "11 5555-0101", "direccion": "Calle Falsa 123"}` |
| 3 | `GET /duenios/2` | 200 Carlos Ruiz con `"ficha": null` |
| 4 | `GET /duenios/999` | 404 `{"detail": "No existe el dueño"}` |
| 5 | `GET /duenios/1/mascotas` | 200 `[Toby (id 1), Mishi (id 2)]` con `duenio_id` 1 |
| 6 | `GET /duenios/999/mascotas` | 404 `{"detail": "No existe el dueño"}` |
| 7 | **[modifica]** `POST /duenios/` Lucía Fernández `lucia.fernandez@example.com` | 201 `{"id": 3, ...}` |
| 8 | `GET /duenios/3/mascotas` | 200 `[]` (existe, sin mascotas) |
| 9 | **Caso C-02** `POST /duenios/` con `ana.gomez@example.com` | 409 `{"detail": "Ya existe un dueño con ese email"}` (consume el id 4 de la secuencia) |
| 10 | `POST /duenios/` con `"id": 7` | 422 `extra_forbidden` en `["body", "id"]` |
| 11 | **[modifica]** `PATCH /duenios/3` `{"nombre": "Lucía F."}` | 200, email sin cambios, `"ficha": null` |
| 12 | `PATCH /duenios/3` `{"email": "ana.gomez@example.com"}` | 409 `{"detail": "Ya existe un dueño con ese email"}` |
| 13 | `PATCH /duenios/3` `{"nombre": null}` | 422 |
| 14 | **[modifica]** `POST /duenios/3/ficha` | 201 `{"id": 2, "duenio_id": 3, ...}` |
| 15 | **Caso C-03** `POST /duenios/1/ficha` | 409 `{"detail": "El dueño ya tiene una ficha"}` |
| 16 | `POST /duenios/999/ficha` | 404 `{"detail": "No existe el dueño"}` |
| 17 | **Caso C-05 (primera parte)** `DELETE /duenios/1` | 409 `{"detail": "No se puede borrar el dueño: tiene mascotas a su nombre"}` |
| 18 | `GET /duenios/1` | 200 igual que el #2 (el 409 no borró nada) |
| 19 | **[modifica]** `DELETE /duenios/3` | 204 sin cuerpo (su ficha 2 cae por CASCADE) |
| 20 | `GET /duenios/3` | 404 `{"detail": "No existe el dueño"}` |
| 21 | `DELETE /duenios/3` | 404 `{"detail": "No existe el dueño"}` |

Para que el entregable no se desincronice del código (como hace C-02 con el `.sql` del caso C-08), `tests/test_duenios_http.py` verifica que el archivo existe, que contiene los cuatro casos de la consigna y que cada bloque `###` tiene su `# Esperado:`, y además **lo ejecuta**: un helper `bloques_http(ruta)` en `tests/soporte.py` separa los bloques (método, URL, cabeceras, cuerpo y el primer código de `# Esperado:`) y el test los envía en orden con `client` sobre `base_con_seed`, comparando el código de estado. La tarea final, además, corre cada petición con `curl` contra `uvicorn` y compara código y cuerpo con el comentario. C-08 puede reutilizar el helper para los `.http` de todos los módulos.

## Risks / Trade-offs

- [C-02 todavía en `apply`: si cambia un nombre de restricción o de relación, la traducción de errores falla] → la tarea 0 exige C-02 completo y verde; los nombres están fijados por sus tests de introspección, y los tests de este change verifican cada 404/409 con su mensaje exacto (un nombre distinto daría el 409 genérico de la Decisión 2 en lugar del mensaje esperado, y el test lo detecta; además queda el `warning` en el log).
- [Carrera PATCH ∥ DELETE del mismo dueño: entre el `SELECT` y el `UPDATE` otra petición lo borra; el `UPDATE` no encuentra la fila y el ORM lanza `StaleDataError` → 500] → aceptado: la ventana es mínima, la consigna no la evalúa y la alternativa (`.with_for_update(of=Duenio)` en la lectura del PATCH, o atrapar `StaleDataError` → 404) agrega complejidad al patrón que copia el equipo. Se documenta como mejora posible.
- [La normalización de `EmailStr` es del DTO, no de la base: un `INSERT` por SQL directo con el dominio en mayúsculas no choca con el UNIQUE] → la consigna sólo exige la unicidad, que la base garantiza; la normalización es una comodidad del contrato HTTP.
- [Las secuencias avanzan con los `INSERT` rechazados (409/404): los ids del `.http` y de los tests dependen del orden] → los tests arrancan siempre de `base_con_seed` y fijan los ids esperados; el `.http` documenta el orden y los saltos (Decisión 19).
- [`IdRuta` sin `ge=1`: `/duenios/0` y `/duenios/-1` ejecutan el handler y responden 404 tras una consulta que no encuentra nada] → costo aceptado por Matheo a cambio de no inventar un rango que la consigna no pide; queda en el spec (`contrato-de-errores`) y en esta decisión para que C-04..C-06 lo sepan.
- [El espía del caso C-01 depende de que el router llame `service.obtener_duenio` por el módulo] → es la forma fijada en la Decisión 14 (igual que `health`); si alguien importara la función directa, el test de triangulación (`GET /duenios/1` registra la llamada) falla y lo avisa.
- [`passive_deletes="all"` no se ejercita desde el `DELETE` del dueño (Decisión 7)] → lo prueban los tests de C-02 con `session.delete`; el criterio del Ej. 3 se evalúa sobre los modelos.

## Migration Plan

Sin migración de datos: el esquema y el seed son de C-02. Puesta en marcha: C-02 aplicado, `docker compose up -d`, `python reiniciar.py`, `uvicorn app.main:app`. Vuelta atrás: los archivos de este change son nuevos salvo `app/main.py` (una línea) y `tests/conftest.py` (una fixture), que se revierten con git.
