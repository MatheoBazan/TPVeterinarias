## Purpose

Define el esquema relacional de la veterinaria que la base de datos impone por sí misma: las seis tablas de la consigna con sus columnas y tipos, las claves primarias y foráneas con su regla de borrado, las restricciones UNIQUE y CHECK, los índices con su justificación, y la navegación entre entidades en los dos extremos de cada clave foránea, con el borrado decidido por la base y no por el ORM. Cubre el Ejercicio 3 de la consigna (30 %). Este change no expone endpoints: la "respuesta" esperada de cada escenario es lo que hace la base (filas resultantes, o el rechazo con su SQLSTATE y el nombre de la restricción que lo produjo); la traducción a códigos HTTP la hacen los changes de cada módulo.

## ADDED Requirements

### Requirement: Tablas y columnas obligatorias de la consigna
Crear el esquema sobre una base sin tablas SHALL dejar exactamente seis tablas en el esquema `public`, con los nombres y las columnas que fija la consigna: `duenio` (`id`, `nombre`, `email`), `ficha_duenio` (`id`, `duenio_id`, `telefono`, `direccion`), `mascota` (`id`, `nombre`, `especie`, `duenio_id`), `practica` (`id`, `nombre`, `precio`), `turno` (`id`, `mascota_id`, `fecha`, `motivo`, `total`) y `turno_practica` (`turno_id`, `practica_id`, `precio_unitario`). Todas esas columnas MUST ser `NOT NULL`. Trazabilidad: Ej. 3 ("Las tablas"); regla dura 1 (esquema intocable).

#### Scenario: El esquema creado tiene exactamente las seis tablas
- **GIVEN** una base `veterinaria_test` sin tablas en el esquema `public`
- **WHEN** se crea el esquema
- **THEN** el esquema `public` contiene exactamente las tablas `duenio`, `ficha_duenio`, `mascota`, `practica`, `turno` y `turno_practica`
- **AND** no existe ninguna tabla llamada `fichaduenio` ni `turnopractica`

#### Scenario: Cada tabla tiene exactamente las columnas de la consigna
- **GIVEN** el esquema recién creado
- **WHEN** se consultan las columnas de cada tabla en `information_schema.columns`
- **THEN** el conjunto de columnas de cada tabla es exactamente el de la consigna (por ejemplo `turno_practica` tiene sólo `turno_id`, `practica_id` y `precio_unitario`)
- **AND** todas ellas tienen `is_nullable = 'NO'`

#### Scenario: Una columna obligatoria rechaza NULL
- **GIVEN** el esquema recién creado y un dueño con id 1
- **WHEN** se inserta directamente en la base una mascota sin `duenio_id` (o un dueño sin `email`)
- **THEN** la base rechaza la escritura con SQLSTATE `23502` (not_null_violation)
- **AND** no queda ninguna fila nueva

### Requirement: Tipos de las columnas
Las columnas de dinero SHALL ser numéricas exactas: `practica.precio` y `turno_practica.precio_unitario` `NUMERIC(10,2)`, y `turno.total` `NUMERIC(12,2)`; la aplicación MUST leerlas como decimales exactos, nunca como punto flotante. `turno.fecha` MUST ser `TIMESTAMP WITH TIME ZONE` y conservar el instante de un valor con desplazamiento horario. Los `id` MUST ser enteros generados por la base (autoincrementales), y los textos (`nombre`, `email`, `especie`, `telefono`, `direccion`, `motivo`) columnas de caracteres. Trazabilidad: Ej. 3; "el dinero se representa con Decimal, nunca con float"; DD-11 (`fecha` con zona horaria).

#### Scenario: Tipos declarados en la base
- **GIVEN** el esquema recién creado
- **WHEN** se consultan los tipos en `information_schema.columns`
- **THEN** `practica.precio` y `turno_practica.precio_unitario` son `numeric` con precisión 10 y escala 2
- **AND** `turno.total` es `numeric` con precisión 12 y escala 2
- **AND** `turno.fecha` es `timestamp with time zone`
- **AND** los `id` son `integer` con valor por defecto tomado de una secuencia

#### Scenario: El dinero vuelve como decimal exacto con dos decimales
- **GIVEN** una práctica guardada con precio `15000`
- **WHEN** se la vuelve a leer
- **THEN** el precio leído es el decimal exacto `15000.00` (tipo `Decimal`, no `float`)
- **AND** una práctica guardada con precio `0.10` se lee como `0.10` exacto, sin error de redondeo binario

