## Why

Después de C-02 la base tiene las seis tablas con sus restricciones, pero la API no expone ningún recurso: no hay forma de dar de alta, leer, editar ni borrar dueños, ni de cargar su ficha. Este change implementa el módulo `duenios` y cubre el **Ejercicio 2 — Contratos y CRUD (20 %)** para dueños y fichas, más la parte del dueño del **Ejercicio 5 — Lecturas sin N+1 (15 %)** ("lo mismo vale para el [detalle] de un dueño con su ficha"). Va ahora porque está en el camino crítico (`C-01 → C-02 → C-03 → C-06 → C-08`) y porque **fija el patrón de referencia** —router delgado, DTO separados, service que escribe sin preguntar y traduce el rechazo de la base— que Lautaro y Uriel copian en C-04, C-05 y C-06.

## What Changes

- **Seis endpoints de la consigna**, con sus códigos exactos (todos los handlers `async def`):

  | Método | Ruta | Cuerpo | Respuesta | Códigos |
  |--------|------|--------|-----------|---------|
  | POST | `/duenios/` | `DuenioCreate` | `DuenioRead` | 201, 409, 422 |
  | GET | `/duenios/{id}` | — | Dueño con su ficha | 200, 404, 422 |
  | PATCH | `/duenios/{id}` | `DuenioUpdate` | Dueño con su ficha | 200, 404, 409, 422 |
  | DELETE | `/duenios/{id}` | — | — | 204, 404, 409 |
  | POST | `/duenios/{id}/ficha` | `FichaCreate` | `FichaRead` | 201, 404, 409 |
  | GET | `/duenios/{id}/mascotas` | — | Mascotas del dueño | 200, 404 |

- **DTO separados de los modelos de tabla** en `app/modules/duenios/schemas.py`: `DuenioCreate` (sin `id`), `DuenioUpdate` (todo opcional, sólo se aplica lo enviado con `exclude_unset`), `DuenioRead`, el detalle "dueño con su ficha", `FichaCreate` (sin `id` ni `duenio_id`: el dueño viene de la ruta) y `FichaRead`. Los DTO de entrada rechazan campos no declarados (422). Además, la salida mínima de una mascota (`MascotaRead`) para `GET /duenios/{id}/mascotas`, que C-04 reutiliza.
- **Escribir y que decida la base, sin consultas previas** ("¿ya existe?"): el service escribe; si la base rechaza, atrapa el `IntegrityError`, deshace la transacción y responde con un mensaje propio:
  - email repetido → **409** (RN-01, `uq_duenio_email`), en el alta y en el PATCH;
  - segunda ficha del mismo dueño → **409** (RN-03, `uq_ficha_duenio_duenio_id`);
  - ficha para un dueño inexistente → **404** (la clave foránea apunta al recurso de la ruta);
  - borrar un dueño con mascotas → **409** (RN-08, `ON DELETE RESTRICT`); sin mascotas → **204** y la ficha cae por `ON DELETE CASCADE` en la base.
- **Helper reutilizable de traducción de rechazos** en `app/core/`: identifica la restricción violada a partir del error de PostgreSQL y la convierte en el código y mensaje que cada operación declara. C-04..C-06 lo usan pasando sus propias restricciones, sin editar el código de este change.
- **Formato único de error** `{"detail": "<mensaje propio>"}` para 404 y 409 (el mismo que FastAPI usa para sus errores) y contrato de los ids de ruta: un id que no es entero (o fuera del rango de los ids) responde **422 sin ejecutar el handler**.
- **Lecturas con carga anticipada y número fijo de consultas**: el detalle del dueño trae la ficha en la misma consulta (`joinedload`, relación "a uno"); las mascotas del dueño, con `selectinload` (colección). Nunca carga perezosa.
- **Registro del router** en `crear_app()`.
- **Entregable de la cátedra**: `test/duenios.http` con los casos C-01, C-02 (email), C-03 y C-05 (primera parte) de la consigna y los caminos felices, cada uno con la respuesta esperada en un comentario, ejecutables en orden después de `python reiniciar.py`.
- **Tests pytest** (TDD estricto contra PostgreSQL real): cada código HTTP de cada endpoint, PATCH parcial, rollback ante 409, ausencia de consultas previas y conteo de consultas del detalle (con y sin ficha) y de las mascotas del dueño.

