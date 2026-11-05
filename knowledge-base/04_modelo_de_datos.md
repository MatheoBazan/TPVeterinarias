# Modelo de Datos

Los nombres de tablas y columnas son **obligatorios** (la corrección los usa). Se pueden **agregar** columnas, no quitar ni renombrar las indicadas. Se crean con `SQLModel.metadata.create_all` (sin Alembic). Dinero: `Decimal`, nunca `float`.

## Dominios

- Clientes: `duenio`, `ficha_duenio`.
- Pacientes: `mascota`.
- Catálogo: `practica`.
- Agenda y facturación del turno: `turno`, `turno_practica`.

## Relaciones (por qué es de ese tipo — consigna)

| Relación | Entre | Razón |
|----------|-------|-------|
| Uno a uno | Dueño y ficha | Un dueño tiene como máximo una ficha: clave foránea más unicidad (sec. 4.3 del curso) |
| Agregación | Dueño y mascota | La mascota existe por sí misma y puede cambiar de dueño; mientras un dueño tenga mascotas a su nombre, no se puede borrar |
| Asociación | Turno y mascota | El turno conoce a la mascota que se atiende, pero ninguno es parte del otro |
| Composición | Turno y sus prácticas | Una práctica reservada no tiene sentido sin su turno: nace con él y se borra con él |
| Muchos a muchos con datos | Turno y práctica | Un turno lleva varias prácticas y una práctica figura en muchos turnos; el precio cobrado es de la relación, no de la práctica |

Figura 1 (diagrama de clases): rombo vacío = agregación, rombo lleno = composición, flecha = asociación. `TurnoPractica` es la clase intermedia entre turno y práctica y guarda el precio cobrado en ese turno.

Transcripción de la Figura 1 (verificada contra la imagen de la página 4 del PDF):

| Clase | Atributos |
|-------|-----------|
| `Duenio` | `int id`, `str nombre`, `str email` |
| `FichaDuenio` | `int id`, `str telefono`, `str direccion` |
| `Mascota` | `int id`, `str nombre`, `str especie` |
| `Turno` | `int id`, `datetime fecha`, `str motivo`, `Decimal total` |
| `TurnoPractica` | `Decimal precio_unitario` |
| `Practica` | `int id`, `str nombre`, `Decimal precio` |

| Asociación en el diagrama | Extremo A (mult.) | Extremo B (mult.) | Notación |
|---------------------------|-------------------|-------------------|----------|
| "1 a 1" | `Duenio` 1 | `FichaDuenio` 0..1 | línea simple |
| "agregación" | `Duenio` 1 (rombo vacío) | `Mascota` 0..* | rombo vacío del lado de `Duenio` |
| "asociación" | `Turno` 0..* | `Mascota` 1 | flecha hacia `Mascota` |
| "composición" | `Turno` 1 (rombo lleno) | `TurnoPractica` 1..* | rombo lleno del lado de `Turno` |
| "asociación" | `TurnoPractica` 0..* | `Practica` 1 | flecha hacia `Practica` |

Las FK no figuran como atributos en el diagrama: aparecen recién en la traducción al esquema (tabla siguiente), del lado "muchos" / del lado dependiente de cada relación.

## ERD

```
duenio 1 ──── 0..1 ficha_duenio         (FK ficha_duenio.duenio_id, UNIQUE)
duenio 1 ──◇─ 0..* mascota              (FK mascota.duenio_id, ON DELETE RESTRICT)   agregación
mascota 1 ─── 0..* turno                (FK turno.mascota_id)                         asociación
turno 1 ──◆── 1..* turno_practica       (FK turno_practica.turno_id, ON DELETE CASCADE) composición
practica 1 ── 0..* turno_practica       (FK turno_practica.practica_id)               M:N con datos
```

## Entidades (tabla de la consigna)

### `duenio`
- Columnas: `id`, `nombre`, `email`.
- Restricciones: `email` UNIQUE (RN-01).
- Relaciones: `ficha` (uno, `uselist=False`), `mascotas` (lista).

