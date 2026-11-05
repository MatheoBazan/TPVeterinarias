# contrato-de-errores Specification

## Purpose
Define el contrato de errores que comparten todos los módulos de la API: el cuerpo de los 404 y 409, cómo una escritura rechazada por la base se convierte en 404 o 409 con mensaje propio sin consultas previas y deshaciendo la transacción, que un rechazo no previsto responde 409 con un mensaje genérico propio y se registra, y el 422 de un id de ruta no entero o sobre la cota sin ejecutar el handler. Lo fija el módulo de dueños y lo reutilizan mascotas, prácticas y turnos.

## Requirements

### Requirement: Cuerpo de los errores 404 y 409
Toda respuesta 404 o 409 de la API SHALL tener el cuerpo JSON `{"detail": "<mensaje>"}`, con `detail` como única clave y un mensaje propio en español escrito por la aplicación. El mensaje MUST NOT contener SQL, nombres de restricciones, nombres de tablas ni texto del controlador de la base. Las respuestas 422 SHALL conservar el formato de validación de FastAPI: `{"detail": [ ... ]}`, una lista con un elemento por error que incluye `loc`, `msg` y `type`. Trazabilidad: Ej. 2 (códigos de respuesta); caso C-02 de la consigna ("409 con mensaje propio"); PA-11.

#### Scenario: Un 409 sólo lleva el mensaje propio
- **GIVEN** la base con los datos iniciales (el dueño 1 tiene el email `ana.gomez@example.com`)
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Otra Ana", "email": "ana.gomez@example.com"}`
- **THEN** la respuesta es **409** con el cuerpo exacto `{"detail": "Ya existe un dueño con ese email"}`
- **AND** el cuerpo no contiene `uq_duenio_email`, `duplicate key`, `INSERT` ni `asyncpg`

#### Scenario: Un 404 sólo lleva el mensaje propio
- **GIVEN** la base con los datos iniciales, sin dueño 999
- **WHEN** se hace `GET /duenios/999`
- **THEN** la respuesta es **404** con el cuerpo exacto `{"detail": "No existe el dueño"}`

#### Scenario: Un 422 conserva el formato de validación de FastAPI
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Lucía Fernández"}` (sin `email`)
- **THEN** la respuesta es **422**
- **AND** `detail` es una lista con un error cuyo `loc` es `["body", "email"]` y cuyo `type` es `missing`

### Requirement: Rechazos de la base traducidos sin consultas previas
Toda escritura cuya integridad garantiza la base (unicidad, clave foránea, `ON DELETE RESTRICT`) SHALL enviarse a la base sin una consulta previa del tipo "¿ya existe?": la sentencia de escritura es la que decide. Si la base la rechaza, la API MUST deshacer la transacción y responder con el código y el mensaje que esa operación declara para la restricción violada (o, si no la declara, con el 409 genérico del requisito siguiente). La misma restricción MAY significar cosas distintas en operaciones distintas (por ejemplo, la clave foránea de `ficha_duenio.duenio_id` al crear la ficha significa "no existe el dueño de la ruta" → 404), por eso cada operación declara sus propios rechazos. Después de un rechazo, la petición siguiente MUST poder escribir normalmente. Trazabilidad: consigna "Ninguna de estas reglas se verifica con una consulta previa del tipo ¿ya existe?… el service atrapa el IntegrityError, deshace la transacción y responde 409 con un mensaje propio"; regla dura 3; PA-01.

#### Scenario: El alta con email repetido no consulta antes de escribir
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Otra Ana", "email": "ana.gomez@example.com"}`
- **THEN** la respuesta es **409** con `{"detail": "Ya existe un dueño con ese email"}`
- **AND** la única sentencia SQL que la aplicación envió a la base (sin contar el control de la transacción: `BEGIN`, `COMMIT`, `ROLLBACK`) es un `INSERT INTO duenio`; ninguna sentencia `SELECT` la precedió

#### Scenario: La ficha de un dueño inexistente se rechaza por la clave foránea, sin consultar al dueño
- **GIVEN** la base con los datos iniciales, sin dueño 999
- **WHEN** se hace `POST /duenios/999/ficha` con `{"telefono": "11 5555-0999", "direccion": "Calle 999"}`
- **THEN** la respuesta es **404** con `{"detail": "No existe el dueño"}`
- **AND** la única sentencia SQL enviada (sin contar el control de la transacción) es un `INSERT INTO ficha_duenio`
- **AND** `ficha_duenio` sigue teniendo una sola fila

#### Scenario: El borrado de un dueño lo decide una única sentencia DELETE
- **GIVEN** la base con los datos iniciales
- **WHEN** se hace `DELETE /duenios/1` (el dueño 1 tiene mascotas)
- **THEN** la respuesta es **409**
- **AND** la única sentencia SQL enviada (sin contar el control de la transacción) es un `DELETE FROM duenio`; no hubo `SELECT`, ni `UPDATE` ni `DELETE` sobre `mascota` o `ficha_duenio`

