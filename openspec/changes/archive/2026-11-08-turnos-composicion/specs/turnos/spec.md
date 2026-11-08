# Spec Delta — turnos

## Purpose

Expone el turno de la veterinaria como un agregado con sus prácticas: reserva en una sola transacción con el precio copiado del catálogo y el total calculado por el servidor, detalle con la mascota y las prácticas en un número fijo de consultas, y borrado cuyas prácticas elimina la base.

## ADDED Requirements

### Requirement: Contrato de alta de turno
`POST /turnos/` SHALL recibir exactamente `mascota_id` (entero), `fecha` (fecha y hora ISO 8601 con zona horaria), `motivo` (texto no vacío, sin espacios en los extremos) y `practicas` (lista de `{"practica_id": <entero>}`). El cuerpo MUST NOT llevar `id`, precios ni total: un campo no declarado, en el turno o en una práctica, responde **422**. Trazabilidad: Ej. 2 (DTO de alta sin `id`); Ej. 4; RN-06; regla dura 7.

#### Scenario: Un precio o un total en el cuerpo se rechaza
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `{"mascota_id": 1, "fecha": "2026-11-12T10:30:00-03:00", "motivo": "Control", "total": "1.00", "practicas": [{"practica_id": 1}]}`
- **THEN** la respuesta es **422**
- **AND** `turno` sigue teniendo una fila

#### Scenario: Un precio dentro de una práctica se rechaza
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `"practicas": [{"practica_id": 1, "precio_unitario": "1.00"}]` y el resto válido
- **THEN** la respuesta es **422**
- **AND** `turno` sigue teniendo una fila

#### Scenario: Motivo vacío
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `"motivo": "   "` y el resto válido
- **THEN** la respuesta es **422**

### Requirement: El turno tiene al menos una práctica
Si `practicas` es una lista vacía o falta, `POST /turnos/` MUST responder **422** con el formato de validación de FastAPI y MUST NOT enviar ninguna sentencia SQL. Trazabilidad: RN-05.

#### Scenario: Lista de prácticas vacía
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `{"mascota_id": 1, "fecha": "2026-11-12T10:30:00-03:00", "motivo": "Control", "practicas": []}`
- **THEN** la respuesta es **422** con un error cuyo `loc` es `["body", "practicas"]`
- **AND** la aplicación no envió ninguna sentencia SQL

### Requirement: Fecha con zona horaria obligatoria
`fecha` MUST incluir zona horaria (`Z` o un desplazamiento como `-03:00`). Una fecha sin zona MUST responder **422** sin enviar sentencias SQL: la API no supone la zona del servidor. Trazabilidad: PA-10; DD-11.

#### Scenario: Fecha sin zona horaria
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `"fecha": "2026-11-12T10:30:00"` y el resto válido
- **THEN** la respuesta es **422** con un error cuyo `loc` es `["body", "fecha"]`
- **AND** `turno` sigue teniendo una fila

### Requirement: Reserva con precio copiado y total del servidor
Un alta válida SHALL guardar el turno y una fila de `turno_practica` por práctica, con `precio_unitario` igual al precio del catálogo en ese momento y `total` igual a la suma de esos precios, y responder **201** con el formato de la consigna: `fecha` en UTC con sufijo `Z`, dinero como string con dos decimales, la mascota y las prácticas ordenadas por `practica_id`. Trazabilidad: Ej. 4; RN-06; DD-10; DD-11; caso C-06 de la consigna.

#### Scenario: Caso C-06 — el ejemplo de la consigna
- **GIVEN** la base recién reiniciada con los datos iniciales (ya existe el turno 1)
- **WHEN** se hace `POST /turnos/` con `{"mascota_id": 1, "fecha": "2026-11-12T10:30:00-03:00", "motivo": "Control anual", "practicas": [{"practica_id": 1}, {"practica_id": 3}]}`
- **THEN** la respuesta es **201** con el cuerpo exacto `{"id": 2, "fecha": "2026-11-12T13:30:00Z", "motivo": "Control anual", "total": "27000.00", "mascota": {"id": 1, "nombre": "Toby", "especie": "perro"}, "practicas": [{"practica_id": 1, "nombre": "Consulta", "precio_unitario": "15000.00"}, {"practica_id": 3, "nombre": "Vacuna antirrábica", "precio_unitario": "12000.00"}]}`
- **AND** `turno_practica` tiene dos filas con `turno_id` 2, con `precio_unitario` 15000.00 y 12000.00

#### Scenario: Las prácticas se devuelven ordenadas por id
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `"practicas": [{"practica_id": 4}, {"practica_id": 1}, {"practica_id": 2}]` y el resto válido
- **THEN** la respuesta es **201** con las prácticas en el orden `practica_id` 1, 2, 4 y `"total": "37000.00"`

#### Scenario: Precio congelado ante un cambio del catálogo
- **GIVEN** que `POST /turnos/` con la práctica 1 respondió **201** con `"precio_unitario": "15000.00"`
- **WHEN** el precio de la práctica 1 se cambia a 20000.00 directamente en la base y se hace `GET /turnos/{id}` de ese turno
- **THEN** la respuesta sigue mostrando `"precio_unitario": "15000.00"` y el mismo `total`

### Requirement: Práctica inexistente rechaza todo el turno
Si alguna `practica_id` no existe, `POST /turnos/` MUST responder **409** con `{"detail": "No existe la práctica indicada"}` y MUST NOT guardar nada (ni el turno ni ninguna de sus prácticas). La existencia la decide la base al escribir: la API MUST NOT consultar el catálogo antes de escribir. Trazabilidad: Ej. 4 ("todo o nada"); caso C-04 de la consigna (segunda parte); regla dura 3.