#### Scenario: La fecha conserva el instante y se lee en UTC
- **GIVEN** un turno guardado con `fecha = 2026-11-12T10:30:00-03:00`
- **WHEN** se lo vuelve a leer
- **THEN** la fecha leída tiene zona horaria y representa el instante `2026-11-12T13:30:00Z`

### Requirement: Claves primarias
Cada tabla SHALL tener clave primaria: `id` en `duenio`, `ficha_duenio`, `mascota`, `practica` y `turno`; y la clave primaria compuesta `(turno_id, practica_id)`, en ese orden, en `turno_practica`, que MUST impedir que una misma práctica aparezca dos veces en un turno. Trazabilidad: RN-07 ("clave primaria compuesta de `turno_practica`; 409"); caso C-04 (práctica repetida en el alta del turno, lo traduce C-06).

#### Scenario: La clave primaria de turno_practica es compuesta y empieza por turno_id
- **GIVEN** el esquema recién creado
- **WHEN** se consulta la definición de la clave primaria de `turno_practica`
- **THEN** es `PRIMARY KEY (turno_id, practica_id)`, con `turno_id` como primera columna

#### Scenario: La misma práctica dos veces en un turno se rechaza
- **GIVEN** el turno 1 con la práctica 1
- **WHEN** se inserta otra fila de `turno_practica` con `turno_id = 1` y `practica_id = 1`
- **THEN** la base rechaza la escritura con SQLSTATE `23505` y restricción `turno_practica_pkey`
- **AND** el turno 1 sigue teniendo una sola fila para la práctica 1

#### Scenario: La misma práctica en dos turnos distintos se acepta
- **GIVEN** el turno 1 con la práctica 1
- **WHEN** se crea un turno 2 con la práctica 1
- **THEN** la base acepta la escritura y la práctica 1 figura en los dos turnos

### Requirement: Unicidad garantizada por la base
La base SHALL rechazar, sin que la aplicación consulte antes, un segundo dueño con el mismo `email` (restricción `uq_duenio_email`), una segunda práctica con el mismo `nombre` (`uq_practica_nombre`) y una segunda ficha para el mismo dueño (`uq_ficha_duenio_duenio_id`, que convierte la relación dueño–ficha en uno a uno). Los nombres de las restricciones MUST ser estables, porque los changes de cada módulo traducen el rechazo a 409 por ese nombre. Trazabilidad: RN-01, RN-02, RN-03; casos C-02 y C-03 de la consigna (los 409 los produce el endpoint de cada módulo).

#### Scenario: Email de dueño repetido
- **GIVEN** el dueño `ana.gomez@example.com`
- **WHEN** se inserta otro dueño con email `ana.gomez@example.com`
- **THEN** la base rechaza la escritura con SQLSTATE `23505` y restricción `uq_duenio_email`
- **AND** sigue habiendo un solo dueño con ese email

#### Scenario: Email distinto se acepta
- **GIVEN** el dueño `ana.gomez@example.com`
- **WHEN** se inserta un dueño con email `otra.persona@example.com`
- **THEN** la base acepta la escritura

#### Scenario: Nombre de práctica repetido
- **GIVEN** la práctica "Consulta"
- **WHEN** se inserta otra práctica llamada "Consulta"
- **THEN** la base rechaza la escritura con SQLSTATE `23505` y restricción `uq_practica_nombre`

#### Scenario: Segunda ficha para el mismo dueño
- **GIVEN** el dueño 1 con ficha
- **WHEN** se inserta otra ficha con `duenio_id = 1`
- **THEN** la base rechaza la escritura con SQLSTATE `23505` y restricción `uq_ficha_duenio_duenio_id`

#### Scenario: Primera ficha de otro dueño se acepta
- **GIVEN** el dueño 2 sin ficha
- **WHEN** se inserta una ficha con `duenio_id = 2`
- **THEN** la base acepta la escritura y el dueño 2 queda con exactamente una ficha

### Requirement: Restricciones CHECK sobre el dinero
La base SHALL rechazar un `practica.precio` menor o igual a cero (`ck_practica_precio_positivo`), un `turno_practica.precio_unitario` menor o igual a cero (`ck_turno_practica_precio_unitario_positivo`) y un `turno.total` negativo (`ck_turno_total_no_negativo`), también cuando la escritura no pasa por la aplicación. Trazabilidad: RN-04 (lado base; el DTO lo valida en el change de prácticas), RN-06 (precio copiado y total calculado, siempre válidos); caso C-08 de la consigna.

