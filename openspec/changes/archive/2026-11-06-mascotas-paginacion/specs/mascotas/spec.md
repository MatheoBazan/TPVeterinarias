# Spec Delta

## Purpose

Expone el recurso mascota de la veterinaria: alta con el id de un dueño existente, detalle de la mascota con su dueño y listado paginado con su envoltorio, con contratos separados de las tablas, los códigos HTTP de la consigna, la clave foránea garantizada por la base y lecturas con un número fijo de consultas.

## ADDED Requirements

### Requirement: Alta de mascota
`POST /mascotas/` SHALL recibir un cuerpo con exactamente `nombre`, `especie` y `duenio_id` (el id de un dueño existente) y responder **201** con `{"id", "nombre", "especie", "duenio_id"}` de la mascota creada. El `id` lo genera la base y MUST NOT viajar en el cuerpo. `nombre` y `especie` se guardan sin los espacios de los extremos. Trazabilidad: Ej. 2 (DTO de alta sin `id`; 201); Ej. 4 ("en la agregación viaja un id").

#### Scenario: Alta válida
- **GIVEN** la base con los datos iniciales (dueños 1 y 2; mascotas 1, 2 y 3)
- **WHEN** se hace `POST /mascotas/` con `{"nombre": "Rocky", "especie": "perro", "duenio_id": 2}`
- **THEN** la respuesta es **201** con el cuerpo exacto `{"id": 4, "nombre": "Rocky", "especie": "perro", "duenio_id": 2}`
- **AND** `GET /duenios/2/mascotas` responde **200** con las mascotas 3 y 4

#### Scenario: Los textos se guardan sin espacios en los extremos
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /mascotas/` con `{"nombre": "  Pelusa  ", "especie": " gato ", "duenio_id": 1}`
- **THEN** la respuesta es **201** con `"nombre": "Pelusa"` y `"especie": "gato"`

### Requirement: Alta con un dueño inexistente
Si `duenio_id` no corresponde a ningún dueño, `POST /mascotas/` MUST responder **409** con `{"detail": "No existe el dueño indicado"}` y MUST NOT guardar nada. La existencia del dueño la decide la clave foránea de la base al escribir: la API MUST NOT consultar al dueño antes del `INSERT`. Después del rechazo, la siguiente alta MUST funcionar. Trazabilidad: caso C-04 de la consigna (primera parte); regla derivada "mascota con dueño inexistente → 409 (violación de FK), no 404/422"; regla dura 3.

#### Scenario: Caso C-04 (primera parte) — mascota con un dueño inexistente
- **GIVEN** la base con los datos iniciales, sin dueño 999
- **WHEN** se hace `POST /mascotas/` con `{"nombre": "Fantasma", "especie": "gato", "duenio_id": 999}`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "No existe el dueño indicado"}`
- **AND** el cuerpo no contiene `mascota_duenio_id_fkey`, `foreign key`, `INSERT` ni `asyncpg`
- **AND** `mascota` sigue teniendo tres filas

#### Scenario: El rechazo lo decide un único INSERT, sin consultar al dueño
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /mascotas/` con `{"nombre": "Fantasma", "especie": "gato", "duenio_id": 999}`, contando las sentencias SQL que la aplicación envía
- **THEN** la respuesta es **409**
- **AND** la única sentencia SQL enviada (sin contar el control de la transacción: `BEGIN`, `COMMIT`, `ROLLBACK`) es un `INSERT INTO mascota`; ningún `SELECT` la precedió

#### Scenario: Ids de dueño cero o negativos también los rechaza la clave foránea
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /mascotas/` con `duenio_id` `0` y luego con `duenio_id` `-1` (con `nombre` y `especie` válidos)
- **THEN** cada respuesta es **409** con `{"detail": "No existe el dueño indicado"}`
- **AND** `mascota` sigue teniendo tres filas

#### Scenario: Después del rechazo la siguiente alta funciona
- **GIVEN** que `POST /mascotas/` con `duenio_id` `999` acaba de responder **409**
- **WHEN** se hace `POST /mascotas/` con `{"nombre": "Rocky", "especie": "perro", "duenio_id": 2}`
- **THEN** la respuesta es **201**
- **AND** `mascota` tiene cuatro filas

### Requirement: Contrato de entrada del alta de mascota
Un cuerpo de `POST /mascotas/` que no cumple el contrato MUST responder **422** con el formato de validación de FastAPI y MUST NOT escribir nada: campo faltante, `nombre` o `especie` vacíos después de quitar los espacios, `duenio_id` no entero o mayor que 2147483647, o un campo no declarado (por ejemplo `id`). Trazabilidad: Ej. 2 ("422 si el cuerpo … no cumple el contrato"; DTO de alta sin `id`); regla dura 7 (`extra="forbid"`).

