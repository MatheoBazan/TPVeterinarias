## Why

Después de C-03 la API expone dueños y fichas, pero una mascota sólo se puede ver como parte de su dueño (`GET /duenios/{id}/mascotas`): no hay forma de darla de alta, de leerla con su dueño ni de recorrer el listado completo. Este change implementa el módulo `mascotas` sobre el patrón que fijó C-03 (router delgado, DTO separados, service que escribe sin preguntar y traduce el rechazo de la base) y cubre tres criterios de la consigna a la vez: el **alta con relación por id** (Ej. 4), el **envoltorio de paginación** (Ej. 2) y la **lectura de la mascota con su dueño sin N+1** (Ej. 5). Va ahora porque C-03 está archivado (GATE 3 de `CHANGES.md`) y C-08 lo exige para el 100 % de la nota.

## What Changes

- **Tres endpoints de la consigna** ("Endpoints de referencia" del PDF), todos `async def`:

  | Método | Ruta | Cuerpo / parámetros | Respuesta | Códigos |
  |--------|------|---------------------|-----------|---------|
  | POST | `/mascotas/` | `MascotaCreate` | `MascotaRead` | 201, 409, 422 |
  | GET | `/mascotas/` | `page`, `size` (query) | Envoltorio con mascotas | 200, 422 |
  | GET | `/mascotas/{id}` | — | Mascota con su dueño | 200, 404, 422 |

- **Alta con el id del dueño en el cuerpo** (agregación, Ej. 4): `MascotaCreate` lleva `nombre`, `especie` y `duenio_id`, sin `id`, y rechaza campos no declarados (422). El service escribe sin consultar antes si el dueño existe; si la base rechaza el `INSERT` por la clave foránea `mascota_duenio_id_fkey`, deshace la transacción y responde **409** con mensaje propio (caso C-04 de la consigna, primera parte). A diferencia de la ficha de C-03 (dueño en la **ruta** → 404), acá el dueño viaja en el **cuerpo** y el recurso de la ruta existe: por eso es 409, como fija la consigna.
- **Listado paginado** `GET /mascotas/?page=&size=` con el envoltorio `{items, total, page, size, pages}`: `size` 20 por defecto y entre 1 y 100; `page` desde 1; una página más allá de `pages` responde **422**; la primera página responde siempre, aun sin mascotas (`items: []`, `total: 0`, `pages: 0`). Orden estable por `id`.
- **Detalle con el dueño** `GET /mascotas/{id}`: la mascota y su dueño en **una sola consulta** (`joinedload`, relación "a uno"); 404 con mensaje propio si no existe; id no entero o sobre la cota → 422 sin ejecutar el handler (contrato de C-03).
- **Número fijo de consultas**: alta → sólo el `INSERT`; detalle → 1 sentencia; listado → 2 sentencias (conteo + página) cualquiera sea el tamaño de la página; página fuera de rango → sólo el conteo.
- **DTO** en `app/modules/mascotas/schemas.py`: se **conserva sin cambios** `MascotaRead` (creada por C-03, D-11, que ya usa `GET /duenios/{id}/mascotas`) y se agregan a su lado `MascotaCreate`, el detalle "mascota con su dueño" (reutiliza `DuenioRead`) y el envoltorio de la página.
- **Registro del router** de `mascotas` en `crear_app()`.
- **Entregable de la cátedra**: `test/mascotas.http` con el caso C-04 (primera parte) de la consigna y los caminos felices y bordes de la paginación, cada uno con la respuesta esperada en un comentario, ejecutable en orden después de `python reiniciar.py`.
- **Tests pytest** (TDD estricto contra PostgreSQL real): paginación (vacía, en el borde, fuera de rango, `page`/`size` inválidos), 409 por FK sin consulta previa, 422 por campos extra o inválidos, 404, y conteo de sentencias del detalle y del listado.

**Fuera de alcance**: editar o borrar mascotas (la consigna no los pide), filtros u orden configurable del listado, paginar otros recursos; el caso C-04 segunda parte (turno con práctica inexistente) es de C-06; prácticas (C-05), turnos (C-06), laboratorio (C-07). Sin cambios al esquema ni al seed (C-02).

## Capabilities

### New Capabilities
- `mascotas`: el recurso mascota de la API: alta con el id de un dueño existente (rechazo de la base por clave foránea → 409), detalle de la mascota con su dueño, listado paginado con su envoltorio y sus reglas de rango, y lecturas con un número fijo de consultas.

### Modified Capabilities
- (ninguna: `contrato-de-errores` ya define el cuerpo de 404/409, la traducción de rechazos sin consultas previas, el formato de los 422 y el id de ruta para **todo** `{id}`; este change los cumple sin cambiar sus requisitos. `duenios-y-fichas` no cambia: `GET /duenios/{id}/mascotas` sigue respondiendo el mismo `MascotaRead`)

## Impact

- **Ejercicio / peso**: Ej. 2 — Contratos y CRUD (parte del **20 %**: DTO separados, códigos HTTP, **envoltorio de paginación**); Ej. 4 — Altas con relaciones (parte del **15 %**: "el alta de una mascota recibe el `duenio_id` de un dueño que ya existe: en la agregación viaja un id"); Ej. 5 — Lecturas sin N+1 (parte del **15 %**: mascota con su dueño con carga anticipada y número fijo de consultas).
- **Reglas de negocio**: regla derivada "mascota con dueño inexistente → 409 (violación de FK), no 404/422" (KB 05); sin consultas previas (consigna, regla dura 3). Ninguna RN-01..RN-09 nueva: RN-08 (`ON DELETE RESTRICT` de `mascota.duenio_id`) ya la cubre C-03.
- **Casos de la consigna**: **C-04 primera parte** (mascota con un dueño inexistente → 409). También ejercita el contrato del caso C-01 en `GET /mascotas/abc`.
- **Preguntas abiertas resueltas**: **PA-05** (`pages = 0` cuando `total = 0`; `page = 1` responde siempre; `page > max(pages, 1)` → 422) y **PA-12** (listado ordenado por `id` ascendente).
- **Código nuevo**: `app/modules/mascotas/service.py`, `app/modules/mascotas/router.py`, `test/mascotas.http`, tests nuevos en `tests/` (`test_mascotas.py`, `test_mascotas_paginacion.py`, `test_mascotas_consultas.py`, `test_mascotas_http.py`).
- **Código modificado**: `app/modules/mascotas/schemas.py` (se agregan DTO; `MascotaRead` intacto), `app/main.py` (registra el router; el change paralelo C-05 agrega en el mismo lugar el de `practicas`: conflicto de una línea, trivial).
- **No se tocan**: `app/modules/mascotas/models.py` y los demás modelos de C-02, `reiniciar.py`, `app/core/*` (se reutilizan `traducir_rechazo`, `Rechazo`, `MensajeError`, `IdRuta`, `ENTERO_MAXIMO`, `SessionDep`), el módulo `duenios` (se reutilizan `DuenioRead` y `ENTRADA`), `tests/conftest.py` y `tests/soporte.py` (se reutilizan `base_con_seed`, `esquema_vacio`, `sesion`, `client`, `sentencias_app`, `bloques_http`).
- **Dependencias**: ninguna nueva. Requisito previo: C-03 (`duenios-fichas`) archivado y en verde.
- **Governance**: MEDIO — lógica de paginación y alta con relación: implementar con checkpoints y revisar las decisiones marcadas ⚠ del design antes del `apply`.
