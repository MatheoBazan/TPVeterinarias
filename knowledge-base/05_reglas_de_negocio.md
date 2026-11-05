# Reglas de Negocio

Códigos de la consigna: `RN-01`..`RN-09`. Regla general: **ninguna se verifica con una consulta previa "¿ya existe?"**. Se escribe; si la base rechaza, el service atrapa `IntegrityError`, hace rollback y responde 409 con mensaje propio (entre la pregunta y la escritura otra petición puede escribir lo mismo; la única defensa real es la base — sec. 4.10).

## Dominio: Dueños y fichas

- **RN-01**: El email de un dueño es único. — Garante: UNIQUE en la base; 409.
- **RN-03**: Un dueño tiene como máximo una ficha. — Garante: UNIQUE en `ficha_duenio.duenio_id`; 409.
- **RN-08**: No se puede borrar un dueño que tenga mascotas a su nombre. — Garante: `ON DELETE RESTRICT`; 409.

## Dominio: Catálogo de prácticas

- **RN-02**: El nombre de una práctica es único. — Garante: UNIQUE en la base; 409.
- **RN-04**: El precio de una práctica es mayor que cero. — Garante: CHECK en la base **y** validación del DTO.

## Dominio: Turnos

- **RN-05**: Un turno se reserva con sus prácticas: viajan dentro del cuerpo del alta y tiene al menos una. — Garante: DTO anidado; 422 si la lista está vacía (`min_length=1`).
- **RN-06**: El precio de cada práctica se copia del catálogo al reservar el turno, y el total lo calcula el servidor. — Garante: ni el precio ni el total viajan en el DTO. Los turnos ya reservados no cambian si el catálogo cambia (precio congelado en `turno_practica.precio_unitario`).
- **RN-07**: Una misma práctica no aparece dos veces en un turno. — Garante: clave primaria compuesta de `turno_practica`; 409. **No** rechazar en el DTO.
- **RN-09**: Al borrar un turno se borran sus prácticas. — Garante: `ON DELETE CASCADE` en la base (no el ORM).

## Reglas derivadas / comportamiento exigido por las consignas

- Mascota con dueño inexistente → **409** (violación de FK), no 404/422 (C-04).
- Turno con una práctica inexistente → 409 y **no queda guardado nada** (ni turno ni prácticas): una sola transacción, todo o nada (Ej. 4).
- Param de ruta no entero (p. ej. `/duenios/abc`) → 422 sin ejecutar el handler (C-01).
- Insertar `precio = 0` directo en la base es rechazado por el CHECK (C-08).
- Dinero con `Decimal`; `total >= 0` (CHECK); `precio_unitario > 0` (CHECK).

## Matriz regla → garante → código HTTP

| Regla | Base de datos | DTO / service | HTTP |
|-------|---------------|---------------|------|
| RN-01 | UNIQUE `duenio.email` | catch `IntegrityError` | 409 |
| RN-02 | UNIQUE `practica.nombre` | catch `IntegrityError` | 409 |
| RN-03 | UNIQUE `ficha_duenio.duenio_id` | catch `IntegrityError` | 409 |
| RN-04 | CHECK `precio > 0` | validación DTO (`gt=0`) | 422 (DTO) |
| RN-05 | — | DTO anidado `min_length=1` | 422 |
| RN-06 | CHECK `total >= 0`, `precio_unitario > 0` | servicio copia precio y calcula total | — |
| RN-07 | PK (`turno_id`, `practica_id`) | catch `IntegrityError` | 409 |
| RN-08 | `ON DELETE RESTRICT` | catch `IntegrityError` | 409 |
| RN-09 | `ON DELETE CASCADE` + `passive_deletes` | — | 204 |

## Excepciones globales

- Toda escritura rechazada por la base: rollback + 409 con mensaje propio.
- Distinguir violación de FK sobre un recurso de la ruta (404) de UNIQUE/otras (409) sin pre-chequeo: punto abierto (PA-01 en `10`).