#### Scenario: Después de un rechazo la siguiente escritura funciona
- **GIVEN** que `POST /duenios/` con el email `ana.gomez@example.com` acaba de responder **409**
- **WHEN** se hace `POST /duenios/` con `{"nombre": "Lucía Fernández", "email": "lucia.fernandez@example.com"}`
- **THEN** la respuesta es **201**
- **AND** `duenio` tiene tres filas: las dos iniciales y la nueva

### Requirement: Un rechazo no previsto responde 409 genérico y se registra
Si la base rechaza una escritura por una restricción de integridad que la operación no declaró (o que no informa nombre, como un `NOT NULL`), la API MUST deshacer la transacción y responder **409** con el cuerpo `{"detail": "La base rechazó la escritura"}` (mensaje propio, sin SQL ni nombres de restricciones). La API SHALL registrar en el log, con nivel de advertencia, el nombre de la restricción y el SQLSTATE, y MUST NOT registrar los valores enviados ni credenciales. Sólo los errores de integridad (`IntegrityError`) reciben este tratamiento: cualquier otra excepción se propaga normalmente. Trazabilidad: consigna "409 si la base rechaza la escritura"; regla dura 3. Decisión aprobada con cambios por Matheo, 2026-11-05.

#### Scenario: Una restricción no declarada responde 409 genérico y se registra
- **GIVEN** una escritura que la base rechaza por una restricción (por ejemplo, `uq_practica_nombre`) que la operación en curso no declaró entre sus rechazos
- **WHEN** se traduce el rechazo
- **THEN** el resultado es una respuesta **409** con `{"detail": "La base rechazó la escritura"}`
- **AND** el log de advertencia contiene el nombre de la restricción y el SQLSTATE, y ningún valor de los datos enviados
- **AND** la transacción quedó deshecha: una lectura posterior en la misma sesión funciona

#### Scenario: Una restricción declarada produce exactamente su código y su mensaje
- **GIVEN** una escritura que la base rechaza por `uq_duenio_email`, y una operación que declaró para esa restricción el código 409 y el mensaje "Ya existe un dueño con ese email"
- **WHEN** se traduce el rechazo
- **THEN** el resultado es una respuesta **409** con `{"detail": "Ya existe un dueño con ese email"}`
- **AND** no se registra ninguna advertencia

### Requirement: Id de ruta entero, con cota superior
Todo parámetro `{id}` de una ruta SHALL ser un entero no mayor que 2147483647 (el máximo de los ids que genera la base; el límite evita el desborde del tipo entero de 32 bits). Un valor que no es entero o que supera esa cota MUST responder **422** con el formato de validación de FastAPI, con `loc` igual a `["path", "id"]`, y MUST NOT ejecutar el handler: no se invoca la lógica del módulo ni se envía ninguna sentencia SQL. No hay cota inferior: `0` y los negativos son enteros válidos que no corresponden a ningún registro y responden **404**, igual que cualquier id en rango que no existe. Trazabilidad: caso C-01 de la consigna ("un parámetro de ruta que no es entero, por ejemplo `/duenios/abc` → 422, sin ejecutar el handler"); Ej. 2 ("422 si … los parámetros no cumplen el contrato"). Decisión aprobada con cambios por Matheo, 2026-11-05 (sólo cota superior).

#### Scenario: Caso C-01 — `/duenios/abc` responde 422 sin ejecutar el handler
- **GIVEN** la aplicación arrancada contra la base con los datos iniciales
- **WHEN** se hace `GET /duenios/abc`
- **THEN** la respuesta es **422** y `detail` tiene un error con `loc` `["path", "id"]` y `type` `int_parsing`
- **AND** la lógica del módulo de dueños no se ejecutó y no se envió ninguna sentencia SQL

#### Scenario: Todas las rutas con id rechazan un id no entero
- **WHEN** se hace `PATCH /duenios/abc` con `{"nombre": "X"}`, `DELETE /duenios/abc`, `POST /duenios/abc/ficha` con una ficha válida y `GET /duenios/abc/mascotas`
- **THEN** cada respuesta es **422** con `loc` `["path", "id"]`
- **AND** ningún dueño, ficha ni mascota cambió

#### Scenario: Un id sobre la cota responde 422; uno en rango inexistente, cero o negativo responde 404
- **WHEN** se hace `GET /duenios/2147483648`
- **THEN** la respuesta es **422** con `loc` `["path", "id"]` y no se envía ninguna sentencia SQL
- **AND** `GET /duenios/2147483647`, `GET /duenios/0` y `GET /duenios/-1` responden **404** con `{"detail": "No existe el dueño"}`
