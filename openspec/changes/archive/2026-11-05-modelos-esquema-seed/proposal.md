## Why

Después de C-01 la API tiene motor, sesión y salud, pero ninguna tabla: los módulos de dueños, mascotas, prácticas y turnos (C-03..C-06) no tienen dónde escribir, y la consigna **no corrige** un proyecto que no crea su esquema con `python reiniciar.py` sobre una base vacía. Este change cubre el **Ejercicio 3 — Modelos, restricciones y relaciones (30 % de la nota, el criterio de mayor peso)**: "lado de cada clave foránea, uno a uno con UNIQUE, tabla intermedia con su dato, RESTRICT y CASCADE, CHECK, índices y su justificación, navegación en los dos extremos". Además deja la base como garante de las reglas de negocio que los changes siguientes traducen a 409 sin consultas previas.

## What Changes

- **Seis modelos de tabla** con los nombres obligatorios de la consigna, en sus módulos:
  - `app/modules/duenios/models.py`: `Duenio` → tabla `duenio` (`id`, `nombre`, `email`) y `FichaDuenio` → tabla `ficha_duenio` (`id`, `duenio_id`, `telefono`, `direccion`).
  - `app/modules/mascotas/models.py`: `Mascota` → tabla `mascota` (`id`, `nombre`, `especie`, `duenio_id`).
  - `app/modules/practicas/models.py`: `Practica` → tabla `practica` (`id`, `nombre`, `precio` NUMERIC(10,2)).
  - `app/modules/turnos/models.py`: `Turno` → tabla `turno` (`id`, `mascota_id`, `fecha` con zona horaria, `motivo`, `total` NUMERIC(12,2)) y `TurnoPractica` → tabla `turno_practica` (`turno_id`, `practica_id`, `precio_unitario` NUMERIC(10,2)).
  - Cada módulo nuevo lleva sólo `__init__.py` y `models.py`; sus `schemas.py`, `service.py` y `router.py` los crea el change de ese módulo (C-03..C-06).
- **Restricciones en la base** (todas creadas por `create_all`, sin DDL a mano):
  - UNIQUE: `duenio.email` (RN-01), `practica.nombre` (RN-02), `ficha_duenio.duenio_id` (RN-03, relación uno a uno).
  - CHECK: `practica.precio > 0` (RN-04), `turno.total >= 0`, `turno_practica.precio_unitario > 0` (RN-06).
  - Clave primaria compuesta `turno_practica (turno_id, practica_id)` (RN-07).
  - Claves foráneas con su regla de borrado: `mascota.duenio_id` RESTRICT (RN-08), `turno_practica.turno_id` CASCADE (RN-09), y las que la consigna no fija (PA-02, aprobadas): `ficha_duenio.duenio_id` CASCADE, `turno.mascota_id` RESTRICT, `turno_practica.practica_id` RESTRICT.
  - Índices en `mascota.duenio_id`, `turno.mascota_id` y `turno_practica.practica_id`; **ninguno propio** en `turno_practica.turno_id` (lo sirve la clave primaria compuesta).
  - Dinero con `Decimal` (columnas `NUMERIC`), nunca `float`; `NOT NULL` en todas las columnas de la consigna.
- **Navegación en los dos extremos** de cada una de las cinco claves foráneas con `Relationship(back_populates=...)`: `Duenio.ficha` ↔ `FichaDuenio.duenio` (`Duenio.ficha` devuelve un objeto, no una lista), `Duenio.mascotas` ↔ `Mascota.duenio`, `Mascota.turnos` ↔ `Turno.mascota`, `Turno.practicas` ↔ `TurnoPractica.turno`, `Practica.turnos` ↔ `TurnoPractica.practica`.
- **El borrado lo decide la base**: `Turno.practicas` (y el lado "uno" de las otras cuatro claves foráneas) se declara con `passive_deletes` para que el ORM no cargue, no vacíe ni borre las filas hijas: la base aplica `ON DELETE CASCADE` o rechaza con `RESTRICT`.
- **Registro único de modelos** que importan `reiniciar.py`, la aplicación y los tests, para que `create_all` vea las seis tablas y las relaciones entre módulos se resuelvan.
- **`reiniciar.py`** en la raíz: borra las tablas, las crea con `create_all` y carga los datos iniciales (PA-03, aprobado) en una sola transacción; funciona sobre una base vacía y se puede repetir. Deja la base en el estado del que parte el ejemplo de `POST /turnos/` del Ej. 4 (el turno del ejemplo recibe id 2 y total `"27000.00"`).
- **Entregable de la cátedra**: `test/c08_check_precio.sql` con `UPDATE practica SET precio = 0`, que la base rechaza por el CHECK (caso C-08 de la consigna), con el error esperado y cómo ejecutarlo en un comentario.
- **README**: completa la sección "Índice de `turno_practica.turno_id`" (1–2 líneas) y quita la marca "disponible desde C-02" del paso `python reiniciar.py`.
- **Tests pytest** (TDD estricto, PostgreSQL real `veterinaria_test`): introspección del esquema (nombres, tipos, restricciones, reglas de borrado, índices) y comportamiento (la base rechaza UNIQUE/CHECK/FK, RESTRICT bloquea, CASCADE borra sin que el ORM emita `DELETE` de las hijas, carga anticipada de las relaciones, seed exacto, `reiniciar.py` sobre base vacía).

