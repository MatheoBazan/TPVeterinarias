## Context

Motivación y alcance en `proposal.md`; comportamiento exigido en `specs/esquema-relacional/spec.md` y `specs/datos-iniciales/spec.md`.

Estado de partida (C-01 `base-proyecto-conexion`, en `apply` mientras se escribe este design; código ya en disco y leído):

- `app/core/config.py`: `cargar_configuracion() -> Configuracion(database_url, sql_echo)`, `ConfiguracionInvalida`; `load_dotenv(RAIZ_PROYECTO / ".env")` al importar, con `override=False`.
- `app/core/database.py`: `crear_motor(config)`, `crear_fabrica_sesiones(engine)` (`AsyncSession` de `sqlmodel.ext.asyncio.session`, `expire_on_commit=False`), `get_session`, `SessionDep`.
- `app/main.py`: `lifespan` + `crear_app()` + `app`; el arranque no crea el esquema.
- Tests: `pytest.ini` (`asyncio_mode = auto`, loops y fixtures de scope `function`, marcador `integracion`, `pythonpath = .`), `tests/conftest.py` (`url_base_test`, `app`, `client`), `tests/soporte.py` (`validar_url_de_test`, `levantar_app`, `cliente_de`). La base de tests se llama `veterinaria_test` y el guard exige el sufijo `_test`.
- `docker-compose.yml`: servicio `db` (`postgres:16`), puerto host 5433 por defecto, `./docker/initdb` montado; **no** monta `test/`.
- Versiones instaladas (venv de Matheo, Python 3.14.7): `sqlmodel==0.0.48`, `sqlalchemy==2.0.57`, `asyncpg==0.32.0`, `pydantic==2.14.3`.

Restricciones que condicionan el diseño: reglas duras 1 (esquema intocable, `create_all`, sin Alembic), 3 (la base es el garante; `passive_deletes`; `Decimal`), 4 (lecturas eager), 6 (DTO separados), 8 (nombres en español sin ñ), 9 (PostgreSQL real), 10 (`reiniciar.py` sobre base vacía) de `AGENTS.md`.

**Verificado antes de decidir** (context7 + código fuente instalado en `.venv`):

- SQLModel, tutorial "Cascade Delete Relationships": `ondelete` va en el `Field(foreign_key=...)` del lado con la clave foránea; `cascade_delete=True` en `Relationship` se traduce a `cascade="all, delete-orphan"`; para RESTRICT el tutorial usa `passive_deletes="all"` y advierte que sin él "SQLModel (SQLAlchemy) will load and update the heroes before deleting the team, set their foreign key to NULL".
- SQLAlchemy 2.0, `relationship.passive_deletes`: `True` = no cargar las hijas *no cargadas* durante el borrado, pero "rows that are locally present will still be subject to explicit SET NULL or DELETE"; `"all"` = "disable **all** related object update/delete". `sqlalchemy/orm/relationships.py` lanza `ArgumentError` si se combina `passive_deletes="all"` con cascada `delete`/`delete-orphan`; `orm/dependency.py` (`OneToManyDP.presort_deletes`): `should_null_fks = not self.cascade.delete and not self.passive_deletes == "all"`; `orm/sync.py` lanza `AssertionError("... tried to blank-out primary key column ...")` si el ORM intenta poner en NULL una columna de clave primaria.
- `sqlmodel/main.py` 0.0.48: el `__tablename__` por defecto es `cls.__name__.lower()`; `Field(foreign_key=..., ondelete=...)` genera `ForeignKey(foreign_key, ondelete=...)` **sin nombre**; las anotaciones de relación se envuelven en `Mapped[...]`; `datetime` sin `sa_type` se mapea a `UTCDateTime()` (un `TypeDecorator` sobre `DateTime(timezone=True)` que rechaza fechas sin zona) — **ya no** a `TIMESTAMP WITHOUT TIME ZONE` como en versiones anteriores; `str` → `AutoString` (`VARCHAR` sin largo); `Decimal` con `max_digits`/`decimal_places` → `Numeric(p, s)`; los modelos `table=True` **no validan** en el constructor (`sqlmodel_table_construct`).
- SQLModel, tutorial "Code Structure": relaciones entre archivos con `if TYPE_CHECKING:` y anotaciones `Optional["Team"]` / `list["Hero"]` como cadenas.

**Entorno al momento del propose**: `docker compose ps` falla al parsear `docker-compose.yml` (línea 5, col. 58: el valor `${POSTGRES_USER:?Falta POSTGRES_USER: copia env.example a .env}` contiene `": "` sin comillas, inválido en YAML). Es un archivo de C-01 y se reporta a ese change; la tarea 0 de este change verifica que esté corregido.

## Goals / Non-Goals

**Goals:**
- Que todas las reglas con garante "base" (RN-01..RN-04, RN-06..RN-09) se puedan demostrar escribiendo directo en la base, sin pasar por la aplicación.
- Que los nombres de tablas, columnas y restricciones sean un contrato estable y verificado por tests, para que C-03..C-06 traduzcan errores por `constraint_name` / SQLSTATE sin adivinar.
- Que ningún borrado hecho a través del ORM dependa de lo que haya cargado en la sesión: siempre decide la base.
- Que `python reiniciar.py` sea la única forma de crear el esquema y deje siempre los mismos ids.