**Fuera de alcance**: `POST /mascotas/`, `GET /mascotas/` y `GET /mascotas/{id}` (C-04, que extiende `MascotaRead`); prácticas (C-05); turnos (C-06); laboratorio (C-07); cambios al esquema o al seed (C-02). Sin autenticación, repositorios ni Unit of Work.

## Capabilities

### New Capabilities
- `duenios-y-fichas`: los seis endpoints del recurso dueño (alta, detalle con ficha, edición parcial, borrado, alta de ficha y mascotas del dueño) con sus contratos de entrada y salida, sus códigos HTTP, las reglas RN-01, RN-03 y RN-08 garantizadas por la base y las lecturas con un número fijo de consultas.
- `contrato-de-errores`: comportamiento transversal que reutilizan todos los módulos: el cuerpo de los errores 404/409, la traducción de un rechazo de la base a 404/409 con mensaje propio y rollback sin consultas previas, que un rechazo no previsto no se disfrace de 409, y el 422 de un id de ruta inválido sin ejecutar el handler.

### Modified Capabilities
- (ninguna: `conexion-y-ciclo-de-vida` y `salud-del-servicio` no cambian sus requisitos; las capacidades de C-02, `esquema-relacional` y `datos-iniciales`, sólo se usan)

## Impact

- **Ejercicio / peso**: Ej. 2 — Contratos y CRUD (**20 %**: DTO separados, códigos HTTP, PATCH parcial) para dueños y fichas; Ej. 5 — Lecturas sin N+1 (**15 %**) para el detalle del dueño con su ficha.
- **Reglas de negocio**: RN-01 (email único → 409), RN-03 (una ficha por dueño → 409), RN-08 (no se borra un dueño con mascotas → 409). Las tres sin consulta previa.
- **Casos de la consigna**: **C-01** (`/duenios/abc` → 422 sin ejecutar el handler), **C-02** en su parte de email (409 con mensaje propio), **C-03** (segunda ficha → 409), **C-05** primera parte (borrar un dueño con mascotas → 409).
- **Preguntas abiertas resueltas**: **PA-01** (distinguir sin pre-chequeo la clave foránea del recurso de la ruta → 404 de la unicidad → 409, por el nombre de la restricción que informa PostgreSQL), **PA-09** (`GET /duenios/{id}/mascotas` responde 404 si el dueño no existe y `[]` si existe sin mascotas, con un número fijo de consultas), **PA-11** (cuerpo de error `{"detail": "..."}`).
- **Código nuevo**: `app/modules/duenios/{schemas,service,router}.py`, `app/modules/mascotas/schemas.py` (sólo `MascotaRead`), `app/core/errores.py` (traducción de rechazos y cuerpo de error), `app/core/parametros.py` (id de ruta), `test/duenios.http`, tests nuevos en `tests/`.
- **Código modificado**: `app/main.py` (registra el router de `duenios`), `tests/conftest.py` (fixture que captura las sentencias del motor de la aplicación), `tests/soporte.py` (helper que lee y ejecuta los bloques de un `.http`).
- **Dependencias**: ninguna nueva (`email-validator`, necesaria para validar el email, ya la instala `fastapi[standard]`).
- **Requisito previo**: C-02 (`modelos-esquema-seed`) aplicado y en verde: modelos `Duenio`, `FichaDuenio`, `Mascota` con sus relaciones, nombres de restricciones, `reiniciar.py` y fixtures `base_con_seed` / `sesion`.
- **Contrato para los changes siguientes**: el helper de traducción de rechazos, el cuerpo de error, el id de ruta y `MascotaRead`; la forma router/service/schemas que copian C-04..C-06.
- **Governance**: MEDIO — lógica de negocio y patrón que se replica: Matheo revisa las decisiones marcadas ⚠ del design antes del `apply`.
