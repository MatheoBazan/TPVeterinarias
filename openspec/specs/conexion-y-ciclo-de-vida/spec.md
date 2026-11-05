# conexion-y-ciclo-de-vida Specification

## Purpose

Define cómo la API obtiene la dirección de la base desde el entorno sin versionar secretos, cómo el motor asincrónico y la fábrica de sesiones nacen y mueren con la aplicación (lifespan, `app.state`) y cómo cada petición recibe su propia sesión con `Depends(get_session)`. Cubre el Ejercicio 1 de la consigna (10 %, criterio "Estructura, lifespan, `Depends`, `.env` y `env.example`").

## Requirements

### Requirement: Dirección de la base leída del entorno
La aplicación SHALL leer la dirección de la base de la variable de entorno `DATABASE_URL`, que puede venir del entorno del proceso o de un archivo `.env` en la raíz del repositorio; si ambas fuentes la definen, MUST prevalecer la del entorno del proceso. La dirección MUST usar el controlador asincrónico (`postgresql+asyncpg://`). Si la variable falta, está vacía o usa otro controlador, el arranque MUST fallar con un mensaje que nombre `DATABASE_URL` y remita a `env.example`, sin mostrar la clave contenida en la dirección. Trazabilidad: Ej. 1 (".env y env.example"); sin RN.

#### Scenario: Arranque con DATABASE_URL definida
- **GIVEN** `DATABASE_URL=postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria_test` en el entorno
- **WHEN** la aplicación arranca
- **THEN** el arranque termina sin error
- **AND** el motor de la aplicación apunta a la base `veterinaria_test`

#### Scenario: El entorno del proceso prevalece sobre el .env
- **GIVEN** un `.env` cuya `DATABASE_URL` apunta a la base de desarrollo `veterinaria`
- **AND** el proceso define `DATABASE_URL` apuntando a `veterinaria_test`
- **WHEN** la aplicación arranca
- **THEN** el motor apunta a `veterinaria_test`

#### Scenario: Falta DATABASE_URL
- **GIVEN** que `DATABASE_URL` no está definida ni en el entorno ni en `.env`
- **WHEN** la aplicación arranca
- **THEN** el arranque falla y la aplicación no atiende peticiones
- **AND** el mensaje de error menciona `DATABASE_URL` y `env.example`

#### Scenario: DATABASE_URL vacía
- **GIVEN** `DATABASE_URL=` (cadena vacía o sólo espacios)
- **WHEN** la aplicación arranca
- **THEN** el arranque falla con el mismo mensaje que cuando falta la variable

#### Scenario: DATABASE_URL con un controlador que no es asincrónico de PostgreSQL
- **GIVEN** `DATABASE_URL` con el esquema `postgresql://` o `sqlite+aiosqlite://`
- **WHEN** la aplicación arranca
- **THEN** el arranque falla con un mensaje que exige el prefijo `postgresql+asyncpg://`
- **AND** el mensaje no contiene la clave de la dirección

### Requirement: Eco de SQL opcional por entorno
La aplicación SHALL permitir activar el registro en consola de cada sentencia SQL que envía el motor mediante la variable de entorno `SQL_ECHO`. Con `SQL_ECHO` en `1` o `true` (sin distinguir mayúsculas) el eco MUST quedar encendido; con cualquier otro valor o sin la variable MUST quedar apagado. Trazabilidad: evidencia de consola del caso C-07 de la consigna (se produce en el change de turnos); resuelve PA-08.

#### Scenario: Sin SQL_ECHO el eco está apagado
- **GIVEN** que `SQL_ECHO` no está definida
- **WHEN** la aplicación arranca
- **THEN** el motor no registra las sentencias SQL en la consola

#### Scenario: SQL_ECHO encendido
- **GIVEN** `SQL_ECHO=1` (o `SQL_ECHO=true`, o `SQL_ECHO=TRUE`)
- **WHEN** la aplicación arranca
- **THEN** el motor registra en la consola cada sentencia SQL que ejecuta

#### Scenario: SQL_ECHO con un valor que no es verdadero
- **GIVEN** `SQL_ECHO=0` (o `SQL_ECHO=false`, o `SQL_ECHO=` vacía)
- **WHEN** la aplicación arranca
- **THEN** el motor no registra las sentencias SQL en la consola

### Requirement: Motor y fábrica de sesiones en el lifespan
El motor asincrónico y la fábrica de sesiones SHALL crearse en el lifespan de la aplicación y guardarse en `app.state`; el motor MUST cerrarse (liberando todas sus conexiones) al apagar la aplicación. El arranque MUST NOT abrir conexiones a la base ni crear el esquema (el esquema lo crea `reiniciar.py`), de modo que la aplicación arranca aunque la base no esté disponible. Trazabilidad: Ej. 1 ("se crean en el lifespan de la aplicación, se guardan en `app.state`, y el motor se cierra al apagar").

#### Scenario: El arranque guarda motor y fábrica en app.state
- **GIVEN** una `DATABASE_URL` válida
- **WHEN** la aplicación completa su arranque
- **THEN** `app.state` contiene el motor asincrónico y la fábrica de sesiones creados en ese arranque

#### Scenario: El arranque no necesita la base
- **GIVEN** una `DATABASE_URL` que apunta a `127.0.0.1:1`, donde nada escucha
- **WHEN** la aplicación arranca
- **THEN** el arranque termina sin error
- **AND** `GET /health/live` responde 200 `{"estado": "vivo"}`