**Non-Goals:**
- Validaciones de contenido que la consigna no pide en la base (largo máximo de textos, textos vacíos, formato de email, fecha futura): son del DTO de cada módulo.
- Columnas adicionales (`creado_en`, borrado lógico, etc.).
- Tipos `ENUM` para `especie`: texto libre como en la consigna.
- Carga de datos de ejemplo más allá del mínimo aprobado (PA-03).
- `lazy="raise"` u otras protecciones contra la carga perezosa: la sesión asincrónica ya la impide (`MissingGreenlet`) y la evidencia de consultas es del caso C-07 (C-06).

## Decisions

### Decisión 1 — `__tablename__` explícito en los seis modelos
SQLModel nombra la tabla con el nombre de la clase en minúsculas: `FichaDuenio` → `fichaduenio` y `TurnoPractica` → `turnopractica`, que **no** son los nombres obligatorios. Cada modelo declara `__tablename__` (también los cuatro en los que coincidiría: `duenio`, `mascota`, `practica`, `turno`), para que el nombre de la tabla se lea en el código y no dependa de una convención de la biblioteca.

**Alternativas**: declararlo sólo en los dos modelos compuestos (menos líneas, pero el nombre de cuatro tablas quedaría implícito y atado al nombre de la clase; descartada); `sa_column`/`Table` explícita (descartada: abandona el estilo de SQLModel que enseña la cátedra).

### Decisión 2 — Tipos de columna y nulabilidad
| Columna | Anotación y `Field` | Tipo en PostgreSQL |
|---------|---------------------|--------------------|
| `id` (5 tablas) | `int \| None = Field(default=None, primary_key=True)` | `INTEGER` con secuencia (`SERIAL`), `NOT NULL` |
| textos (`nombre`, `email`, `especie`, `telefono`, `direccion`, `motivo`) | `str` | `VARCHAR` sin largo, `NOT NULL` |
| `practica.precio`, `turno_practica.precio_unitario` | `Decimal = Field(sa_type=Numeric(10, 2))` | `NUMERIC(10,2)`, `NOT NULL` |
| `turno.total` | `Decimal = Field(sa_type=Numeric(12, 2))` | `NUMERIC(12,2)`, `NOT NULL` |
| `turno.fecha` | `datetime = Field(sa_type=DateTime(timezone=True))` | `TIMESTAMP WITH TIME ZONE`, `NOT NULL` |
| claves foráneas | `int = Field(foreign_key=..., ondelete=...)` (no opcional) | `INTEGER`, `NOT NULL` |
| `turno_practica.turno_id` / `practica_id` | `int \| None = Field(default=None, primary_key=True, foreign_key=..., ondelete=...)` | `INTEGER`, `NOT NULL` (por ser PK) |

- **Sin valores por defecto en la base** (ni `server_default`): `total` lo calcula el service (RN-06) y `fecha` la manda el cliente. Un `INSERT` incompleto falla con `23502` en vez de inventar un valor.
- **Textos sin largo**: en PostgreSQL `VARCHAR` sin largo equivale a `TEXT` (skill `postgresql-table-design`: preferir `TEXT` a `VARCHAR(n)`); la consigna no fija largos. Si un módulo quiere acotar, lo hace en su DTO.
- **Dinero con `sa_type=Numeric(p, s)`** (estándar del proyecto en `.atl/skill-registry.md`): se lee igual que la consigna ("NUMERIC 10,2"). `Field(max_digits=10, decimal_places=2)` genera la misma columna (verificado en `get_sqlalchemy_type`) y queda como alternativa equivalente; se elige una sola forma para los tres campos. `Numeric` devuelve `Decimal` (asyncpg lo entrega así), nunca `float`.
- ⚠ **`fecha` con `sa_type=DateTime(timezone=True)` explícito.** Hallazgo: SQLModel 0.0.48 ya mapea `datetime` a `UTCDateTime()` (también `TIMESTAMPTZ`, y además rechaza fechas sin zona). Se declara igual el tipo explícito porque (a) el corrector ve "con zona horaria" en el código sin conocer un cambio reciente de SQLModel (hasta hace pocas versiones el default era sin zona), (b) no depende del default de la biblioteca si alguien cambia el pin, y (c) es el estándar del proyecto. Lo que se pierde (el rechazo de fechas sin zona en el modelo) se cubre en el DTO de C-06 con `AwareDatetime` (PA-10) y el seed usa fechas con zona. Ver Riesgos.

**Alternativas**: dejar el default `UTCDateTime()` (descartada: implícito y dependiente de la versión); `sa_type=UTCDateTime()` importado de `sqlmodel.sql.sqltypes` (conserva el rechazo de fechas sin zona, pero es un módulo interno poco conocido; descartada); `max_length` en los textos (descartada: nada lo pide y obliga a elegir números arbitrarios); `default=Decimal("0")` en `total` (descartada: escondería un service que se olvida de calcularlo).

### Decisión 3 — ⚠ Nombres de restricciones e índices: explícitos para UNIQUE y CHECK, deterministas para el resto, sin `naming_convention`
C-03 traduce `IntegrityError` a 404/409 por SQLSTATE y `constraint_name` (PA-01), y el caso C-08 muestra el nombre del CHECK en la consola: los nombres son contrato.