#### Scenario: Cuerpos inválidos
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /mascotas/` con cada uno de estos cuerpos:
  - `{"especie": "perro", "duenio_id": 1}` → error en `["body", "nombre"]` con `type` `missing`
  - `{"nombre": "Rocky", "duenio_id": 1}` → `["body", "especie"]`, `missing`
  - `{"nombre": "Rocky", "especie": "perro"}` → `["body", "duenio_id"]`, `missing`
  - `{"nombre": "   ", "especie": "perro", "duenio_id": 1}` → `["body", "nombre"]`, `string_too_short`
  - `{"nombre": "Rocky", "especie": "", "duenio_id": 1}` → `["body", "especie"]`, `string_too_short`
  - `{"nombre": "Rocky", "especie": "perro", "duenio_id": "abc"}` → `["body", "duenio_id"]`, `int_parsing`
  - `{"nombre": "Rocky", "especie": "perro", "duenio_id": 2147483648}` → `["body", "duenio_id"]`, `less_than_equal`
  - `{"id": 9, "nombre": "Rocky", "especie": "perro", "duenio_id": 1}` → `["body", "id"]`, `extra_forbidden`
- **THEN** cada respuesta es **422** con un error en `detail` con el `loc` y el `type` indicados
- **AND** `mascota` sigue teniendo tres filas

### Requirement: Detalle de una mascota con su dueño
`GET /mascotas/{id}` SHALL responder **200** con `{"id", "nombre", "especie", "duenio_id", "duenio"}`, donde `duenio` es el objeto `{"id", "nombre", "email"}` de su dueño. Si no existe una mascota con ese `id`, MUST responder **404** con `{"detail": "No existe la mascota"}`. El `{id}` sigue el contrato de id de ruta de `contrato-de-errores` (no entero o sobre 2147483647 → 422 sin ejecutar el handler). Trazabilidad: Ej. 2 (`GET /mascotas/{id}` → mascota con su dueño; 200/404).

#### Scenario: Mascota del dueño 1
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/1`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"id": 1, "nombre": "Toby", "especie": "perro", "duenio_id": 1, "duenio": {"id": 1, "nombre": "Ana Gómez", "email": "ana.gomez@example.com"}}`

#### Scenario: Mascota del dueño 2
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/3`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2, "duenio": {"id": 2, "nombre": "Carlos Ruiz", "email": "carlos.ruiz@example.com"}}`

#### Scenario: Mascota inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/999`, `GET /mascotas/0` y `GET /mascotas/2147483647`
- **THEN** cada respuesta es **404** con el cuerpo exacto `{"detail": "No existe la mascota"}`

#### Scenario: Id de ruta inválido
- **WHEN** se hace `GET /mascotas/abc` y `GET /mascotas/2147483648`
- **THEN** cada respuesta es **422** con un error con `loc` `["path", "id"]` (`int_parsing` y `less_than_equal`)
- **AND** no se envía ninguna sentencia SQL

### Requirement: Envoltorio del listado de mascotas
`GET /mascotas/` SHALL responder **200** con `{"items", "total", "page", "size", "pages"}`: `items` son las mascotas de la página pedida, cada una `{"id", "nombre", "especie", "duenio_id"}`, ordenadas por `id` ascendente; `total` es la cantidad de mascotas; `page` y `size` son los valores usados; `pages` es `total / size` redondeado hacia arriba (`0` si no hay mascotas). Trazabilidad: Ej. 2 ("Devuelve el envoltorio de la sección 2.9"); PA-05; PA-12.

