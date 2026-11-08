# Design — turnos-composicion (C-06)

## Context

- El esquema ya existe (C-02): `turno` (`ck_turno_total_no_negativo`, `turno_mascota_id_fkey` RESTRICT) y `turno_practica` (PK compuesta `turno_practica_pkey` = (`turno_id`, `practica_id`), `turno_practica_turno_id_fkey` CASCADE, `turno_practica_practica_id_fkey` RESTRICT, `ck_turno_practica_precio_unitario_positivo`, `precio_unitario NOT NULL`). `Turno.practicas` tiene `passive_deletes="all"`. El seed deja el turno 1 (Mishi, prácticas 1 y 2, total 23000.00), así que el ejemplo del PDF recibe el id 2.
- Patrón a copiar (C-03..C-05): router de una línea por ruta; service que escribe primero y traduce el `IntegrityError` con `traducir_rechazo` y un mapa `RECHAZOS_*` por nombre de restricción; DTO en `schemas.py` con `ENTRADA` (`extra="forbid"`, `str_strip_whitespace=True`); `IdRuta` para `{id}`; `MensajeError` para documentar 404/409.
- Infraestructura de tests: `base_con_seed`, `client`, `sentencias_app` (captura de SQL del motor de la app), `sesion_seed`, `bloques_http` para correr un `.http` en orden.

## Goals / Non-Goals

**Goals:**
- Que el rechazo de una práctica inexistente lo decida la base **en la misma sentencia que escribe**, sin una lectura previa del catálogo (regla dura 3) y sin ventana de carrera entre "leer el precio" y "escribir".
- Respuesta byte a byte igual al ejemplo del PDF.
- Lecturas en 2 sentencias `SELECT` fijas.

**Non-Goals:**
- Listado de turnos, modificación de un turno o de sus prácticas (la consigna no los pide).
- Cambios en `models.py`, `reiniciar.py` o `app/core/errores.py`.

## Decisions

### D-1 — El precio lo copia la base en un único `INSERT … SELECT` (práctica inexistente → `NOT NULL`)

Secuencia del alta, toda en una transacción:

1. `INSERT INTO turno (mascota_id, fecha, motivo, total) VALUES (…, 0)` vía ORM (`session.add` + `flush`). Mascota inexistente → `turno_mascota_id_fkey`.
2. Una sola sentencia para todas las prácticas, con los ids pedidos como arreglo:
   ```sql
   INSERT INTO turno_practica (turno_id, practica_id, precio_unitario)
   SELECT :turno_id, pedida.practica_id, practica.precio
   FROM unnest(:ids) WITH ORDINALITY AS pedida(practica_id, orden)
   LEFT JOIN practica ON practica.id = pedida.practica_id
   ORDER BY pedida.orden
   RETURNING precio_unitario
   ```
   - Práctica inexistente → el `LEFT JOIN` deja `precio` en `NULL` → la base rechaza con `not_null_violation` (SQLSTATE 23502) sobre `turno_practica.precio_unitario`.
   - Práctica repetida → dos filas con la misma PK → `turno_practica_pkey` (23505). El DTO no la mira (RN-07).
3. `turno.total = sum(precios devueltos)` con `Decimal` y `commit` (el ORM emite el `UPDATE turno`).

Cualquier `IntegrityError` en 1–3 → `rollback` → 409. No queda nada: ni turno ni prácticas.

**Alternativas descartadas:**
- *Leer los precios con un `SELECT … WHERE id IN (…)` y responder 409 si falta alguno* — es la consulta previa "¿ya existe?" que prohíbe la regla dura 3; además, si el catálogo cambia entre la lectura y la escritura, el precio copiado o la decisión pueden quedar viejos.
- *Leer los precios y, para una práctica faltante, escribir un precio de relleno para que dispare la FK* — si la práctica se crea entre la lectura y la escritura, el relleno quedaría guardado como precio real.
- *`INNER JOIN` y comparar la cantidad de filas insertadas con las pedidas* — la decide la aplicación, no una restricción de la base.

Con D-1 el precio se lee y se escribe en la misma sentencia (no hay ventana) y quien rechaza es una restricción de la base. Costo: el garante de "práctica inexistente" es el `NOT NULL` de `precio_unitario` y no la FK `turno_practica_practica_id_fkey`; se documenta con un comentario en el service y la FK sigue mapeada por si acaso (D-2).

### D-2 — Traducción de rechazos del alta

`RECHAZOS_ALTA` en `turnos/service.py`:

| Restricción | HTTP | Mensaje |
|---|---|---|
| `turno_mascota_id_fkey` | 409 | `No existe la mascota indicada` |
| `turno_practica_pkey` | 409 | `Una práctica no puede repetirse en el mismo turno` |
| `turno_practica_practica_id_fkey` | 409 | `No existe la práctica indicada` (defensivo; con D-1 no debería dispararse) |

`traducir_rechazo` busca por `constraint_name`, que un `NOT NULL` no informa. Un helper local del service mira primero la excepción de asyncpg (`exc.orig.__cause__`): si es `NotNullViolationError` con `column_name == "precio_unitario"` → 409 `No existe la práctica indicada`; si no, delega en `traducir_rechazo(exc, RECHAZOS_ALTA)` (que mantiene el 409 genérico con log para lo no previsto). No se toca `app/core/errores.py`: el spec `contrato-de-errores` ya permite que cada operación declare sus rechazos.

### D-3 — Contratos (`schemas.py`)