**Fuera de alcance**: DTO, services, routers y endpoints (C-03..C-07); la traducción de `IntegrityError` a 409/404 (C-03, PA-01); la evidencia del caso C-07 (C-06); `.http` de endpoints (cada change de módulo). Sin Alembic, repositorios ni Unit of Work.

## Capabilities

### New Capabilities
- `esquema-relacional`: las seis tablas de la consigna con sus columnas, tipos, claves primarias, claves foráneas con regla de borrado, UNIQUE, CHECK e índices; la navegación ORM en ambos extremos y el borrado decidido por la base (`passive_deletes`).
- `datos-iniciales`: `python reiniciar.py` recrea el esquema sobre una base vacía o existente y carga el seed exacto que reproduce el ejemplo del Ej. 4; el `.sql` del caso C-08 de la consigna.

### Modified Capabilities
- (ninguna: las capacidades de C-01, `conexion-y-ciclo-de-vida` y `salud-del-servicio`, no cambian sus requisitos; este change sólo reutiliza `cargar_configuracion`, `crear_motor` y `crear_fabrica_sesiones`)

## Impact

- **Ejercicio / peso**: Ej. 3 — Modelos, restricciones y relaciones, **30 %**. Habilita el Ej. 4 (el seed fija los ids del ejemplo de `POST /turnos/`).
- **Reglas de negocio con garante en la base**: RN-01, RN-02, RN-03, RN-04 (lado base; el DTO lo hace C-05), RN-06 (CHECK de `total` y `precio_unitario`; copiar el precio lo hace C-06), RN-07, RN-08, RN-09.
- **Casos de la consigna**: **C-08** (cerrado: `.sql` + test). Deja lista la base para C-02, C-03, C-04 y C-05 (sus 409/204 los producen los endpoints de C-03..C-06).
- **Condición de corrección**: "crea su esquema con `python reiniciar.py` sobre una base vacía".
- **Preguntas abiertas resueltas**: **PA-02** (ON DELETE de `ficha_duenio.duenio_id` CASCADE, `turno.mascota_id` RESTRICT, `turno_practica.practica_id` RESTRICT — aprobado por Matheo) y **PA-03** (seed exacto — aprobado por Matheo).
- **Código nuevo**: `app/modules/{duenios,mascotas,practicas,turnos}/{__init__,models}.py`, `app/core/modelos.py` (registro de modelos), `reiniciar.py`, `test/c08_check_precio.sql`, tests nuevos en `tests/`.
- **Código modificado** (archivos de C-01): `app/main.py` (una línea: importa el registro de modelos), `tests/conftest.py` (fixtures de esquema y seed), `tests/soporte.py` (helper para leer el error de PostgreSQL detrás de un `IntegrityError`), `README.md`.
- **Dependencias**: ninguna nueva.
- **Contrato para los changes siguientes**: modelos y relaciones con estos nombres; nombres estables de restricciones (`uq_duenio_email`, `uq_practica_nombre`, `uq_ficha_duenio_duenio_id`, `ck_*`, `<tabla>_<columna>_fkey`, `turno_practica_pkey`) para que C-03 traduzca errores por `constraint_name` / SQLSTATE; fixtures `esquema_vacio` y `base_con_seed` en `tests/conftest.py`.
- **Governance**: ALTO — define el esquema del que dependen todos los demás changes. Matheo revisa el design antes del `apply`.