#### Scenario: Primera página con los valores por defecto
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"items": [{"id": 1, "nombre": "Toby", "especie": "perro", "duenio_id": 1}, {"id": 2, "nombre": "Mishi", "especie": "gato", "duenio_id": 1}, {"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2}], "total": 3, "page": 1, "size": 20, "pages": 1}`

#### Scenario: Última página incompleta
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?page=2&size=2`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"items": [{"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2}], "total": 3, "page": 2, "size": 2, "pages": 2}`

#### Scenario: Página exacta en el borde
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?page=1&size=3` y `GET /mascotas/?page=3&size=1`
- **THEN** la primera responde **200** con los ids `[1, 2, 3]`, `"total": 3` y `"pages": 1`
- **AND** la segunda responde **200** con los ids `[3]`, `"total": 3` y `"pages": 3`

#### Scenario: El orden es por id aunque cambie el orden físico de las filas
- **GIVEN** la base con los datos iniciales y la mascota 1 modificada directamente en la base después de las otras (su fila queda última en el almacenamiento)
- **WHEN** se hace `GET /mascotas/`
- **THEN** los ids de `items` son `[1, 2, 3]`

#### Scenario: Listado sin mascotas
- **GIVEN** el esquema recién creado, sin mascotas
- **WHEN** se hace `GET /mascotas/`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}`

### Requirement: Tamaño de página
El parámetro `size` SHALL valer 20 si no se envía y MUST ser un entero entre 1 y 100 inclusive; un valor fuera de ese rango o no entero MUST responder **422** con el formato de validación de FastAPI, con `loc` `["query", "size"]`, sin consultar la base. Trazabilidad: Ej. 2 ("`size` vale 20 por defecto y va de 1 a 100"); Ej. 2 ("422 si … los parámetros no cumplen el contrato").

#### Scenario: Tamaños en el límite
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?size=1` y `GET /mascotas/?size=100`
- **THEN** la primera responde **200** con un único item (id 1), `"size": 1` y `"pages": 3`
- **AND** la segunda responde **200** con los tres items, `"size": 100` y `"pages": 1`

#### Scenario: Tamaños inválidos
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?size=0`, `GET /mascotas/?size=101`, `GET /mascotas/?size=-5` y `GET /mascotas/?size=abc`
- **THEN** cada respuesta es **422** con un error con `loc` `["query", "size"]` (`type` `greater_than_equal`, `less_than_equal`, `greater_than_equal` e `int_parsing`, respectivamente)
- **AND** no se envía ninguna sentencia SQL

### Requirement: Rango de página
El parámetro `page` SHALL valer 1 si no se envía y MUST ser un entero mayor o igual a 1 (si no, **422** con `loc` `["query", "page"]` sin consultar la base). La página 1 MUST responder siempre, aun sin mascotas. Una página mayor que `pages` (o mayor que 1 si `pages` es 0) MUST responder **422** con `{"detail": [{"type": "pagina_fuera_de_rango", "loc": ["query", "page"], "msg": "La página pedida no existe", "input": <page>, "ctx": {"pages": <pages>}}]}`. Trazabilidad: Ej. 2; PA-05.

#### Scenario: Página más allá de pages
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?page=3&size=2`
- **THEN** la respuesta es **422** con el cuerpo exacto `{"detail": [{"type": "pagina_fuera_de_rango", "loc": ["query", "page"], "msg": "La página pedida no existe", "input": 3, "ctx": {"pages": 2}}]}`

#### Scenario: Página 2 con los valores por defecto
- **GIVEN** la base con los datos iniciales (3 mascotas, `pages` = 1)
- **WHEN** se hace `GET /mascotas/?page=2`
- **THEN** la respuesta es **422** con `detail[0].type` `pagina_fuera_de_rango` y `detail[0].ctx` `{"pages": 1}`

#### Scenario: Sin mascotas, sólo la primera página responde
- **GIVEN** el esquema recién creado, sin mascotas
- **WHEN** se hace `GET /mascotas/?page=1` y `GET /mascotas/?page=2`
- **THEN** la primera responde **200** con `"items": []` y `"pages": 0`
- **AND** la segunda responde **422** con `detail[0].type` `pagina_fuera_de_rango` y `detail[0].ctx` `{"pages": 0}`

#### Scenario: Páginas inválidas
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?page=0`, `GET /mascotas/?page=-1` y `GET /mascotas/?page=abc`
- **THEN** cada respuesta es **422** con un error con `loc` `["query", "page"]` (`type` `greater_than_equal`, `greater_than_equal` e `int_parsing`, respectivamente)
- **AND** no se envía ninguna sentencia SQL

### Requirement: Lecturas de mascotas con un número fijo de consultas
Las lecturas del módulo SHALL usar un número fijo de sentencias SQL, sin carga perezosa: el detalle MUST obtener al dueño en la misma sentencia que lee a la mascota (una sola sentencia); el listado MUST enviar exactamente dos sentencias (el conteo y la página) cualquiera sea el tamaño de la página, y una sola (el conteo) cuando la página está fuera de rango. Trazabilidad: Ej. 5 (carga anticipada declarada en la misma consulta; `joinedload` para «a uno»; número fijo de consultas).

#### Scenario: El detalle usa una sola consulta
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/1` y luego `GET /mascotas/3`, contando las sentencias SQL que la aplicación envía en cada petición
- **THEN** cada petición envía exactamente una sentencia: un `SELECT` sobre `mascota` que incluye `duenio` en la misma sentencia

#### Scenario: El listado no multiplica las consultas con el tamaño de la página
- **GIVEN** la base con los datos iniciales y 22 mascotas más agregadas directamente en la base (25 en total)
- **WHEN** se hace `GET /mascotas/?size=1`, `GET /mascotas/?size=3` y `GET /mascotas/` (20 items), contando las sentencias SQL de cada petición
- **THEN** cada petición envía exactamente dos sentencias: un `SELECT` de conteo sobre `mascota` y un `SELECT` de la página sobre `mascota`
- **AND** ninguna sentencia consulta `duenio`

#### Scenario: Una página fuera de rango sólo cuenta
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /mascotas/?page=5`, contando las sentencias SQL
- **THEN** la respuesta es **422** y la petición envía exactamente una sentencia: el `SELECT` de conteo sobre `mascota`
