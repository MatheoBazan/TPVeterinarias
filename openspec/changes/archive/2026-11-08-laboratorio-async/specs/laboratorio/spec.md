# Spec Delta — laboratorio

## Purpose

Permite consultar el stock de vacunas que informa la biblioteca del laboratorio provista por la cátedra, que es sincrónica y lenta, sin que esa espera impida al servidor atender otras peticiones.

## ADDED Requirements

### Requirement: Consulta de stock
`GET /laboratorio/stock/{vacuna}` SHALL responder **200** con `{"vacuna": <vacuna>, "stock": <entero>}`, donde `vacuna` es el texto de la ruta y `stock` es el valor que devuelve la función `consultar_stock` de la biblioteca del laboratorio para esa vacuna. La ruta no accede a la base de datos. Trazabilidad: Ej. 6; tabla de endpoints de la consigna.

#### Scenario: Stock de una vacuna
- **GIVEN** el servidor levantado
- **WHEN** se hace `GET /laboratorio/stock/rabia`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"vacuna": "rabia", "stock": 15}`

#### Scenario: El stock depende de la vacuna consultada
- **GIVEN** el servidor levantado
- **WHEN** se hace `GET /laboratorio/stock/parvovirus`
- **THEN** la respuesta es **200** con el cuerpo exacto `{"vacuna": "parvovirus", "stock": 20}`

### Requirement: Biblioteca del laboratorio sin modificar
El módulo `app/modules/laboratorio/cliente.py` MUST tener exactamente el contenido que entrega la cátedra: la función sincrónica `consultar_stock(vacuna: str) -> int` que espera un segundo con `time.sleep(1)` y devuelve `10 + len(vacuna)`. La API MUST usar esa función tal cual, sin reescribirla ni reemplazarla por una variante asincrónica. Trazabilidad: Ej. 6 ("llamando a esa función sin modificarla"); regla dura 2.

#### Scenario: El archivo coincide con el de la cátedra
- **GIVEN** el repositorio
- **WHEN** se compara `app/modules/laboratorio/cliente.py` con el código del enunciado
- **THEN** el código coincide línea por línea (import de `time`, firma, docstring, `time.sleep(1)` y `return 10 + len(vacuna)`)

### Requirement: El servidor sigue atendiendo durante las consultas
Mientras haya consultas al laboratorio en curso, el servidor MUST seguir atendiendo otras peticiones: la espera de `consultar_stock` MUST ocurrir fuera del bucle de eventos. Varias consultas simultáneas MUST resolverse en paralelo y no una detrás de otra. Trazabilidad: Ej. 6; caso C-09 de la consigna; regla dura 2.

#### Scenario: Caso C-09 — tres consultas simultáneas y un health
- **GIVEN** tres peticiones `GET /laboratorio/stock/{vacuna}` en curso al mismo tiempo
- **WHEN** se hace `GET /health/live`
- **THEN** la respuesta es **200** `{"estado": "vivo"}` en menos de 0,5 segundos, antes de que termine cualquiera de las consultas al laboratorio

#### Scenario: Las consultas simultáneas no se encolan
- **GIVEN** el servidor levantado
- **WHEN** se lanzan tres `GET /laboratorio/stock/{vacuna}` al mismo tiempo
- **THEN** las tres responden **200** con su stock
- **AND** las tres terminan en menos de 2 segundos en total (en serie tardarían 3)