| Restricción | Cómo se declara | Nombre en la base |
|-------------|-----------------|-------------------|
| UNIQUE `duenio.email` | `__table_args__ = (UniqueConstraint("email", name="uq_duenio_email"),)` | `uq_duenio_email` |
| UNIQUE `ficha_duenio.duenio_id` | ídem | `uq_ficha_duenio_duenio_id` |
| UNIQUE `practica.nombre` | ídem | `uq_practica_nombre` |
| CHECK `precio > 0` | `CheckConstraint("precio > 0", name=...)` | `ck_practica_precio_positivo` |
| CHECK `total >= 0` | ídem | `ck_turno_total_no_negativo` |
| CHECK `precio_unitario > 0` | ídem | `ck_turno_practica_precio_unitario_positivo` |
| Índices de FK | `Field(index=True)` | `ix_mascota_duenio_id`, `ix_turno_mascota_id`, `ix_turno_practica_practica_id` (convención por defecto de SQLAlchemy `ix_%(column_0_label)s`) |
| Claves foráneas | `Field(foreign_key="tabla.id", ondelete=...)` | default de PostgreSQL `<tabla>_<columna>_fkey` (p. ej. `mascota_duenio_id_fkey`) |
| Claves primarias | `Field(primary_key=True)` | default de PostgreSQL `<tabla>_pkey` (p. ej. `turno_practica_pkey`) |

- Los UNIQUE van en `__table_args__` y no como `Field(unique=True)` porque `unique=True` no permite nombrarlos (PostgreSQL los llamaría `duenio_email_key`).
- Las claves foráneas conservan `Field(foreign_key=..., ondelete=...)`, la forma de SQLModel que enseña el curso y que el corrector busca; SQLModel no permite nombrarlas por esa vía, y el nombre que pone PostgreSQL es determinista y se recrea idéntico en cada `reiniciar.py`.
- **Todos los nombres de la tabla quedan fijados por tests de introspección** (Decisión 16): si un cambio los altera, la suite falla antes que la traducción de errores de C-03.

**Alternativas**: `SQLModel.metadata.naming_convention = {...}` (nombra también FK y PK de forma uniforme, pero es estado global que tiene que asignarse antes de importar el primer modelo — dependencia de orden de import frágil y oculta; descartada); `ForeignKeyConstraint(..., name=...)` en `__table_args__` (nombres uniformes `fk_*`, pero la clave foránea deja de verse en el `Field` de la columna; descartada); todos los nombres por defecto de PostgreSQL, incluidos UNIQUE y CHECK (`practica_precio_check`) (cero líneas extra, pero el nombre del CHECK del caso C-08 y de los UNIQUE que traduce C-03 no se vería en el código; descartada).

### Decisión 4 — Claves foráneas y reglas de borrado (PA-02, APROBADA por Matheo, 2026-11-05)
| Clave foránea | Regla | Origen | Justificación |
|---------------|-------|--------|---------------|
| `mascota.duenio_id` → `duenio.id` | RESTRICT | PDF (RN-08) | Agregación: no se borra un dueño con mascotas a su nombre |
| `turno_practica.turno_id` → `turno.id` | CASCADE | PDF (RN-09) | Composición: las prácticas reservadas nacen y mueren con el turno |
| `ficha_duenio.duenio_id` → `duenio.id` | CASCADE | PA-02 / DD-05 | La ficha no tiene sentido sin su dueño. Con RESTRICT, borrar un dueño con ficha y sin mascotas daría 409, pero RN-08 sólo prohíbe borrar por las mascotas: `DELETE /duenios/{id}` debe dar 204 |
| `turno.mascota_id` → `mascota.id` | RESTRICT | PA-02 / DD-06 | Asociación: un turno no pierde su mascota; no existe `DELETE /mascotas` |
| `turno_practica.practica_id` → `practica.id` | RESTRICT | PA-02 / DD-07 | El historial de precios cobrados sobrevive; no existe `DELETE /practicas` |

Se declaran siempre explícitas, también las RESTRICT: la regla por defecto (`NO ACTION`) se comportaría casi igual en este TP, pero el criterio de evaluación mira "RESTRICT y CASCADE" y la intención tiene que leerse en el código y en `pg_constraint` (`confdeltype` `'r'` / `'c'`, nunca `'a'`). Las claves foráneas quedan del lado "muchos" / dependiente (lo que exige el criterio "lado de cada clave foránea").

**Alternativas** (ya evaluadas en DD-05/06/07): SET NULL (incompatible con `NOT NULL` y con el sentido de las relaciones), RESTRICT en la ficha (contradice los códigos de `DELETE /duenios/{id}`), CASCADE en `turno.mascota_id` o `practica_id` (borraría historial en silencio).

### Decisión 5 — Índices exactamente donde los pide la consigna, y el orden de la PK compuesta
- `index=True` sólo en `mascota.duenio_id`, `turno.mascota_id` y `turno_practica.practica_id`: PostgreSQL no indexa solo una clave foránea, y sin índice el `RESTRICT`/`CASCADE` y los joins del lado "muchos" recorren la tabla entera.
- `ficha_duenio.duenio_id`, `duenio.email` y `practica.nombre` no llevan `index=True`: el UNIQUE ya crea su índice; un segundo sería redundante.
- `turno_practica.turno_id` **no** lleva índice propio: es la primera columna de la PK compuesta y el índice B-tree de la PK sirve cualquier búsqueda por `turno_id` (prefijo izquierdo). `practica_id`, segunda columna, no puede usar ese índice: por eso sí lleva el suyo.
- **El orden importa**: la PK sigue el orden de declaración de las columnas, así que en `TurnoPractica` se declara `turno_id` **antes** que `practica_id`. Un test verifica `PRIMARY KEY (turno_id, practica_id)`; si alguien invirtiera las columnas, la explicación del README sería falsa y el test lo detecta.

