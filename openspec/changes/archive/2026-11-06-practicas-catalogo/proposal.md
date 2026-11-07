## Why

Después de C-03 la API expone dueños y fichas, pero el catálogo de prácticas sólo existe en la base (lo carga `reiniciar.py`): no hay forma de darlo de alta ni de consultarlo por HTTP. Este change implementa el módulo `practicas` y completa, para el catálogo, el **Ejercicio 2 — Contratos y CRUD (20 %)**. Va ahora porque C-03 ya fijó el patrón (router delgado, DTO separados, service que escribe sin preguntar y traduce el rechazo de la base) y porque C-06 (`turnos-composicion`) copia el precio de cada práctica del catálogo: conviene que el contrato del precio (`Decimal`, mayor que cero, serializado como string con 2 decimales) quede fijado antes.

## What Changes

- **Dos endpoints de la consigna** (tabla de endpoints, filas 12 y 13), con sus códigos exactos y handlers `async def`:

  | Método | Ruta | Cuerpo | Respuesta | Códigos |
  |--------|------|--------|-----------|---------|
  | POST | `/practicas/` | `PracticaCreate` | `PracticaRead` | 201, 409, 422 |
  | GET | `/practicas/` | — | Catálogo de prácticas (`list[PracticaRead]`) | 200 |

- **DTO separados del modelo de tabla** en `app/modules/practicas/schemas.py`: `PracticaCreate` (sin `id`; `nombre` y `precio`; rechaza campos no declarados con 422) y `PracticaRead` (`id`, `nombre`, `precio`). El modelo `Practica` de C-02 no se toca.
- **RN-04 en el contrato**: `precio` es `Decimal` (nunca `float`) y debe ser mayor que cero → **422** si es `0` o negativo, validado en el DTO antes de llegar a la base. La base mantiene su `CHECK (precio > 0)` como segundo garante (caso C-08 de la consigna).
- **RN-02 garantizada por la base, sin consulta previa**: el service inserta; si el nombre ya existe, la base rechaza la escritura por su restricción UNIQUE, el service atrapa el `IntegrityError`, deshace la transacción y responde **409** con un mensaje propio (helper `traducir_rechazo` de C-03).
- **Dinero como string con 2 decimales** en las respuestas (`"15000.00"`), igual en el alta y en el listado.
- **Registro del router** en `crear_app()`.
- **Entregable de la cátedra**: `test/practicas.http` con el caso **C-02** de la consigna en su parte de prácticas (nombre repetido → 409 con mensaje propio), los caminos felices y los 422 del precio, cada uno con la respuesta esperada en un comentario, ejecutable en orden después de `python reiniciar.py`; más las **notas de ejecución del caso C-08** (cómo correr `test/c08_check_precio.sql` y cómo comprobar por HTTP que el precio no cambió).
- **Tests pytest** (TDD estricto contra PostgreSQL real): 201, 409 por nombre duplicado (con rollback y sin `SELECT` previo), 422 por precio ≤ 0 y por campos extra, `Decimal` serializado como string, listado completo en orden y con una sola consulta, y ejecución del `.http`.

**Fuera de alcance**: editar o borrar prácticas (la consigna no define esos endpoints), paginación o filtros del catálogo, turnos y precio congelado (C-06), cambios al esquema o al seed (C-02). Sin autenticación, repositorios ni Unit of Work.

## Capabilities

### New Capabilities
- `catalogo-de-practicas`: los dos endpoints del catálogo de prácticas (alta y listado) con sus contratos de entrada y salida, sus códigos HTTP, la regla RN-02 garantizada por la base (409 sin consulta previa) y RN-04 validada en el contrato (422) y en la base (CHECK, caso C-08).

### Modified Capabilities
- (ninguna: `contrato-de-errores` ya cubre el cuerpo de los 409 y la traducción de rechazos, y este change sólo lo reutiliza; `esquema-relacional` y `datos-iniciales` se usan tal cual)

## Impact

- **Ejercicio / peso**: Ej. 2 — Contratos y CRUD (**parte del 20 %**: DTO separados, códigos HTTP) para el catálogo de prácticas.
- **Reglas de negocio**: **RN-02** (nombre de práctica único → 409, garante: UNIQUE `uq_practica_nombre` en la base) y **RN-04** (precio mayor que cero → 422 en el DTO; `CHECK ck_practica_precio_positivo` en la base).
- **Casos de la consigna**: **C-02** en su parte de prácticas (nombre de práctica repetido → 409 con mensaje propio) y **C-08** (notas de ejecución del `.sql` que ya existe y verificación por HTTP de que el precio no cambió).
- **Preguntas abiertas**: ninguna de `knowledge-base/10_preguntas_abiertas.md` es propia de este change. Reutiliza lo resuelto en C-03: **PA-01** (traducción por nombre de restricción) y **PA-11** (cuerpo `{"detail": "..."}`). **PA-07** (orden y estado previo de los `.http`) sigue abierta para C-08; este change aplica la misma convención que `test/duenios.http` (correr en orden, una sola vez, después de `python reiniciar.py`).
- **Código nuevo**: `app/modules/practicas/{schemas,service,router}.py`, `test/practicas.http`, `tests/test_practicas.py`, `tests/test_practicas_http.py`.
- **Código modificado**: `app/main.py` (registra el router de `practicas`).
- **Sin cambios**: `app/modules/practicas/models.py`, `reiniciar.py`, `app/core/errores.py`, `app/core/database.py`, `test/c08_check_precio.sql` (ya documentado y probado por C-02).
- **Dependencias**: ninguna nueva.
- **Requisito previo**: C-03 (`duenios-fichas`) archivado: `app/core/errores.py` (`Rechazo`, `traducir_rechazo`, `MensajeError`), fixtures `base_con_seed`, `client`, `sentencias_app` y helper `bloques_http`.
- **Contrato para los changes siguientes**: C-06 lee `practica.precio` para copiarlo a `turno_practica.precio_unitario`; el formato del dinero en la respuesta (string con 2 decimales) queda fijado acá.
- **Governance**: BAJO — catálogo con dos endpoints que replican el patrón de C-03; autonomía completa si los tests pasan.