#### Scenario: Caso C-04 (segunda parte) — turno con una práctica inexistente
- **GIVEN** la base con los datos iniciales, sin práctica 999
- **WHEN** se hace `POST /turnos/` con `{"mascota_id": 1, "fecha": "2026-11-12T10:30:00-03:00", "motivo": "Control", "practicas": [{"practica_id": 1}, {"practica_id": 999}]}`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "No existe la práctica indicada"}`
- **AND** `turno` sigue teniendo una fila y `turno_practica` dos filas (las del turno 1)

#### Scenario: Ninguna sentencia de lectura precede a la escritura
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con una práctica inexistente, contando las sentencias SQL que envía la aplicación
- **THEN** la respuesta es **409**
- **AND** la primera sentencia enviada (sin contar `BEGIN`, `COMMIT`, `ROLLBACK`) es un `INSERT INTO turno`

#### Scenario: Después del rechazo la siguiente reserva funciona
- **GIVEN** que una reserva con la práctica 999 acaba de responder **409**
- **WHEN** se hace `POST /turnos/` con la práctica 1 y el resto válido
- **THEN** la respuesta es **201**

### Requirement: Práctica repetida rechazada por la base
Si la misma `practica_id` aparece dos veces en `practicas`, `POST /turnos/` MUST responder **409** con `{"detail": "Una práctica no puede repetirse en el mismo turno"}` y MUST NOT guardar nada. El DTO MUST NOT rechazar la repetición: lo decide la clave primaria compuesta de `turno_practica`. Trazabilidad: RN-07; DD-09.

#### Scenario: Práctica repetida
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /turnos/` con `"practicas": [{"practica_id": 1}, {"practica_id": 1}]` y el resto válido
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "Una práctica no puede repetirse en el mismo turno"}`
- **AND** `turno` sigue teniendo una fila

### Requirement: Mascota inexistente
Si `mascota_id` no corresponde a ninguna mascota, `POST /turnos/` MUST responder **409** con `{"detail": "No existe la mascota indicada"}` y MUST NOT guardar nada; lo decide la clave foránea de `turno.mascota_id`. Trazabilidad: PA-13; SU-02; mismo criterio que el caso C-04 de la consigna.

#### Scenario: Turno para una mascota inexistente
- **GIVEN** la base con los datos iniciales, sin mascota 999
- **WHEN** se hace `POST /turnos/` con `"mascota_id": 999` y prácticas válidas
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "No existe la mascota indicada"}`
- **AND** `turno` sigue teniendo una fila

### Requirement: Detalle de turno
`GET /turnos/{id}` SHALL responder **200** con el mismo formato que el alta. Si el turno no existe MUST responder **404** con `{"detail": "No existe el turno"}`. El `id` sigue el contrato de ids de ruta (`contrato-de-errores`). Trazabilidad: Ej. 5; caso C-07 de la consigna.

#### Scenario: Detalle del turno del seed
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /turnos/1`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"id": 1, "fecha": "2026-11-10T12:00:00Z", "motivo": "Control y desparasitación", "total": "23000.00", "mascota": {"id": 2, "nombre": "Mishi", "especie": "gato"}, "practicas": [{"practica_id": 1, "nombre": "Consulta", "precio_unitario": "15000.00"}, {"practica_id": 2, "nombre": "Desparasitación", "precio_unitario": "8000.00"}]}`

#### Scenario: Turno inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /turnos/999`
- **THEN** la respuesta es **404** con `{"detail": "No existe el turno"}`

### Requirement: Detalle en un número fijo de consultas
`GET /turnos/{id}` MUST obtener el turno, su mascota y sus prácticas (con el nombre de cada una) en un número fijo de sentencias SQL que no depende de la cantidad de prácticas, sin carga perezosa. Trazabilidad: Ej. 5; caso C-07 de la consigna; regla dura 4; DD-14.

#### Scenario: Caso C-07 — mismo número de consultas con una y con tres prácticas
- **GIVEN** un turno con una práctica y otro con tres prácticas
- **WHEN** se hace `GET /turnos/{id}` de cada uno, contando las sentencias SQL que envía la aplicación
- **THEN** las dos respuestas son **200**
- **AND** las dos lecturas envían la misma cantidad de sentencias `SELECT`, y esa cantidad es 2

### Requirement: Borrado de turno
`DELETE /turnos/{id}` SHALL responder **204** sin cuerpo y borrar el turno; sus filas de `turno_practica` las borra la base (`ON DELETE CASCADE`). Si el turno no existe MUST responder **404** con `{"detail": "No existe el turno"}`. Trazabilidad: RN-09; caso C-05 de la consigna (segunda parte).

#### Scenario: Caso C-05 (segunda parte) — borrar el turno 1
- **GIVEN** la base con los datos iniciales (turno 1 con dos prácticas)
- **WHEN** se hace `DELETE /turnos/1`
- **THEN** la respuesta es **204**
- **AND** `GET /turnos/1` responde **404**
- **AND** `turno_practica` no tiene filas con `turno_id` 1
- **AND** las prácticas 1 y 2 siguen en el catálogo

#### Scenario: Borrar un turno inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `DELETE /turnos/999`
- **THEN** la respuesta es **404** con `{"detail": "No existe el turno"}`
