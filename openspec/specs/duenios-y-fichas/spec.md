# duenios-y-fichas Specification

## Purpose
Expone el recurso dueño de la veterinaria: alta, detalle con su ficha, edición parcial, borrado, alta de la ficha y listado de sus mascotas, con contratos de entrada y salida separados de las tablas y los códigos HTTP de la consigna. Las reglas RN-01, RN-03 y RN-08 las garantiza la base, y las lecturas resuelven sus relaciones con un número fijo de consultas.

## Requirements

### Requirement: Alta de dueño
`POST /duenios/` SHALL recibir un cuerpo con exactamente `nombre` y `email` y responder **201** con `{"id", "nombre", "email"}` del dueño creado; el `id` lo genera la base y MUST NOT viajar en el cuerpo de alta. `nombre` MUST ser un texto no vacío después de quitar los espacios de los extremos, que se guarda sin esos espacios; `email` MUST tener formato de email, y su dominio se guarda en minúsculas (la parte local se conserva como se envió). Un cuerpo que no cumple el contrato (campo faltante, formato inválido, texto vacío, campo no declarado como `id`) MUST responder **422** sin escribir nada. Un email que ya tiene otro dueño MUST responder **409** con `{"detail": "Ya existe un dueño con ese email"}` sin agregar filas. Trazabilidad: Ej. 2 (DTO de alta sin `id`; 201/409/422); RN-01; caso C-02 de la consigna (email repetido).

#### Scenario: Alta válida
- **GIVEN** la base con los datos iniciales (dueños 1 y 2)
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Lucía Fernández", "email": "lucia.fernandez@example.com"}`
- **THEN** la respuesta es **201** con el cuerpo exacto `{"id": 3, "nombre": "Lucía Fernández", "email": "lucia.fernandez@example.com"}`
- **AND** `GET /duenios/3` responde **200** con ese dueño y `"ficha": null`

#### Scenario: Los textos se guardan sin espacios en los extremos y el dominio del email en minúsculas
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /duenios/` con `{"nombre": "  Lucía Fernández  ", "email": "Lucia.Fernandez@EXAMPLE.COM"}`
- **THEN** la respuesta es **201** con `"nombre": "Lucía Fernández"` y `"email": "Lucia.Fernandez@example.com"`

#### Scenario: Caso C-02 — email repetido
- **GIVEN** la base con los datos iniciales (el dueño 1 tiene `ana.gomez@example.com`)
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Otra Ana", "email": "ana.gomez@example.com"}`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "Ya existe un dueño con ese email"}`
- **AND** `duenio` sigue teniendo exactamente dos filas

#### Scenario: Email repetido con el dominio en otra capitalización
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Otra Ana", "email": "ana.gomez@EXAMPLE.com"}`
- **THEN** la respuesta es **409** con `{"detail": "Ya existe un dueño con ese email"}`