- `PracticaDeTurnoCreate`: `practica_id: int = Field(le=ENTERO_MAXIMO)`, `ENTRADA`.
- `TurnoCreate`: `mascota_id: int = Field(le=ENTERO_MAXIMO)`, `fecha: AwareDatetime`, `motivo: str = Field(min_length=1)`, `practicas: list[PracticaDeTurnoCreate] = Field(min_length=1)`, `ENTRADA`. Sin `id`, precio ni total.
  - `le=ENTERO_MAXIMO` evita el desborde int32 de asyncpg (500), igual que `duenio_id` en C-04. `0` y negativos llegan a la base y responden 409.
- `MascotaDeTurnoRead {id, nombre, especie}` (propio de turnos: el ejemplo no muestra `duenio_id`, así que no se reutiliza `MascotaRead`).
- `PracticaDeTurnoRead {practica_id, nombre, precio_unitario}`.
- `TurnoRead {id, fecha, motivo, total, mascota, practicas}` en el orden del ejemplo. `field_serializer("fecha")` → `valor.astimezone(UTC)`, así siempre sale con `Z`. `Decimal` se serializa como string (`NUMERIC(…, 2)` ya trae dos decimales).

**PA-10**: `AwareDatetime` → una fecha sin zona responde 422 en el DTO. Alternativa descartada: asumir UTC (C-02 ya advirtió que asyncpg tomaría la hora local de la máquina; asumir una zona silenciosamente cambia la hora del turno).

**PA-13**: mascota inexistente → 409 por la FK (D-2), igual que el caso C-04 de la consigna. Alternativa descartada: 404 (la mascota no es un recurso de la ruta, y obligaría a consultarla antes).

### D-4 — Lectura con carga anticipada (2 `SELECT` fijos)

```python
select(Turno).where(Turno.id == turno_id).options(
    joinedload(Turno.mascota),
    selectinload(Turno.practicas).joinedload(TurnoPractica.practica),
).execution_options(populate_existing=True)
```

- Sentencia 1: `turno JOIN mascota`. Sentencia 2: `turno_practica JOIN practica WHERE turno_id IN (…)`. Siempre 2, con 1 o con 30 prácticas.
- `populate_existing=True` porque el alta reutiliza esta lectura en la misma sesión: el `Turno` recién insertado ya está en el identity map con `practicas` sin cargar (se insertaron por Core) y `fecha` con el desplazamiento original. Sin la opción, el 201 podría salir con la lista vacía.
- Orden de `practicas`: por `practica_id`, ordenando en Python al armar el `TurnoRead`. Alternativa descartada: `order_by` en la relación (modifica `models.py` de C-02 por un detalle de presentación).
- Respuesta armada a mano desde el turno (`a_lectura(turno) -> TurnoRead`): el `nombre` sale de `tp.practica.nombre` y el `precio_unitario` de `turno_practica` (precio congelado, RN-06).

### D-5 — El 201 relee el turno

Tras el `commit`, `crear_turno` devuelve `obtener_turno(session, turno.id)`. Son 2 `SELECT` más, pero el 201 y el `GET` salen del mismo código y de lo que quedó guardado (fecha normalizada por la base, nombres del catálogo). Alternativa descartada: armar la respuesta en memoria (habría que pedir los nombres en el `RETURNING` y normalizar la fecha a mano).

### D-6 — Borrado

Igual que `borrar_duenio`: `DELETE FROM turno WHERE id = :id`; `rowcount == 0` → 404; si no, `commit` → 204. La base borra `turno_practica` por CASCADE (RN-09); el ORM no carga ni borra las hijas. Sin `try/except IntegrityError`: nada referencia a `turno` con RESTRICT.

### D-7 — `test/turnos.http` y evidencia del caso C-07

Mismo formato que los `.http` existentes. Se corre una vez, en orden, tras `python reiniciar.py`:

1. Caso C-06: el ejemplo del PDF → 201 con id 2 (tiene que ir primero: un alta rechazada también consume un valor de la secuencia).
2. `[modifica]` turno con una práctica (id 3) y con tres (id 4).
3. Caso C-07: `GET /turnos/3` y `GET /turnos/4` → 200.
4. Caso C-04 (segunda parte): práctica 999 → 409; `GET /turnos/5` → 404 (no quedó nada).
5. Práctica repetida → 409; lista vacía → 422; fecha sin zona → 422.
6. Caso C-05 (segunda parte): `DELETE /turnos/1` → 204; `GET /turnos/1` → 404.

Un comentario de cabecera explica la evidencia del caso C-07: `SQL_ECHO=1` en `.env` (PA-08, resuelta en C-01), levantar uvicorn, pedir `GET /turnos/3` y `GET /turnos/4` y ver en la consola dos `SELECT` en cada uno. Juntar las capturas en el README es tarea de C-08.

## Risks / Trade-offs

- [El garante de "práctica inexistente" es el `NOT NULL` y no la FK; quien lea el código puede no entenderlo] → comentario en el service apuntando a D-1, test que fija el mensaje y la FK sigue en el mapa.
- [`column_name` es un atributo de la excepción de asyncpg, no de SQLAlchemy] → el mismo acceso que ya usa `restriccion_violada` (`exc.orig.__cause__`); un test lo cubre.
- [Un alta rechazada consume ids de `turno`] → normal en PostgreSQL; el `.http` pone primero el caso C-06 para que salga el id 2.
- [`populate_existing` pisa cambios sin confirmar del turno en la sesión] → la lectura se usa sólo después de un `commit` o en una petición de sólo lectura.

## Migration Plan

Sin migración: no cambia el esquema. Despliegue = `python reiniciar.py` + `uvicorn`, como hasta ahora.
