## Purpose

Expone el estado del servicio con dos rutas de la consigna: `GET /health/live`, que confirma que el proceso atiende sin tocar la base, y `GET /health/ready`, que confirma con `SELECT 1` que la base contesta y responde 503 cuando no, sin colgar la petición. Cubre la parte "La salud del servicio" del Ejercicio 1 (10 %).

## ADDED Requirements

### Requirement: Liveness sin tocar la base
`GET /health/live` SHALL responder **200** con el cuerpo exacto `{"estado": "vivo"}` y MUST NOT abrir conexiones ni ejecutar sentencias contra la base, de modo que responde igual con la base disponible o caída. Trazabilidad: Ej. 1 ("`GET /health/live` no toca la base"); endpoint 1 de la tabla de referencia; prerequisito del caso C-09 de la consigna (el de salud responde de inmediato).

#### Scenario: Liveness con la base disponible
- **GIVEN** la aplicación arrancada contra `veterinaria_test`
- **WHEN** se hace `GET /health/live` sin cuerpo
- **THEN** la respuesta es **200** con el cuerpo `{"estado": "vivo"}`

#### Scenario: Liveness con la base caída
- **GIVEN** la aplicación arrancada con `DATABASE_URL` apuntando a `127.0.0.1:1`, donde nada escucha
- **WHEN** se hace `GET /health/live`
- **THEN** la respuesta es **200** con el cuerpo `{"estado": "vivo"}`
- **AND** responde en menos de 1 segundo

#### Scenario: Liveness no abre conexiones
- **GIVEN** la aplicación recién arrancada contra `veterinaria_test`, con el pool del motor sin conexiones
- **WHEN** se hace `GET /health/live`
- **THEN** el pool del motor sigue sin conexiones abiertas ni prestadas
- **AND** en cambio, después de un `GET /health/ready`, el pool conserva una conexión abierta (contraste que prueba que la medición detecta el uso de la base)

### Requirement: Readiness con SELECT 1
`GET /health/ready` SHALL ejecutar `SELECT 1` contra la base usando la sesión de la petición y, si la base contesta, responder **200** con el cuerpo exacto `{"estado": "listo"}`. Trazabilidad: Ej. 1 ("`GET /health/ready` ejecuta `SELECT 1`"); endpoint 2 de la tabla de referencia ("Estado de la base", códigos 200 y 503); resuelve PA-06.

#### Scenario: Readiness con la base disponible
- **GIVEN** la aplicación arrancada contra `veterinaria_test` con el contenedor `postgres:16` sano
- **WHEN** se hace `GET /health/ready` sin cuerpo
- **THEN** la respuesta es **200** con el cuerpo `{"estado": "listo"}`

#### Scenario: Readiness repetido devuelve la conexión al pool
- **GIVEN** la aplicación arrancada contra `veterinaria_test`
- **WHEN** se hace `GET /health/ready` dos veces seguidas
- **THEN** ambas respuestas son **200** `{"estado": "listo"}`
- **AND** el pool no tiene conexiones prestadas después de cada respuesta

### Requirement: Readiness responde 503 si la base no contesta, en tiempo acotado
Si la base no contesta a `SELECT 1` por cualquier motivo (nada escucha en el puerto, el servidor acepta la conexión pero no responde, la base no existe o rechaza las credenciales), `GET /health/ready` SHALL responder **503** con el cuerpo exacto `{"estado": "sin base"}`, sin incluir detalles del controlador, del SQL ni de la dirección de la base. La respuesta MUST llegar dentro del tiempo máximo de la verificación (2 segundos por defecto) más un margen de 1 segundo, aunque el servidor de base nunca conteste. Un 503 MUST NOT dejar la aplicación inutilizada: las rutas de salud siguen respondiendo después. Trazabilidad: Ej. 1 ("responde 503 si la base no contesta"); endpoint 2 de la tabla de referencia; resuelve PA-06.

#### Scenario: Nada escucha en el puerto de la base
- **GIVEN** la aplicación arrancada con `DATABASE_URL` apuntando a `127.0.0.1:1`
- **WHEN** se hace `GET /health/ready`
- **THEN** la respuesta es **503** con el cuerpo `{"estado": "sin base"}`
- **AND** llega antes del tiempo máximo de la verificación más 1 segundo

#### Scenario: El servidor acepta la conexión pero nunca contesta
- **GIVEN** un servidor TCP local que acepta conexiones y nunca envía bytes
- **AND** la aplicación arrancada con `DATABASE_URL` apuntando a ese servidor
- **WHEN** se hace `GET /health/ready`
- **THEN** la respuesta es **503** con el cuerpo `{"estado": "sin base"}`
- **AND** llega antes del tiempo máximo de la verificación más 1 segundo

#### Scenario: El servidor contesta pero la base no existe
- **GIVEN** la aplicación arrancada con `DATABASE_URL` apuntando al servidor de test pero a una base inexistente
- **WHEN** se hace `GET /health/ready`
- **THEN** la respuesta es **503** con el cuerpo `{"estado": "sin base"}`

#### Scenario: Después de un 503 la aplicación sigue atendiendo
- **GIVEN** la aplicación arrancada con `DATABASE_URL` apuntando a `127.0.0.1:1`
- **AND** un `GET /health/ready` que respondió **503**
- **WHEN** se hace `GET /health/live` y luego otro `GET /health/ready`
- **THEN** el primero responde **200** `{"estado": "vivo"}` y el segundo **503** `{"estado": "sin base"}`

### Requirement: Contrato de salud documentado
La documentación OpenAPI de la aplicación SHALL declarar `GET /health/live` con la respuesta 200 y `GET /health/ready` con las respuestas 200 y 503, ambas con el mismo esquema de cuerpo (`estado` de tipo texto). Trazabilidad: tabla de endpoints de referencia (códigos 200 / 200, 503); regla dura 5 (el router declara `status_code` y `response_model`).

#### Scenario: OpenAPI declara los códigos de readiness
- **WHEN** se hace `GET /openapi.json`
- **THEN** la operación `GET /health/ready` declara las respuestas `200` y `503`
- **AND** la operación `GET /health/live` declara la respuesta `200`
