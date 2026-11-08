# Proposal — turnos-composicion (C-06)

## Why

El turno es el agregado central de la consigna y todavía no tiene API: no se puede reservar, consultar ni borrar. Cubre el **Ej. 4 — Altas con relaciones (15 %)** completo y la parte de turnos del **Ej. 5 — Lecturas sin N+1 (15 %)**, y es el último change del camino crítico antes de la entrega (C-08). El esquema (`turno`, `turno_practica`, sus restricciones y el seed que reproduce el ejemplo del PDF) ya existe desde C-02.

## What Changes

- `POST /turnos/` — reserva un turno con sus prácticas anidadas (`{"mascota_id", "fecha", "motivo", "practicas": [{"practica_id"}]}`), en **una sola transacción, todo o nada**:
  - el precio de cada práctica se copia del catálogo a `turno_practica.precio_unitario` y el `total` lo calcula el servidor; ni precio ni total viajan en el DTO (RN-06);
  - lista de prácticas vacía → **422** en el DTO (RN-05);
  - práctica inexistente → **409** y no queda guardado nada (caso C-04 de la consigna, segunda parte);
  - práctica repetida en el mismo turno → **409** por la clave primaria compuesta de `turno_practica`, no por el DTO (RN-07);
  - mascota inexistente → **409** por la clave foránea (PA-13);
  - `fecha` sin zona horaria → **422** (PA-10);
  - **201** con el formato exacto del ejemplo del PDF: `fecha` en UTC con `Z`, dinero como string con dos decimales, `mascota {id, nombre, especie}`, `practicas [{practica_id, nombre, precio_unitario}]` (caso C-06 de la consigna).
- `GET /turnos/{id}` — detalle con mascota (`joinedload`) y prácticas (`selectinload` + `joinedload` de la práctica para el nombre) en un número fijo de consultas, independiente de la cantidad de prácticas; **404** si no existe (caso C-07 de la consigna).
- `DELETE /turnos/{id}` — **204**; las filas de `turno_practica` las borra la base por `ON DELETE CASCADE` (RN-09); **404** si no existe (caso C-05 de la consigna, segunda parte).
- Módulo `app/modules/turnos/` completo: `schemas.py`, `service.py`, `router.py` (el `models.py` ya existe), y registro del router en `app/main.py`.
- `test/turnos.http` con los casos C-04 (segunda parte), C-05 (segunda parte), C-06 y C-07 de la consigna, y las instrucciones para la evidencia de consola del caso C-07 con `SQL_ECHO=1` (PA-08 ya resuelta en C-01).
- Tests pytest en `tests/` contra PostgreSQL real.

Sin cambios de esquema: no se agregan ni modifican tablas ni columnas.

## Capabilities

### New Capabilities
- `turnos`: reserva de turnos con sus prácticas (precio congelado, total del servidor, todo o nada), detalle con carga anticipada y borrado en cascada delegado a la base.

### Modified Capabilities
- Ninguna. El contrato de errores (`contrato-de-errores`) ya prevé que cada operación declare sus propios rechazos; turnos lo reutiliza sin cambiar sus requisitos.

## Reglas, casos y preguntas abiertas

- **Reglas**: RN-05, RN-06, RN-07, RN-09.
- **Casos de la consigna**: C-04 (segunda parte), C-05 (segunda parte), C-06, C-07.
- **Preguntas abiertas que resuelve**: **PA-10** (`fecha` sin zona → 422), **PA-13** (`mascota_id` inexistente → 409). **PA-08** ya está resuelta (`SQL_ECHO`, C-01); este change sólo documenta su uso para la evidencia del caso C-07.

## Impact

- **Código nuevo**: `app/modules/turnos/{schemas,service,router}.py`; una línea en `app/main.py` para registrar el router.
- **Sin tocar**: `models.py` de turnos, `reiniciar.py`, `app/core/errores.py` y los módulos de C-03..C-05.
- **API**: tres rutas nuevas bajo `/turnos`.
- **Tests**: `tests/test_turnos*.py` y `test/turnos.http`.
- **Dependencias**: ninguna nueva.