### `ficha_duenio`
- Columnas: `id`, `duenio_id`, `telefono`, `direccion`.
- Restricciones: `duenio_id` UNIQUE (RN-03; crea su propio índice).
- ON DELETE de `duenio_id`: **no especificado por la consigna** → propuesta CASCADE (DD-05; abierta en `10`).

### `mascota`
- Columnas: `id`, `nombre`, `especie`, `duenio_id`.
- Restricciones: `duenio_id` con **ON DELETE RESTRICT** (RN-08); **índice en `duenio_id`**.

### `practica`
- Columnas: `id`, `nombre`, `precio` (NUMERIC(10,2)).
- Restricciones: `nombre` UNIQUE (RN-02); **CHECK `precio > 0`** (RN-04).

### `turno`
- Columnas: `id`, `mascota_id`, `fecha` (TIMESTAMP **con zona horaria**), `motivo`, `total` (NUMERIC(12,2)).
- Restricciones: **CHECK `total >= 0`**; **índice en `mascota_id`**.
- ON DELETE de `mascota_id`: no especificado → propuesta RESTRICT (DD-06; abierta en `10`).

### `turno_practica`
- Columnas: `turno_id`, `practica_id`, `precio_unitario` (NUMERIC(10,2)).
- Restricciones: **clave primaria compuesta (`turno_id`, `practica_id`)** (RN-07); `turno_id` con **ON DELETE CASCADE** (RN-09); **CHECK `precio_unitario > 0`**; **índice en `practica_id`**.
- ON DELETE de `practica_id`: no especificado → propuesta RESTRICT (DD-07; abierta en `10`).

## Índices y su justificación

PostgreSQL **no crea solo** el índice de una clave foránea (sec. 4.10), por eso la consigna los pide:

| Índice | Origen |
|--------|--------|
| `mascota.duenio_id` | explícito (consigna) |
| `turno.mascota_id` | explícito (consigna) |
| `turno_practica.practica_id` | explícito (consigna) |
| `ficha_duenio.duenio_id` | implícito: lo crea la restricción UNIQUE |
| `duenio.email`, `practica.nombre` | implícitos: UNIQUE |
| `turno_practica (turno_id, practica_id)` | implícito: PK compuesta |

**Por qué `turno_practica.turno_id` NO lleva índice propio** (el README debe explicarlo en 1-2 líneas): `turno_id` es la **columna más a la izquierda** de la clave primaria compuesta (`turno_id`, `practica_id`); el índice B-tree de la PK ya sirve las búsquedas, joins y el borrado en cascada por `turno_id`. Un índice adicional sería redundante.

## Navegación ORM

- Cada relación se declara en **ambos extremos** con `Relationship(back_populates=...)`.
- `Duenio.ficha` devuelve un **objeto** (`uselist=False`), no una lista.
- `Turno.practicas` (hacia `TurnoPractica`) se declara con **`passive_deletes="all"`** (igual que los otros cuatro lados "uno") para que el ORM no intente vaciar ni borrar esas filas, estén o no cargadas: lo hace la base con ON DELETE CASCADE (RN-09). `"all"` y no `True`: ver D-7 de `openspec/changes/modelos-esquema-seed/design.md`.

## Seed data inicial (`reiniciar.py`)

Mínimo de la consigna: dos dueños (uno con ficha), tres mascotas, cuatro prácticas, un turno con dos prácticas.

Restricción derivada del ejemplo de respuesta de `POST /turnos/` (Ej. 4) — el seed debe reproducirlo:

| Dato | Valor requerido por el ejemplo |
|------|--------------------------------|
| `mascota` id 1 | nombre "Toby", especie "perro" |
| `practica` id 1 | "Consulta", precio 15000.00 |
| `practica` id 3 | "Vacuna antirrábica", precio 12000.00 |
| `turno` del seed | id 1 (así el turno del ejemplo recibe id 2) |

El orden de inserción de prácticas debe fijar esos ids; las prácticas 2 y 4 son libres (**Suposición:** p. ej. "Desparasitación" y otra). `reiniciar.py` borra las tablas, las crea con `create_all` y carga estos datos; debe funcionar sobre una base vacía. Los ids autoincrementales deben reiniciarse (drop/create las recrea).
