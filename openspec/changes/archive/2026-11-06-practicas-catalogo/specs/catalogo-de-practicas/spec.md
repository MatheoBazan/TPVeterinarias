## Purpose

Expone el catálogo de prácticas de la veterinaria: alta de una práctica con su precio y listado completo del catálogo, con contratos de entrada y salida separados de la tabla y los códigos HTTP de la consigna. RN-02 (nombre único) la garantiza la base sin consulta previa y RN-04 (precio mayor que cero) la validan el contrato y el CHECK de la base.

## ADDED Requirements

### Requirement: Alta de práctica
`POST /practicas/` SHALL recibir un cuerpo con exactamente `nombre` y `precio` y responder **201** con `{"id", "nombre", "precio"}` de la práctica creada. El `id` lo genera la base y MUST NOT viajar en el cuerpo. `nombre` MUST ser un texto no vacío tras quitar los espacios de los extremos, y se guarda sin ellos. Trazabilidad: Ej. 2 (DTO de alta sin `id`; 201); US-009.

#### Scenario: Alta válida
- **GIVEN** la base con los datos iniciales (prácticas 1 a 4)
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Castración", "precio": "30000.00"}`
- **THEN** la respuesta es **201** con el cuerpo exacto `{"id": 5, "nombre": "Castración", "precio": "30000.00"}`
- **AND** `GET /practicas/` incluye esa práctica como último elemento

#### Scenario: El nombre se guarda sin espacios en los extremos
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "  Ecografía  ", "precio": "25000.00"}`
- **THEN** la respuesta es **201** con `"nombre": "Ecografía"`

### Requirement: Contrato del precio
`precio` SHALL ser un monto decimal exacto, enviado como string o como número JSON, mayor que cero y que entre en `NUMERIC(10,2)`: a lo sumo 8 dígitos enteros y 2 decimales. Un precio `0` o negativo MUST responder **422** sin escribir nada (RN-04). La respuesta MUST devolver el precio como string con exactamente 2 decimales. Trazabilidad: RN-04; Ej. 2 (422); consigna "dinero con `Decimal`, nunca `float`"; US-009.

#### Scenario: Precio cero o negativo
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Gratis", "precio": "0"}`, y luego con `{"nombre": "Negativa", "precio": "-100.00"}`
- **THEN** cada respuesta es **422** con un error en `["body", "precio"]` de tipo `greater_than`
- **AND** `practica` sigue teniendo exactamente cuatro filas

#### Scenario: Precio que no entra en NUMERIC(10,2)
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Fracción", "precio": "12.345"}`, y luego con `{"nombre": "Carísima", "precio": "100000000.00"}`
- **THEN** cada respuesta es **422** con un error en `["body", "precio"]` (más de 2 decimales y más de 8 dígitos enteros, respectivamente)
- **AND** `practica` sigue teniendo exactamente cuatro filas

#### Scenario: Precio que no es un número
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Rara", "precio": "abc"}`, y luego con `{"nombre": "Rara", "precio": "NaN"}`
- **THEN** cada respuesta es **422** con un error en `["body", "precio"]`

#### Scenario: El precio se devuelve como string con 2 decimales
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Control", "precio": 9000}` (número JSON entero), y luego con `{"nombre": "Curación", "precio": "4500.5"}`
- **THEN** las respuestas son **201** con `"precio": "9000.00"` y `"precio": "4500.50"`, respectivamente
- **AND** `GET /practicas/` devuelve esas dos prácticas con los mismos strings

### Requirement: Cuerpo de alta que no cumple el contrato
Un cuerpo de `POST /practicas/` al que le falta `nombre` o `precio`, con un `nombre` vacío o con un campo no declarado (por ejemplo `id`) MUST responder **422** con el formato de validación de FastAPI, señalando el campo culpable, sin escribir nada. Trazabilidad: Ej. 2 (DTO de alta sin `id`; 422); regla dura 7 (`extra='forbid'`).

#### Scenario: Campo faltante, nombre vacío o campo no declarado
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con cada uno de estos cuerpos: `{"precio": "100.00"}`, `{"nombre": "Sin precio"}`, `{"nombre": "   ", "precio": "100.00"}`, `{"id": 9, "nombre": "Con id", "precio": "100.00"}`
- **THEN** cada respuesta es **422** y el error señala `["body", "nombre"]`, `["body", "precio"]`, `["body", "nombre"]` y `["body", "id"]` (tipo `extra_forbidden`), respectivamente
- **AND** `practica` sigue teniendo exactamente cuatro filas