#### Scenario: Cuerpo que no cumple el contrato
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /duenios/` con cada uno de estos cuerpos: `{"nombre": "Lucía"}` (sin email), `{"email": "lucia@example.com"}` (sin nombre), `{"nombre": "Lucía", "email": "no-es-un-email"}`, `{"nombre": "   ", "email": "lucia@example.com"}`, `{"id": 7, "nombre": "Lucía", "email": "lucia@example.com"}`
- **THEN** cada respuesta es **422** y el error señala el campo culpable (`email`, `nombre`, `email`, `nombre` e `id`, respectivamente)
- **AND** `duenio` sigue teniendo exactamente dos filas

### Requirement: Detalle de un dueño con su ficha
`GET /duenios/{id}` SHALL responder **200** con `{"id", "nombre", "email", "ficha"}`, donde `ficha` es el objeto `{"id", "duenio_id", "telefono", "direccion"}` si el dueño tiene ficha, o `null` si no la tiene (nunca una lista). Si no existe un dueño con ese `id`, MUST responder **404** con `{"detail": "No existe el dueño"}`. Trazabilidad: Ej. 2 (`GET /duenios/{id}` → dueño con su ficha; 200/404/422); consigna "`Duenio.ficha` devuelve un objeto y no una lista".

#### Scenario: Dueño con ficha
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/1`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"id": 1, "nombre": "Ana Gómez", "email": "ana.gomez@example.com", "ficha": {"id": 1, "duenio_id": 1, "telefono": "11 5555-0101", "direccion": "Calle Falsa 123"}}`

#### Scenario: Dueño sin ficha
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/2`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"id": 2, "nombre": "Carlos Ruiz", "email": "carlos.ruiz@example.com", "ficha": null}`

#### Scenario: Dueño inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/999`
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`

### Requirement: Edición parcial de un dueño
`PATCH /duenios/{id}` SHALL aplicar sólo los campos presentes en el cuerpo (`nombre`, `email`, ambos opcionales) y dejar los demás como estaban, y responder **200** con el dueño con su ficha (mismo formato que el detalle). Un cuerpo vacío `{}` MUST responder **200** sin cambiar nada. Los campos enviados cumplen las mismas reglas que en el alta; enviar `null` en un campo, un campo no declarado o un valor inválido MUST responder **422** sin cambiar nada. Si el nuevo email ya lo tiene otro dueño, MUST responder **409** con `{"detail": "Ya existe un dueño con ese email"}` y el dueño MUST quedar sin cambios. Si el dueño no existe, MUST responder **404** con `{"detail": "No existe el dueño"}`. Trazabilidad: Ej. 2 ("El PATCH del dueño. Aplica sólo los campos enviados, con `exclude_unset`"; 200/404/409/422); RN-01.

#### Scenario: Sólo cambia el nombre
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/1` con `{"nombre": "Ana María Gómez"}`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"id": 1, "nombre": "Ana María Gómez", "email": "ana.gomez@example.com", "ficha": {"id": 1, "duenio_id": 1, "telefono": "11 5555-0101", "direccion": "Calle Falsa 123"}}`

#### Scenario: Sólo cambia el email
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/2` con `{"email": "carlos.ruiz@example.org"}`
- **THEN** la respuesta es **200** con `{"id": 2, "nombre": "Carlos Ruiz", "email": "carlos.ruiz@example.org", "ficha": null}`

#### Scenario: Cuerpo vacío no cambia nada
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/2` con `{}`
- **THEN** la respuesta es **200** con `{"id": 2, "nombre": "Carlos Ruiz", "email": "carlos.ruiz@example.com", "ficha": null}`

#### Scenario: El propio email no es un conflicto
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/1` con `{"email": "ana.gomez@example.com"}`
- **THEN** la respuesta es **200** y el dueño 1 queda igual

#### Scenario: Email de otro dueño
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/2` con `{"nombre": "Carlos R.", "email": "ana.gomez@example.com"}`
- **THEN** la respuesta es **409** con `{"detail": "Ya existe un dueño con ese email"}`
- **AND** `GET /duenios/2` sigue respondiendo `"nombre": "Carlos Ruiz"` y `"email": "carlos.ruiz@example.com"` (tampoco cambió el nombre)

#### Scenario: Cuerpo que no cumple el contrato
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/2` con cada uno de estos cuerpos: `{"nombre": null}`, `{"email": null}`, `{"email": "no-es-un-email"}`, `{"nombre": ""}`, `{"id": 5}`
- **THEN** cada respuesta es **422**
- **AND** el dueño 2 queda sin cambios