#### Scenario: Precio de práctica cero o negativo
- **GIVEN** el esquema recién creado
- **WHEN** se inserta una práctica con precio `0` (o con precio `-1`)
- **THEN** la base rechaza la escritura con SQLSTATE `23514` y restricción `ck_practica_precio_positivo`

#### Scenario: Precio mínimo positivo se acepta
- **GIVEN** el esquema recién creado
- **WHEN** se inserta una práctica con precio `0.01`
- **THEN** la base acepta la escritura

#### Scenario: Cambiar el precio a cero directo en la base
- **GIVEN** la práctica 1 con precio `15000.00`
- **WHEN** se ejecuta directamente en la base `UPDATE practica SET precio = 0 WHERE id = 1`
- **THEN** la base rechaza la sentencia con SQLSTATE `23514` y restricción `ck_practica_precio_positivo`
- **AND** la práctica 1 conserva el precio `15000.00`

#### Scenario: Precio unitario cero en un turno
- **GIVEN** un turno y una práctica existentes
- **WHEN** se inserta una fila de `turno_practica` con `precio_unitario = 0`
- **THEN** la base rechaza la escritura con SQLSTATE `23514` y restricción `ck_turno_practica_precio_unitario_positivo`

#### Scenario: Total negativo se rechaza y total cero se acepta
- **GIVEN** una mascota existente
- **WHEN** se inserta un turno con `total = -0.01`
- **THEN** la base rechaza la escritura con SQLSTATE `23514` y restricción `ck_turno_total_no_negativo`
- **AND** un turno con `total = 0` se acepta

### Requirement: Claves foráneas con su regla de borrado
Cada clave foránea SHALL estar del lado "muchos" o dependiente de su relación, rechazar una referencia a una fila inexistente y declarar explícitamente su regla de borrado: `ficha_duenio.duenio_id` → `duenio.id` ON DELETE CASCADE; `mascota.duenio_id` → `duenio.id` ON DELETE RESTRICT; `turno.mascota_id` → `mascota.id` ON DELETE RESTRICT; `turno_practica.turno_id` → `turno.id` ON DELETE CASCADE; `turno_practica.practica_id` → `practica.id` ON DELETE RESTRICT. Cada restricción MUST llamarse `<tabla>_<columna>_fkey`. Trazabilidad: RN-08 (RESTRICT), RN-09 (CASCADE); PA-02 (reglas que la consigna no fija, aprobadas); caso C-04 de la consigna (mascota con dueño inexistente y turno con práctica inexistente: la base rechaza).

#### Scenario: Reglas de borrado declaradas en la base
- **GIVEN** el esquema recién creado
- **WHEN** se consulta `pg_constraint` para las cinco claves foráneas
- **THEN** `ficha_duenio_duenio_id_fkey` y `turno_practica_turno_id_fkey` tienen `confdeltype = 'c'` (CASCADE)
- **AND** `mascota_duenio_id_fkey`, `turno_mascota_id_fkey` y `turno_practica_practica_id_fkey` tienen `confdeltype = 'r'` (RESTRICT)
- **AND** ninguna clave foránea queda con la regla por defecto `NO ACTION` (`'a'`)

#### Scenario: Mascota con un dueño inexistente
- **GIVEN** que no existe el dueño 999
- **WHEN** se inserta una mascota con `duenio_id = 999`
- **THEN** la base rechaza la escritura con SQLSTATE `23503` y restricción `mascota_duenio_id_fkey`

#### Scenario: Práctica inexistente en un turno
- **GIVEN** un turno existente y que no existe la práctica 999
- **WHEN** se inserta una fila de `turno_practica` con `practica_id = 999`
- **THEN** la base rechaza la escritura con SQLSTATE `23503` y restricción `turno_practica_practica_id_fkey`

#### Scenario: Ficha o turno con referencia inexistente
- **GIVEN** que no existen el dueño 999 ni la mascota 999
- **WHEN** se inserta una ficha con `duenio_id = 999`, o un turno con `mascota_id = 999`
- **THEN** la base rechaza cada escritura con SQLSTATE `23503` y restricción `ficha_duenio_duenio_id_fkey` o `turno_mascota_id_fkey`, respectivamente