### Requirement: Nombre de práctica único sin consulta previa
Un alta cuyo `nombre` ya existe en el catálogo (comparado tal como queda guardado, sensible a mayúsculas) MUST responder **409** con `{"detail": "Ya existe una práctica con ese nombre"}` sin agregar filas. La decisión la toma la restricción UNIQUE de la base: MUST NOT haber una consulta previa del tipo "¿ya existe?". Trazabilidad: RN-02; caso C-02 de la consigna (nombre de práctica repetido → 409 con mensaje propio); regla dura 3.

#### Scenario: Caso C-02 — nombre de práctica repetido
- **GIVEN** la base con los datos iniciales (la práctica 1 se llama `Consulta`)
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Consulta", "precio": "20000.00"}`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "Ya existe una práctica con ese nombre"}`
- **AND** `practica` sigue teniendo exactamente cuatro filas y la práctica 1 conserva su precio `15000.00`

#### Scenario: El nombre repetido con espacios en los extremos también choca
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "  Vacuna antirrábica ", "precio": "1.00"}`
- **THEN** la respuesta es **409** con `{"detail": "Ya existe una práctica con ese nombre"}`

#### Scenario: El alta repetida no consulta antes de escribir
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Consulta", "precio": "20000.00"}`
- **THEN** la respuesta es **409**
- **AND** la única sentencia SQL que la aplicación envió a la base (sin contar `BEGIN`, `COMMIT`, `ROLLBACK`) es un `INSERT INTO practica`; ninguna sentencia `SELECT` la precedió

#### Scenario: Después del rechazo la siguiente alta funciona
- **GIVEN** que `POST /practicas/` con el nombre `Consulta` acaba de responder **409**
- **WHEN** se hace `POST /practicas/` con `{"nombre": "Castración", "precio": "30000.00"}`
- **THEN** la respuesta es **201** con `"nombre": "Castración"` y un `id` mayor que 4

### Requirement: Listado del catálogo
`GET /practicas/` SHALL responder **200** con una lista JSON de todas las prácticas, cada una `{"id", "nombre", "precio"}` con el precio como string de 2 decimales, ordenadas por `id` ascendente. Con el catálogo vacío MUST responder **200** con `[]`. La respuesta MUST obtenerse con una única consulta, sin importar cuántas prácticas haya. Trazabilidad: Ej. 2 (`GET /practicas/` → catálogo; 200); US-009.

#### Scenario: Catálogo inicial
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /practicas/`
- **THEN** la respuesta es **200** con el cuerpo exacto `[{"id": 1, "nombre": "Consulta", "precio": "15000.00"}, {"id": 2, "nombre": "Desparasitación", "precio": "8000.00"}, {"id": 3, "nombre": "Vacuna antirrábica", "precio": "12000.00"}, {"id": 4, "nombre": "Vacuna quíntuple", "precio": "14000.00"}]`

#### Scenario: Catálogo vacío
- **GIVEN** el esquema creado sin datos
- **WHEN** se hace `GET /practicas/`
- **THEN** la respuesta es **200** con `[]`

#### Scenario: Una sola consulta con cualquier tamaño de catálogo
- **GIVEN** la base con los datos iniciales, y luego la misma base con dos prácticas más dadas de alta
- **WHEN** se hace `GET /practicas/` en cada estado
- **THEN** en los dos casos la aplicación envía exactamente una sentencia `SELECT` sobre `practica`

### Requirement: El CHECK de la base rechaza un precio no positivo escrito por fuera de la API
Aunque la API ya valida el precio en el contrato, la base SHALL rechazar por su CHECK cualquier escritura directa con `precio <= 0`, y el catálogo MUST quedar sin cambios. El entregable `test/c08_check_precio.sql` lo demuestra; `test/practicas.http` documenta cómo ejecutarlo y cómo verificar por HTTP que el precio no cambió. Trazabilidad: RN-04; caso C-08 de la consigna.

#### Scenario: Caso C-08 — UPDATE directo con precio cero
- **GIVEN** la base con los datos iniciales
- **WHEN** se ejecuta directo en la base `UPDATE practica SET precio = 0 WHERE id = 1`
- **THEN** la base rechaza la sentencia con SQLSTATE `23514` sobre la restricción `ck_practica_precio_positivo`
- **AND** a continuación `GET /practicas/` responde **200** con la práctica 1 en `"precio": "15000.00"`