### Decisión 6 — Relaciones en los dos extremos
| Clave foránea | Lado "uno" (sin FK) | Lado "muchos" / dependiente (con FK) |
|---------------|---------------------|--------------------------------------|
| `ficha_duenio.duenio_id` | `Duenio.ficha: Optional["FichaDuenio"]` | `FichaDuenio.duenio: Optional["Duenio"]` |
| `mascota.duenio_id` | `Duenio.mascotas: list["Mascota"]` | `Mascota.duenio: Optional["Duenio"]` |
| `turno.mascota_id` | `Mascota.turnos: list["Turno"]` | `Turno.mascota: Optional["Mascota"]` |
| `turno_practica.turno_id` | `Turno.practicas: list["TurnoPractica"]` | `TurnoPractica.turno: Optional["Turno"]` |
| `turno_practica.practica_id` | `Practica.turnos: list["TurnoPractica"]` | `TurnoPractica.practica: Optional["Practica"]` |

- Todas con `Relationship(back_populates=...)` apuntando al atributo del otro extremo.
- **`Duenio.ficha` con `sa_relationship_kwargs={"uselist": False}`**. Hallazgo: como SQLModel 0.0.48 envuelve la anotación en `Mapped[Optional[...]]`, SQLAlchemy 2.0 ya inferiría `uselist=False`; se declara igual explícito porque es exactamente lo que pide la consigna ("devuelve un objeto y no una lista") y no depende de ese detalle interno.
- **`Practica.turnos`** (y no `turno_practicas`): espeja el nombre que fija la consigna para `Turno.practicas`, cuyos elementos también son filas `TurnoPractica`. Desde una práctica, `practica.turnos[i].turno` llega al turno, igual que `turno.practicas[i].practica` llega a la práctica.
- **`TurnoPractica` es un modelo de tabla completo** (objeto de asociación), no un `link_model`: la relación tiene un dato propio (`precio_unitario`) y `link_model` sólo sirve para tablas intermedias sin datos.
- Anotaciones entre módulos como en el tutorial de SQLModel: `if TYPE_CHECKING:` para el import y el tipo entre comillas (`Optional["Mascota"]`, `list["Turno"]`). **Nunca** `from __future__ import annotations` en los `models.py` ni `"Mascota | None"` como cadena: SQLModel/SQLAlchemy tendrían que evaluar la cadena entera y no resuelven la unión.
- Los lados "muchos" usan la cascada por defecto (`save-update, merge`) y no llevan `passive_deletes` (no aplica: no tienen hijas).

### Decisión 7 — ⚠ `passive_deletes="all"` en los cinco lados "uno", sin `cascade_delete`
Es el punto central del Ej. 3. Qué hace el ORM al ejecutar `session.delete(padre)` + `commit`, según cómo se declare la relación del padre hacia sus hijas (con clave foránea `NOT NULL`):

| Declaración del lado "uno" | Hijas **no** cargadas en la sesión | Hijas **cargadas** en la sesión |
|----------------------------|------------------------------------|---------------------------------|
| Por defecto (`passive_deletes=False`) | El ORM emite un `SELECT` de las hijas y luego `UPDATE hija SET fk = NULL` → `23502` (not null) — un error engañoso que no es el FK; en `turno_practica` (FK dentro de la PK) `AssertionError: ... tried to blank-out primary key column` | Igual: `UPDATE ... SET fk = NULL` o `AssertionError` |
| `cascade_delete=True` (`"all, delete-orphan"`), sin `passive_deletes` | `SELECT` de las hijas y un `DELETE` por cada una: **el ORM hace la cascada**. Con RESTRICT borraría las mascotas y después el dueño → **RN-08 burlada** | `DELETE` de cada hija desde el ORM |
| `passive_deletes=True`, sin `cascade_delete` | Sin `SELECT`; sólo `DELETE padre` → decide la base ✔ | `UPDATE hija SET fk = NULL` o `AssertionError` ✘ (depende de qué haya cargado el service) |
| `passive_deletes=True` + `cascade_delete=True` (patrón del tutorial de SQLModel para CASCADE) | Sin `SELECT`; la base borra en cascada ✔ | El ORM emite un `DELETE` por cada hija cargada ✘ ("el ORM borra esas filas por su cuenta"); con RESTRICT borraría las mascotas cargadas y RN-08 quedaría burlada |
| **`passive_deletes="all"`, sin `cascade_delete`** (elegida) | Sin `SELECT`; sólo `DELETE padre` → la base aplica CASCADE o rechaza con RESTRICT ✔ | El ORM no toca las hijas (ni `UPDATE` ni `DELETE`); sólo `DELETE padre` → decide la base ✔ |
| `passive_deletes="all"` + `cascade_delete=True` | — | — : SQLAlchemy lo rechaza al configurar (`ArgumentError: can't set passive_deletes='all' in conjunction with 'delete' or 'delete-orphan' cascade`) |

Se aplica la misma declaración a las cinco relaciones del lado "uno", con una sola regla para el equipo: **ningún borrado lo resuelve el ORM**.

| Relación | Regla en la base | Con `passive_deletes="all"`, al borrar el padre |
|----------|------------------|-------------------------------------------------|
| `Turno.practicas` | CASCADE | la base borra las filas de `turno_practica` (RN-09, caso C-05) |
| `Duenio.ficha` | CASCADE | la base borra la ficha (204 en `DELETE /duenios/{id}` sin mascotas) |
| `Duenio.mascotas` | RESTRICT | la base rechaza con `23503` sobre `mascota_duenio_id_fkey` → C-03 responde 409 (RN-08, caso C-05) |
| `Mascota.turnos` | RESTRICT | la base rechaza con `23503` sobre `turno_mascota_id_fkey` |
| `Practica.turnos` | RESTRICT | la base rechaza con `23503` sobre `turno_practica_practica_id_fkey` |