### Requirement: Índices de las claves foráneas y su justificación
La base SHALL tener índice en `mascota.duenio_id` (`ix_mascota_duenio_id`), `turno.mascota_id` (`ix_turno_mascota_id`) y `turno_practica.practica_id` (`ix_turno_practica_practica_id`), porque PostgreSQL no indexa solo una clave foránea. `ficha_duenio.duenio_id`, `duenio.email` y `practica.nombre` MUST quedar indexados sólo por su restricción UNIQUE, y `turno_practica.turno_id` MUST NOT tener índice propio: lo sirve el índice de la clave primaria compuesta, de la que es la primera columna. El `README.md` MUST explicarlo en una o dos líneas. Trazabilidad: Ej. 3 ("índices y su justificación"); DD-12.

#### Scenario: Índices exactos de cada tabla
- **GIVEN** el esquema recién creado
- **WHEN** se consultan los índices en `pg_indexes`
- **THEN** `duenio` tiene sólo `duenio_pkey` y `uq_duenio_email`; `ficha_duenio` sólo `ficha_duenio_pkey` y `uq_ficha_duenio_duenio_id`; `mascota` sólo `mascota_pkey` e `ix_mascota_duenio_id`; `practica` sólo `practica_pkey` y `uq_practica_nombre`; `turno` sólo `turno_pkey` e `ix_turno_mascota_id`; `turno_practica` sólo `turno_practica_pkey` e `ix_turno_practica_practica_id`

#### Scenario: turno_practica.turno_id no tiene índice propio
- **GIVEN** el esquema recién creado
- **WHEN** se buscan índices de `turno_practica` cuya primera columna sea `turno_id`
- **THEN** el único es `turno_practica_pkey`, sobre `(turno_id, practica_id)`

#### Scenario: El README justifica el índice ausente
- **GIVEN** el repositorio
- **WHEN** se lee la sección "Índice de `turno_practica.turno_id`" del `README.md`
- **THEN** explica en una o dos líneas que `turno_id` es la primera columna de la clave primaria compuesta, cuyo índice B-tree ya sirve las búsquedas y el borrado en cascada por `turno_id`

### Requirement: Navegación en los dos extremos de cada clave foránea
Cada una de las cinco claves foráneas SHALL poder recorrerse desde los dos extremos, y los dos extremos MUST mantenerse consistentes entre sí: `Duenio.ficha` ↔ `FichaDuenio.duenio`, `Duenio.mascotas` ↔ `Mascota.duenio`, `Mascota.turnos` ↔ `Turno.mascota`, `Turno.practicas` ↔ `TurnoPractica.turno` y `Practica.turnos` ↔ `TurnoPractica.practica`. `Duenio.ficha` MUST devolver un único objeto (o nada si el dueño no tiene ficha), no una lista; los lados "muchos" MUST devolver listas. Toda la navegación MUST poder cargarse por adelantado en la misma consulta (carga anticipada), sin depender de la carga perezosa. `TurnoPractica` MUST ser una entidad propia que guarda `precio_unitario`, el dato de la relación. Trazabilidad: Ej. 3 ("La navegación"); "Cada relación se declara en los dos extremos… `Duenio.ficha` devuelve un objeto y no una lista"; regla dura 4 (lecturas eager).

#### Scenario: La ficha de un dueño es un objeto
- **GIVEN** la base con los datos iniciales
- **WHEN** se lee el dueño 1 cargando su ficha por adelantado
- **THEN** `ficha` es un único objeto ficha cuyo `duenio_id` es 1, no una lista
- **AND** al leer el dueño 2 del mismo modo, `ficha` está vacía (`None`)

#### Scenario: Las colecciones son listas en ambos sentidos
- **GIVEN** la base con los datos iniciales
- **WHEN** se lee el dueño 1 cargando sus mascotas por adelantado
- **THEN** `mascotas` es una lista con "Toby" y "Mishi"
- **AND** cada mascota de la lista navega de vuelta a ese mismo dueño

#### Scenario: Un turno se lee con su mascota y sus prácticas del catálogo
- **GIVEN** la base con los datos iniciales
- **WHEN** se lee el turno 1 cargando por adelantado su mascota y sus prácticas con la práctica del catálogo de cada una
- **THEN** la mascota es "Mishi" y las prácticas son "Consulta" (`precio_unitario` 15000.00) y "Desparasitación" (8000.00)
- **AND** todos esos datos siguen disponibles después de cerrar la sesión, sin nuevas consultas