#### Scenario: Dueño inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/999` con `{"nombre": "Nadie"}`
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`
- **AND** `duenio` sigue teniendo exactamente dos filas

### Requirement: Borrado de un dueño
`DELETE /duenios/{id}` SHALL responder **204** sin cuerpo cuando el dueño existe y no tiene mascotas a su nombre; su ficha, si la tiene, MUST desaparecer con él (lo hace la base con `ON DELETE CASCADE`). Si el dueño tiene mascotas, MUST responder **409** con `{"detail": "No se puede borrar el dueño: tiene mascotas a su nombre"}` y MUST NOT borrar nada (ni el dueño, ni su ficha, ni sus mascotas). Si no existe, MUST responder **404** con `{"detail": "No existe el dueño"}`. Trazabilidad: Ej. 2 (204/404/409); RN-08; caso C-05 de la consigna (primera parte: borrar un dueño con mascotas → 409); PA-02 de C-02 (ficha en CASCADE).

#### Scenario: Caso C-05 (primera parte) — dueño con mascotas
- **GIVEN** la base con los datos iniciales (el dueño 1 tiene la ficha 1 y las mascotas 1 y 2)
- **WHEN** se hace `DELETE /duenios/1`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "No se puede borrar el dueño: tiene mascotas a su nombre"}`
- **AND** el dueño 1, su ficha 1 y las mascotas 1 y 2 siguen existiendo

#### Scenario: Dueño sin mascotas y con ficha
- **GIVEN** la base con los datos iniciales, un dueño 3 creado con `POST /duenios/` y su ficha creada con `POST /duenios/3/ficha`
- **WHEN** se hace `DELETE /duenios/3`
- **THEN** la respuesta es **204** sin cuerpo
- **AND** `GET /duenios/3` responde **404**
- **AND** `ficha_duenio` no tiene ninguna fila con `duenio_id = 3`

#### Scenario: Dueño sin mascotas ni ficha
- **GIVEN** la base con los datos iniciales y un dueño 3 recién creado, sin ficha ni mascotas
- **WHEN** se hace `DELETE /duenios/3`
- **THEN** la respuesta es **204** sin cuerpo
- **AND** `duenio` vuelve a tener exactamente los dueños 1 y 2

#### Scenario: Dueño inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `DELETE /duenios/999`
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`
- **AND** `duenio` sigue teniendo exactamente dos filas

#### Scenario: Dueño ya borrado
- **GIVEN** un dueño 3 recién creado y borrado con `DELETE /duenios/3` (**204**)
- **WHEN** se hace `DELETE /duenios/3` otra vez
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`

### Requirement: Alta de la ficha de un dueño
`POST /duenios/{id}/ficha` SHALL recibir un cuerpo con exactamente `telefono` y `direccion` (textos no vacíos después de quitar los espacios de los extremos) y responder **201** con `{"id", "duenio_id", "telefono", "direccion"}` de la ficha creada, con `duenio_id` igual al `id` de la ruta. El dueño de la ficha lo fija la ruta: ni `id` ni `duenio_id` MUST viajar en el cuerpo (un campo no declarado responde **422**). Si el dueño ya tiene ficha, MUST responder **409** con `{"detail": "El dueño ya tiene una ficha"}` y la ficha existente MUST quedar sin cambios. Si el dueño no existe, MUST responder **404** con `{"detail": "No existe el dueño"}`. Ninguno de los dos casos se averigua con una consulta previa: lo decide la base. Trazabilidad: Ej. 2 (201/404/409); RN-03; caso C-03 de la consigna (segunda ficha → 409); PA-01.

#### Scenario: Primera ficha de un dueño
- **GIVEN** la base con los datos iniciales (el dueño 2 no tiene ficha)
- **WHEN** se hace `POST /duenios/2/ficha` con `{"telefono": "11 5555-0202", "direccion": "Av. Siempre Viva 742"}`
- **THEN** la respuesta es **201** con el cuerpo exacto `{"id": 2, "duenio_id": 2, "telefono": "11 5555-0202", "direccion": "Av. Siempre Viva 742"}`
- **AND** `GET /duenios/2` responde con esa ficha en `ficha`