- **Se conserva la cascada por defecto `save-update, merge`**: `turno.practicas.append(TurnoPractica(practica_id=..., precio_unitario=...))` seguido de `session.add(turno)` inserta el turno y sus filas en la misma transacción, con el `turno_id` sincronizado por el ORM al hacer `flush` — lo que necesita el alta todo-o-nada de C-06.
- Declaración resultante (ejemplo): `practicas: list["TurnoPractica"] = Relationship(back_populates="turno", passive_deletes="all")`.
- **Diferencia con la KB**: `knowledge-base/09` (DD-13) y `08` dicen `passive_deletes=True`. Con `True` el resultado depende de si el service cargó las hijas antes de borrar (fila 3 y 4 de la primera tabla); `"all"` cumple la consigna ("que el ORM no intente vaciar ni borrar esas filas por su cuenta") en todos los casos. Si Matheo lo aprueba, se actualiza DD-13 en la KB al archivar.

**Alternativas**: `passive_deletes=True` + `cascade_delete=True` sólo en las dos relaciones CASCADE y `"all"` en las RESTRICT (es el patrón del tutorial, pero con hijas cargadas el ORM emite los `DELETE` él mismo: el borrado lo decide el ORM, justo lo que la consigna pide evitar; descartada); `passive_deletes=True` a secas (frágil según lo cargado; descartada); dejar el default en las RESTRICT (el `UPDATE ... SET NULL` dispara `23502` antes de llegar al RESTRICT y C-03 respondería por la razón equivocada; descartada).

### Decisión 8 — ⚠ Registro único de modelos en `app/core/modelos.py`
`create_all`/`drop_all` sólo ven las tablas de los modelos **importados**, y SQLAlchemy resuelve los nombres de las relaciones (`"Mascota"`, `"Turno"`, …) recién al configurar los mappers, buscando en las clases ya registradas: si un proceso importa `app.modules.duenios.models` y no `app.modules.mascotas.models`, la primera consulta falla con `InvalidRequestError: ... expression 'Mascota' failed to locate a name`. Con los modelos repartidos en cuatro módulos (D-8 de C-01), hace falta un único lugar que los importe todos:

```python
"""Registro de los modelos de tabla: importarlo registra las seis tablas en
SQLModel.metadata (create_all / drop_all) y permite resolver las relaciones entre módulos."""
from app.modules.duenios.models import Duenio, FichaDuenio
from app.modules.mascotas.models import Mascota
from app.modules.practicas.models import Practica
from app.modules.turnos.models import Turno, TurnoPractica

__all__ = ["Duenio", "FichaDuenio", "Mascota", "Practica", "Turno", "TurnoPractica"]
```

Lo importan: `reiniciar.py` (crea el esquema), `app/main.py` (una línea `from app.core import modelos  # noqa: F401` con comentario: registra todas las tablas antes de la primera consulta; sin ella, C-03 fallaría mientras C-04..C-06 todavía no registren sus routers) y los tests (a través de `reiniciar.py`). No hay ciclos: los `models.py` no importan nada de `app.core`.

**Alternativas**: importar todo en `app/modules/__init__.py` (cualquier import de un submódulo cargaría los seis modelos como efecto colateral escondido; descartada); importar los modelos dentro de `app/core/database.py` (mezcla motor/sesión con el modelo de dominio, contra lo que la consigna asigna a ese archivo; descartada); imports cruzados al final de cada `models.py` (frágil y difícil de leer; descartada); `configure_mappers()` dentro del registro (adelanta el error al import, pero agrega un paso que los tests ya cubren; descartada).

### Decisión 9 — Módulos nuevos sólo con `__init__.py` y `models.py`
Se crean `app/modules/{duenios,mascotas,practicas,turnos}/__init__.py` (vacíos) y `models.py`. `schemas.py`, `service.py` y `router.py` los crea el change de cada módulo (C-03..C-06), como ya fijó C-01 ("cada change crea el suyo; no se dejan esqueletos vacíos"): un archivo vacío o con `TODO` hoy sería código muerto que otro integrante tendría que reemplazar. La estructura completa "igual en todos los módulos" queda al cerrar C-06.

### Decisión 10 — Modelos de tabla independientes, sin clase base compartida con los DTO
Cada modelo hereda directo de `SQLModel` con `table=True`; no se crean `DuenioBase` / `PracticaBase` para que los DTO hereden de ellas. Regla dura 6: el contrato HTTP no se deriva del modelo de tabla. Razones concretas: los modelos de tabla no validan en el constructor (por eso el seed y los tests pueden escribir valores inválidos y comprobar que la base los rechaza), mientras que los DTO necesitan `extra="forbid"`, `EmailStr`, `gt=0`, `min_length=1` y `AwareDatetime`; una base común mezclaría las dos cosas. El costo es repetir dos o tres campos por entidad en `schemas.py`.

**Alternativa**: el patrón "multiple models with inheritance" del tutorial de SQLModel (descartada por lo anterior; cada change de módulo puede reconsiderarlo sólo para sus DTO entre sí).

### Decisión 11 — `reiniciar.py`: funciones importables, transacción única y flush escalonado
Archivo en la raíz (lo nombra la consigna), con tres funciones y el punto de entrada:

- `async def recrear_esquema(engine: AsyncEngine) -> None`: `async with engine.begin() as conn:` → `await conn.run_sync(SQLModel.metadata.drop_all)` y `await conn.run_sync(SQLModel.metadata.create_all)`. Una transacción DDL (PostgreSQL la admite). `drop_all`/`create_all` usan `checkfirst=True`: sobre una base vacía no falla, sobre una existente borra las seis tablas (y sus secuencias, por eso los ids vuelven a 1).
- `async def cargar_datos_iniciales(session: AsyncSession) -> None`: arma los objetos de la Decisión 13 y los guarda en **una transacción** con `flush` escalonado: (1) las cuatro prácticas → `await session.flush()`; (2) los dos dueños con la ficha y las tres mascotas → `flush()`; (3) el turno con sus dos `TurnoPractica` → `await session.commit()`. Si algo falla, el `async with` de la sesión del llamador hace rollback y no queda nada (escenario "falla a mitad de camino").
  - **Por qué escalonado**: sin `flush` intermedios, el orden de los `INSERT` de una tabla sigue el orden en que la cascada `save-update` va agregando objetos a la sesión, y agregar un dueño arrastra mascota → turno → `TurnoPractica` → práctica: las prácticas del turno se insertarían antes que las otras dos y los ids dependerían de qué prácticas lleve el turno. Con el catálogo primero, los ids 1..4 siguen el orden de la lista sin importar la cascada.
  - Nunca se asignan ids a mano: las secuencias tienen que avanzar para que el turno del ejemplo reciba id 2.
  - El precio se copia del objeto del catálogo (`TurnoPractica(practica=p, precio_unitario=p.precio)`) y el total se calcula: `sum((tp.precio_unitario for tp in lineas), start=Decimal("0"))`.
- `async def main() -> None`: `config = cargar_configuracion()` (misma `DATABASE_URL` y `SQL_ECHO` que la aplicación), `engine = crear_motor(config)`; dentro de `try`: `recrear_esquema(engine)` y `async with crear_fabrica_sesiones(engine)() as session: await cargar_datos_iniciales(session)`; `finally: await engine.dispose()`. Al final imprime un resumen de una línea ("Esquema recreado. Datos iniciales: 2 dueños (1 con ficha), 3 mascotas, 4 prácticas, 1 turno con 2 prácticas."). `print` es aceptable: es un script de consola, no un handler del servidor (regla dura 2).
- `if __name__ == "__main__":` ejecuta `asyncio.run(main())` y convierte `ConfiguracionInvalida` en `SystemExit(str(exc))` (mensaje de C-01, que nunca incluye la clave; código de salida 1, sin traceback). Cualquier otro error (p. ej. la base apagada) muestra el traceback de asyncpg tal cual.

Los tests importan `recrear_esquema` y `cargar_datos_iniciales` desde `reiniciar` (la raíz está en `sys.path` por `pythonpath = .`): los datos iniciales se definen una sola vez.

**Alternativas**: seed en `app/core/seed.py` y `reiniciar.py` como envoltorio (el corrector busca los datos en `reiniciar.py`; descartada); `flush` único con `add_all` en orden (los ids dependerían de la cascada; descartada); ids explícitos (las secuencias no avanzan y el siguiente `INSERT` choca con la PK; descartada); `TRUNCATE ... RESTART IDENTITY` en vez de `drop_all` (no recrea las tablas si cambia el modelo y falla sobre una base vacía; descartada); crear el esquema en el `lifespan` (la consigna lo asigna a `reiniciar.py`; descartada); mensaje amigable también para la base apagada (nada lo pide; descartada).

### Decisión 12 — Bucle de eventos en Windows: el de defecto
`asyncio.run(main())` sin políticas: en Windows usa `ProactorEventLoop`, que asyncpg soporta (la incompatibilidad conocida con Proactor es de psycopg, no de asyncpg), y es el mismo bucle con el que corre la suite de C-01. No se usa `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())`: el sistema de políticas está deprecado desde Python 3.14. El `dispose` en el `finally` cierra las conexiones antes de que `asyncio.run` cierre el bucle (evita los avisos "Event loop is closed" de transportes huérfanos en Windows). Si la tarea 0 detectara un problema real con Proactor, el reemplazo es `asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)` (Python ≥3.12), y se registra acá.

### Decisión 13 — Datos iniciales (PA-03, APROBADA por Matheo, 2026-11-05)
| Tabla | Filas (en orden de inserción → id) |
|-------|------------------------------------|
| `practica` | 1 "Consulta" 15000.00 · 2 "Desparasitación" 8000.00 · 3 "Vacuna antirrábica" 12000.00 · 4 "Vacuna quíntuple" 14000.00 |
| `duenio` | 1 "Ana Gómez" `ana.gomez@example.com` · 2 "Carlos Ruiz" `carlos.ruiz@example.com` |
| `ficha_duenio` | 1 → dueño 1, teléfono "11 5555-0101", dirección "Calle Falsa 123" (ficticios) |
| `mascota` | 1 "Toby" "perro" (dueño 1) · 2 "Mishi" "gato" (dueño 1) · 3 "Luna" "perro" (dueño 2) |
| `turno` | 1 → mascota 2 "Mishi", fecha `2026-11-10T09:00:00-03:00` (guardada `12:00Z`), motivo "Control y desparasitación", total calculado 23000.00 |
| `turno_practica` | (1, 1, 15000.00) · (1, 2, 8000.00) — precios copiados del catálogo |

Textos con sus tildes tal cual (UTF-8; la base del contenedor es UTF-8). Teléfono, dirección, fecha y motivo los elige este design (la aprobación fija el resto). El turno del seed es de "Mishi" y no de "Toby" a propósito: la mascota 1 queda sin turnos, así que el ejemplo del Ej. 4 (mascota 1, prácticas 1 y 3) no choca con nada y produce el turno 2 con total 27000.00; y "Toby" sirve en los tests como mascota borrable.