#### Scenario: Los extremos se mantienen consistentes en memoria
- **GIVEN** un dueño y una mascota nuevos, todavía sin guardar
- **WHEN** se asigna el dueño a la mascota
- **THEN** la mascota aparece en la lista `mascotas` del dueño sin consultar la base

#### Scenario: Las prácticas nacen con su turno
- **GIVEN** una mascota y dos prácticas existentes
- **WHEN** se crea un turno nuevo, se agregan a su lista `practicas` dos filas con su `precio_unitario` y se guarda sólo el turno, en una única transacción
- **THEN** la base contiene el turno y sus dos filas de `turno_practica` con el `turno_id` del turno nuevo

### Requirement: El borrado lo decide la base, no el ORM
Al borrar a través del ORM una fila del lado "uno" de una clave foránea, el ORM SHALL emitir sólo el `DELETE` de esa fila: MUST NOT cargar las filas hijas para borrarlas, MUST NOT emitir `DELETE` de las filas hijas y MUST NOT vaciar (poner en `NULL`) su clave foránea, estén o no cargadas en la sesión. La base aplica la regla: con CASCADE borra las hijas, con RESTRICT rechaza el borrado. Trazabilidad: Ej. 3 ("El borrado del turno lo decide la base, con ON DELETE CASCADE, y no el ORM… `passive_deletes`"); RN-08, RN-09; caso C-05 de la consigna (el 409 y el 204 los producen los endpoints de C-03 y C-06); regla dura 3.

#### Scenario: Borrar un turno sin sus prácticas cargadas
- **GIVEN** el turno 1 con dos prácticas, leído sin cargar sus prácticas
- **WHEN** se borra el turno 1 a través del ORM y se confirma la transacción
- **THEN** las sentencias emitidas no incluyen ningún `SELECT`, `UPDATE` ni `DELETE` sobre `turno_practica`, e incluyen el `DELETE` de `turno`
- **AND** `turno_practica` ya no tiene filas con `turno_id = 1`
- **AND** las prácticas 1 y 2 siguen en el catálogo

#### Scenario: Borrar un turno con sus prácticas cargadas
- **GIVEN** el turno 1 leído con sus prácticas cargadas por adelantado
- **WHEN** se borra el turno 1 a través del ORM y se confirma la transacción
- **THEN** las sentencias emitidas no incluyen ningún `UPDATE` ni `DELETE` sobre `turno_practica`
- **AND** `turno_practica` ya no tiene filas con `turno_id = 1`

#### Scenario: Borrar un dueño con mascotas se rechaza
- **GIVEN** el dueño 1, con ficha y dos mascotas, leído con o sin sus mascotas cargadas
- **WHEN** se lo borra a través del ORM y se confirma la transacción
- **THEN** la base rechaza el borrado con SQLSTATE `23503` y restricción `mascota_duenio_id_fkey`
- **AND** el ORM no emitió ningún `UPDATE` sobre `mascota` ni sobre `ficha_duenio`
- **AND** el dueño 1, su ficha y sus mascotas siguen en la base

#### Scenario: Borrar un dueño con ficha y sin mascotas
- **GIVEN** un dueño con ficha y sin mascotas, leído con o sin su ficha cargada
- **WHEN** se lo borra a través del ORM y se confirma la transacción
- **THEN** el borrado se acepta y la ficha desaparece con el dueño (CASCADE)
- **AND** el ORM no emitió `UPDATE` ni `DELETE` sobre `ficha_duenio`

#### Scenario: Borrar una mascota con turnos o una práctica usada se rechaza
- **GIVEN** la mascota 2 ("Mishi"), que tiene el turno 1, y la práctica 1 ("Consulta"), usada en el turno 1
- **WHEN** se borra cada una a través del ORM y se confirma la transacción
- **THEN** la base rechaza cada borrado con SQLSTATE `23503` y restricción `turno_mascota_id_fkey` o `turno_practica_practica_id_fkey`, respectivamente

#### Scenario: Borrar una mascota sin turnos o una práctica sin usar se acepta
- **GIVEN** la mascota 1 ("Toby"), sin turnos, y la práctica 4 ("Vacuna quíntuple"), sin turnos
- **WHEN** se borra cada una a través del ORM y se confirma la transacción
- **THEN** la base acepta cada borrado