#### Scenario: El apagado cierra el motor y sus conexiones
- **GIVEN** la aplicación arrancada contra `veterinaria_test`
- **AND** una conexión real a la base que se usó (`SELECT 1`) y quedó abierta en el pool del motor
- **WHEN** la aplicación se apaga
- **THEN** el motor queda cerrado (dispose)
- **AND** el pool que tenía esa conexión no conserva ninguna conexión abierta

### Requirement: Una sesión por petición
Cada handler que la necesite SHALL recibir la sesión con `Depends(get_session)`. Cada petición MUST recibir una sesión propia, distinta de la de cualquier otra petición; dentro de una misma petición, todas las dependencias que piden la sesión MUST recibir la misma. La sesión MUST crearse con `expire_on_commit=False` y MUST cerrarse al terminar la petición, devolviendo su conexión al pool. Trazabilidad: Ej. 1 ("una por petición, creada con `expire_on_commit=False`").

#### Scenario: Dos peticiones reciben sesiones distintas
- **GIVEN** la aplicación arrancada contra `veterinaria_test`
- **WHEN** se hacen dos peticiones seguidas a un handler que recibe la sesión con `Depends(get_session)`
- **THEN** cada petición recibe un objeto de sesión distinto

#### Scenario: Dentro de una petición la sesión es la misma
- **GIVEN** un handler que recibe la sesión directamente y además a través de otra dependencia que también pide `Depends(get_session)`
- **WHEN** se hace una petición a ese handler
- **THEN** ambas referencias son el mismo objeto de sesión

#### Scenario: La sesión no expira los objetos al confirmar
- **WHEN** un handler recibe la sesión con `Depends(get_session)`
- **THEN** esa sesión tiene `expire_on_commit=False`
- **AND** admite consultas con `exec` para los services de los módulos

#### Scenario: La conexión vuelve al pool al terminar la petición
- **GIVEN** un handler que ejecuta `SELECT 1` con la sesión recibida
- **WHEN** la petición termina con 200
- **THEN** el pool del motor no tiene conexiones prestadas (todas fueron devueltas)

### Requirement: Configuración versionada sin secretos
El repositorio SHALL incluir un `env.example` con todas las variables que usa el proyecto (`DATABASE_URL`, `TEST_DATABASE_URL`, `SQL_ECHO`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`) con la forma del valor y placeholders en lugar de credenciales; la forma de `DATABASE_URL` MUST ser `postgresql+asyncpg://<usuario>:<clave>@localhost:<puerto>/<base>`. El archivo `.env` MUST quedar excluido del control de versiones, y ningún archivo versionado (en particular `env.example` y `docker-compose.yml`) MUST contener la clave real. Trazabilidad: Ej. 1; condición de corrección "credenciales reales en el repositorio = no se corrige".

#### Scenario: env.example declara todas las variables con placeholders
- **WHEN** se lee `env.example`
- **THEN** declara `DATABASE_URL`, `TEST_DATABASE_URL`, `SQL_ECHO`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` y `POSTGRES_PORT`
- **AND** `DATABASE_URL` y `TEST_DATABASE_URL` tienen la forma `postgresql+asyncpg://<usuario>:<clave>@localhost:<puerto>/<base>` con `<usuario>` y `<clave>` literales

#### Scenario: La clave real no aparece en archivos versionados
- **GIVEN** un `.env` local con `POSTGRES_PASSWORD` real
- **WHEN** se inspeccionan `env.example` y `docker-compose.yml`
- **THEN** ninguno contiene ese valor
- **AND** `docker-compose.yml` toma usuario, clave y base de variables de entorno, sin valores por defecto para usuario ni clave

#### Scenario: .env no se versiona
- **WHEN** se ejecuta `git check-ignore .env` en la raíz del repositorio
- **THEN** git informa que `.env` está ignorado

### Requirement: Base de test separada y protegida
La suite pytest SHALL ejecutarse contra una base PostgreSQL real separada, indicada por `TEST_DATABASE_URL`, cuyo nombre MUST terminar en `_test`; nunca contra SQLite ni contra la base de desarrollo. El entorno Docker del repositorio MUST crear `veterinaria_test` automáticamente al inicializar un volumen de datos vacío. Si `TEST_DATABASE_URL` falta o apunta a una base cuyo nombre no termina en `_test`, los tests que usan la base MUST fallar con un mensaje claro en lugar de correr. Trazabilidad: regla dura 9 (sin mocks de la base); decisión DD-04.

#### Scenario: Volumen vacío crea la base de test
- **GIVEN** que el volumen de datos de PostgreSQL no existe
- **WHEN** se ejecuta `docker compose up -d` y el contenedor queda sano
- **THEN** el servidor tiene la base de desarrollo y la base `veterinaria_test`

#### Scenario: Falta TEST_DATABASE_URL
- **GIVEN** que `TEST_DATABASE_URL` no está definida
- **WHEN** se ejecuta un test que necesita la base
- **THEN** el test falla con un mensaje que nombra `TEST_DATABASE_URL` y `env.example`

#### Scenario: TEST_DATABASE_URL apunta a una base que no es de test
- **GIVEN** `TEST_DATABASE_URL` apuntando a la base `veterinaria`
- **WHEN** se ejecuta un test que necesita la base
- **THEN** el test falla con un mensaje que exige que el nombre de la base termine en `_test`
- **AND** no se ejecuta ninguna sentencia contra `veterinaria`