### Decisión 14 — Caso C-08: `test/c08_check_precio.sql`
```sql
-- Caso C-08 de la consigna: la base rechaza por el CHECK un precio que no es mayor que cero (RN-04).
-- Precondición: python reiniciar.py (la práctica 1 es "Consulta", precio 15000.00).
-- Cómo ejecutarlo, con el contenedor levantado (docker compose up -d), igual en bash y en PowerShell:
--   docker compose cp test/c08_check_precio.sql db:/tmp/c08_check_precio.sql
--   docker compose exec db psql -U <usuario> -d veterinaria -f /tmp/c08_check_precio.sql
-- (<usuario> es POSTGRES_USER del .env). También se puede pegar en psql o en cualquier cliente SQL.
-- Esperado:
--   ERROR:  new row for relation "practica" violates check constraint "ck_practica_precio_positivo"
--   DETAIL:  Failing row contains (1, Consulta, 0.00).
--   (SQLSTATE 23514; el UPDATE no modifica ninguna fila)
UPDATE practica SET precio = 0 WHERE id = 1;

-- Esperado: la práctica 1 conserva su precio (15000.00).
SELECT id, nombre, precio FROM practica WHERE id = 1;
```
- `docker compose cp` + `-f` en vez de redirigir la entrada (`< archivo`), que no existe en PowerShell, y en vez de montar `test/` en el contenedor (cambiaría el `docker-compose.yml` de C-01).
- `WHERE id = 1` para que el `DETAIL` del error sea determinista; el texto de la consigna (`UPDATE practica SET precio = 0`) queda literal en la sentencia.
- Un test de pytest ejecuta **la sentencia del propio archivo** (lee el `.sql`, descarta las líneas `--`, separa por `;`) contra la base de test con el seed, y verifica `23514` + `ck_practica_precio_positivo` y el precio intacto: el entregable no puede quedar desincronizado del esquema.
- Este change no crea `.http`: no tiene endpoints. Su entregable en `test/` es este `.sql`.

### Decisión 15 — README
- Sección "Índice de `turno_practica.turno_id`" (el encabezado lo deja C-01): "`turno_practica.turno_id` no lleva índice propio porque es la primera columna de la clave primaria compuesta `(turno_id, practica_id)`: el índice B-tree de esa clave ya sirve las búsquedas, los joins y el borrado en cascada por `turno_id`. `practica_id`, en segunda posición, no puede usarlo, y por eso tiene el suyo."
- Paso `python reiniciar.py`: se quita la marca "disponible desde C-02" y se aclara que borra y recrea las tablas de la base de `DATABASE_URL` y carga los datos iniciales.
- Mención del caso C-08 y cómo ejecutar `test/c08_check_precio.sql` (remite a los comentarios del archivo).

### Decisión 16 — Tests: esquema recreado por test, introspección + comportamiento
**Fixtures nuevas en `tests/conftest.py`** (todas de scope `function`, como las de C-01, porque un motor asyncpg queda atado al bucle que lo creó):
- `motor_test(url_base_test)`: `crear_motor(Configuracion(database_url=url_base_test, sql_echo=False))`; `dispose` al terminar. Reutiliza el guard `_test` de C-01: nunca toca la base de desarrollo.
- `esquema_vacio(motor_test)`: `await recrear_esquema(motor_test)` y devuelve el motor. Cada test arranca con las seis tablas vacías y los ids en 1 (aislamiento total; cuesta unas décimas de segundo por test, aceptable para esta suite).
- `base_con_seed(esquema_vacio)`: carga `cargar_datos_iniciales` en una sesión propia y devuelve el motor. Los changes C-03..C-06 la combinan con `client` (el motor de la app es otro, pero ve los datos confirmados).
- `sesion(esquema_vacio)`: `AsyncSession` de `crear_fabrica_sesiones(motor_test)`.
- `sentencias_sql(motor_test)`: lista que se llena con un listener `before_cursor_execute` sobre `motor_test.sync_engine` (se quita al terminar). Prueba qué SQL emitió el ORM sin depender de `echo`.

**Helper en `tests/soporte.py`**: `error_postgres(exc: IntegrityError) -> asyncpg.PostgresError` devuelve `exc.orig.__cause__` (la excepción original de asyncpg, con `sqlstate` y `constraint_name`), y falla el test si no es una excepción de PostgreSQL. Es sólo de tests: la versión de producción la diseña C-03 (PA-01).