#### Scenario: Caso C-03 — segunda ficha para el mismo dueño
- **GIVEN** la base con los datos iniciales (el dueño 1 ya tiene la ficha 1)
- **WHEN** se hace `POST /duenios/1/ficha` con `{"telefono": "11 5555-9999", "direccion": "Otra dirección 1"}`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "El dueño ya tiene una ficha"}`
- **AND** `GET /duenios/1` sigue mostrando la ficha 1 con `"telefono": "11 5555-0101"` y `"direccion": "Calle Falsa 123"`

#### Scenario: Ficha para un dueño inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /duenios/999/ficha` con `{"telefono": "11 5555-0999", "direccion": "Calle 999"}`
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`
- **AND** `ficha_duenio` sigue teniendo una sola fila

#### Scenario: Cuerpo que no cumple el contrato
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /duenios/2/ficha` con cada uno de estos cuerpos: `{"telefono": "11 5555-0202"}` (sin dirección), `{"telefono": "", "direccion": "Av. Siempre Viva 742"}`, `{"duenio_id": 1, "telefono": "11 5555-0202", "direccion": "Av. Siempre Viva 742"}`
- **THEN** cada respuesta es **422**
- **AND** el dueño 2 sigue sin ficha

### Requirement: Mascotas de un dueño
`GET /duenios/{id}/mascotas` SHALL responder **200** con la lista de las mascotas del dueño, cada una `{"id", "nombre", "especie", "duenio_id"}`, ordenada por `id` ascendente; un dueño sin mascotas responde **200** con `[]`. Si el dueño no existe, MUST responder **404** con `{"detail": "No existe el dueño"}`, distinguible de un dueño sin mascotas. Trazabilidad: Ej. 2 (`GET /duenios/{id}/mascotas` → 200/404); PA-09.

#### Scenario: Dueño con dos mascotas
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/1/mascotas`
- **THEN** la respuesta es **200** con el cuerpo exacto `[{"id": 1, "nombre": "Toby", "especie": "perro", "duenio_id": 1}, {"id": 2, "nombre": "Mishi", "especie": "gato", "duenio_id": 1}]`

#### Scenario: Dueño con una mascota
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/2/mascotas`
- **THEN** la respuesta es **200** con `[{"id": 3, "nombre": "Luna", "especie": "perro", "duenio_id": 2}]`

#### Scenario: Dueño sin mascotas
- **GIVEN** la base con los datos iniciales y un dueño 3 recién creado
- **WHEN** se hace `GET /duenios/3/mascotas`
- **THEN** la respuesta es **200** con `[]`

#### Scenario: Dueño inexistente
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/999/mascotas`
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`

### Requirement: Lecturas del dueño con un número fijo de consultas
Toda respuesta del módulo que incluye datos de una relación del dueño SHALL obtenerlos con carga anticipada declarada en la misma consulta que lee al dueño, nunca con carga perezosa: la ficha (relación "a uno") en la misma sentencia que el dueño, y las mascotas (colección) en una única sentencia adicional. La cantidad de sentencias SQL MUST ser la misma con o sin ficha y MUST NOT crecer con la cantidad de mascotas. Trazabilidad: Ej. 5 ("Lo mismo vale para el [detalle] de un dueño con su ficha"; `joinedload` para «a uno», `selectinload` para colecciones; "Nada perezoso").

#### Scenario: El detalle con y sin ficha usa la misma cantidad de consultas
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `GET /duenios/1` (con ficha) y luego `GET /duenios/2` (sin ficha), contando las sentencias SQL que la aplicación envía en cada petición
- **THEN** cada petición envía exactamente una sentencia: un `SELECT` sobre `duenio` que incluye `ficha_duenio` en la misma sentencia

#### Scenario: Las mascotas del dueño no multiplican las consultas
- **GIVEN** la base con los datos iniciales y un dueño 3 con cuatro mascotas agregadas directamente en la base
- **WHEN** se hace `GET /duenios/2/mascotas` (una mascota), `GET /duenios/1/mascotas` (dos) y `GET /duenios/3/mascotas` (cuatro)
- **THEN** cada petición envía exactamente dos sentencias SQL: una sobre `duenio` y una sobre `mascota`

#### Scenario: El PATCH obtiene la ficha en la misma consulta que lee al dueño
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `PATCH /duenios/1` con `{"nombre": "Ana María Gómez"}`
- **THEN** la respuesta **200** incluye la ficha 1
- **AND** la petición envía exactamente dos sentencias SQL: un `SELECT` sobre `duenio` que incluye `ficha_duenio` y un `UPDATE duenio`