**Archivos de test** (todos con `pytestmark = pytest.mark.integracion`):
- `tests/test_esquema.py` — introspección: tablas exactas (`information_schema.tables`), columnas exactas, tipos y `is_nullable` (`information_schema.columns`), restricciones y `confdeltype` (`pg_constraint` + `pg_get_constraintdef`), índices exactos (`pg_indexes`), PK compuesta en orden; relaciones vía `sqlalchemy.inspect(Modelo).relationships` (`back_populates` cruzados, `uselist`, `passive_deletes == "all"`, sin `delete` en la cascada de los lados "uno").
- `tests/test_restricciones.py` — la base rechaza (con SQLSTATE y nombre): UNIQUE, CHECK con valores límite (`0` / `-1` rechazados, `0.01` aceptado; `total` `-0.01` rechazado, `0` aceptado), FK a filas inexistentes, NOT NULL, PK compuesta repetida; ida y vuelta de `Decimal` y de `fecha` con desplazamiento. Las escrituras inválidas se hacen con el ORM (los modelos de tabla no validan) o con `text()` cuando el ORM no deja expresar el caso (columna ausente → `23502`).
- `tests/test_borrados.py` — `passive_deletes`: borrar el turno 1 con y sin prácticas cargadas (`sentencias_sql` contiene el `DELETE FROM turno` — prueba que la captura funciona — y ninguna sentencia `SELECT`/`UPDATE`/`DELETE` sobre `turno_practica`; las filas desaparecen); dueño con mascotas (cargadas y sin cargar) → `23503` `mascota_duenio_id_fkey`, sin `UPDATE`, todo intacto (verificado con otra sesión tras el rollback); dueño con ficha y sin mascotas → se borra con su ficha; mascota con turnos y práctica usada → `23503`; "Toby" y "Vacuna quíntuple" → se borran.
- `tests/test_relaciones.py` — navegación con carga anticipada (`joinedload` a-uno, `selectinload` colecciones, `selectinload(Turno.practicas).joinedload(TurnoPractica.practica)`): `Duenio.ficha` objeto / `None`, listas en los lados "muchos", datos accesibles tras cerrar la sesión; consistencia en memoria de `back_populates`; alta de un turno con `practicas.append(...)` en una transacción.
- `tests/test_reiniciar.py` — seed exacto (filas y valores por tabla), total = suma de `precio_unitario`, carga que falla a mitad de camino (dueño `ana.gomez@example.com` preexistente → `uq_duenio_email` y `practica` vacía), carga repetida sin recrear → `23505` sin cambios, ejemplo del Ej. 4 (turno 2, total 27000.00) y secuencias (3, 4, 5); `python reiniciar.py` como subproceso (`asyncio.to_thread(subprocess.run, [sys.executable, "reiniciar.py"], cwd=raíz, env={..., "DATABASE_URL": url_base_test, "SQL_ECHO": "0"})`) sobre la base sin tablas y dos veces seguidas (mismo estado e ids), con `DATABASE_URL=""` (vacía: `load_dotenv` no pisa una variable ya definida, así que no se cuela la del `.env`) y con `postgresql://` → código ≠ 0, mensaje con `DATABASE_URL` y sin la clave de `TEST_DATABASE_URL`; un subproceso que sólo hace `import app.main` + `configure_mappers()` termina bien (registro de la Decisión 8) y otro que importa sólo `app.modules.duenios.models` falla al configurar (prueba por qué hace falta el registro); el `.sql` del caso C-08 (Decisión 14).
- `tests/test_repositorio.py` (de C-01) — la sección del README nombra la clave primaria compuesta.

## Risks / Trade-offs

- [`fecha` con `DateTime(timezone=True)` acepta un `datetime` sin zona y asyncpg lo interpreta con la hora local de la máquina] → el modelo nunca recibe fechas sin zona: el seed usa desplazamiento explícito y el DTO de C-06 usa `AwareDatetime` (PA-10 lo decide C-06, con esta restricción). Un test de ida y vuelta fija el comportamiento con desplazamiento.
- [Con `passive_deletes="all"`, las hijas que estaban cargadas en la sesión quedan en ella como objetos persistentes aunque la base ya borró sus filas] → la sesión es una por petición y el `DELETE` responde 204 sin volver a leerlas; si un service necesitara seguir usando la sesión, `session.expunge(...)` o una lectura nueva.
- [`passive_deletes="all"` no evita el `UPDATE ... SET NULL` si una hija se **saca** de la colección (`turno.practicas.remove(tp)`); en `turno_practica` eso es un `AssertionError` por vaciar la PK] → ningún endpoint quita prácticas de un turno existente; si alguna vez hiciera falta, se borra la fila con `session.delete(tp)`. Documentado para C-06.
- [Nombres de FK/PK por defecto de PostgreSQL: un cambio de versión del motor podría cambiar la convención] → PostgreSQL usa `<tabla>_<columna>_fkey` desde hace más de una década y la base está fijada en 16; los tests de introspección fallan si cambia.
- [Recrear el esquema en cada test hace la suite más lenta a medida que crece] → aceptable ahora (seis tablas); si molesta, pasar a `TRUNCATE ... RESTART IDENTITY` por test con el esquema creado una vez, sin cambiar los tests.
- [`DROP TABLE` espera si queda una conexión de un test anterior con una transacción abierta] → todas las sesiones se abren con `async with` y todos los motores se cierran en el teardown; si un test cuelga en `recrear_esquema`, buscar una sesión sin cerrar.
- [`reiniciar.py` borra los datos de la base de `DATABASE_URL`] → es lo que pide la consigna; el README lo dice y los tests lo ejecutan sólo con `TEST_DATABASE_URL` (guard `_test`).
- [El mensaje del error del caso C-08 depende del idioma del servidor] → la imagen `postgres:16` usa inglés por defecto; el comentario del `.sql` cita el nombre de la restricción, que no se traduce.
- [`docker-compose.yml` de C-01 no parsea al momento de este propose] → bloquea la tarea 0; se reporta a C-01 (no se corrige desde este change).
- [La KB dice `passive_deletes=True` (DD-13)] → la Decisión 7 explica por qué `"all"`; actualizar DD-13 al archivar si se aprueba.

## Migration Plan

No hay datos que migrar: hasta este change la base no tiene tablas. Puesta en marcha: con C-01 aplicado y `docker compose up -d`, `python reiniciar.py` crea el esquema de desarrollo; la suite crea el de `veterinaria_test` sola. Vuelta atrás: los archivos de este change son nuevos salvo `app/main.py` (una línea), `tests/conftest.py`, `tests/soporte.py` y `README.md`, que se revierten con git; las tablas se eliminan con `docker compose down -v` o `DROP TABLE`.
