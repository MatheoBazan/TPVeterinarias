# datos-iniciales Specification

## Purpose
Define cómo se deja la base en un estado conocido con `python reiniciar.py`: borra las tablas, las crea y carga los datos iniciales exactos de los que parten los ejemplos y los casos de prueba de la consigna, sobre una base vacía o ya usada. Incluye el archivo `.sql` del caso C-08 de la consigna, que demuestra que la base rechaza por sí misma un precio no positivo.

## Requirements

### Requirement: Recreación del esquema con reiniciar.py
`python reiniciar.py`, ejecutado desde la raíz del repositorio, SHALL leer la dirección de la base de `DATABASE_URL` (entorno o `.env`), borrar las tablas del modelo si existen, crearlas y cargar los datos iniciales, y terminar con código de salida 0 mostrando un resumen breve de lo cargado. MUST funcionar sobre una base sin tablas y MUST poder repetirse: cada ejecución deja exactamente el mismo estado, con los `id` reiniciados desde 1. Si `DATABASE_URL` falta o es inválida, MUST terminar con código distinto de 0 y un mensaje que nombre `DATABASE_URL`, sin mostrar la clave. Trazabilidad: Ej. 3 ("El reiniciar.py deja la base en un estado conocido"); condición de corrección "crea su esquema con `python reiniciar.py` sobre una base vacía"; regla dura 10.

#### Scenario: reiniciar.py sobre una base vacía
- **GIVEN** una base sin ninguna tabla del modelo
- **WHEN** se ejecuta `python reiniciar.py` con `DATABASE_URL` apuntando a esa base
- **THEN** el proceso termina con código 0
- **AND** la base tiene las seis tablas de la consigna con los datos iniciales

#### Scenario: reiniciar.py dos veces seguidas
- **GIVEN** una base en la que ya se ejecutó `python reiniciar.py` y luego se agregaron filas (por ejemplo un dueño 3 y un turno 2)
- **WHEN** se vuelve a ejecutar `python reiniciar.py`
- **THEN** el proceso termina con código 0
- **AND** la base queda con exactamente los datos iniciales, sin el dueño 3 ni el turno 2, y con los mismos `id` que la primera vez

#### Scenario: reiniciar.py sin DATABASE_URL
- **GIVEN** que `DATABASE_URL` no está definida ni en el entorno ni en `.env`
- **WHEN** se ejecuta `python reiniciar.py`
- **THEN** el proceso termina con código distinto de 0
- **AND** el mensaje menciona `DATABASE_URL` y no contiene ninguna clave
- **AND** no se modificó ninguna base

### Requirement: Datos iniciales exactos
Los datos iniciales SHALL ser exactamente los siguientes, cargados en una sola transacción y con los `id` generados por la base en este orden:
- Dueños: 1 "Ana Gómez" `ana.gomez@example.com`, **con** ficha (teléfono y dirección ficticios); 2 "Carlos Ruiz" `carlos.ruiz@example.com`, **sin** ficha.
- Mascotas: 1 "Toby" "perro" (dueño 1); 2 "Mishi" "gato" (dueño 1); 3 "Luna" "perro" (dueño 2).
- Prácticas: 1 "Consulta" 15000.00; 2 "Desparasitación" 8000.00; 3 "Vacuna antirrábica" 12000.00; 4 "Vacuna quíntuple" 14000.00.
- Turno 1 de "Mishi" con "Consulta" y "Desparasitación": el `precio_unitario` de cada práctica MUST ser el precio del catálogo al momento de la carga y el `total` MUST ser la suma de esos precios (23000.00), calculada y no escrita a mano.

Si la carga falla en cualquier punto, MUST NOT quedar ninguna fila de esa carga. Trazabilidad: Ej. 3 (mínimo de la consigna: dos dueños, uno con ficha; tres mascotas; cuatro prácticas; un turno con dos prácticas); PA-03 (aprobado); RN-06 (precio copiado, total calculado).

#### Scenario: Contenido de cada tabla tras la carga
- **GIVEN** un esquema recién creado y vacío
- **WHEN** se cargan los datos iniciales
- **THEN** `duenio` contiene exactamente (1, "Ana Gómez", `ana.gomez@example.com`) y (2, "Carlos Ruiz", `carlos.ruiz@example.com`)
- **AND** `ficha_duenio` contiene exactamente una fila, con `duenio_id = 1`
- **AND** `mascota` contiene exactamente (1, "Toby", "perro", 1), (2, "Mishi", "gato", 1) y (3, "Luna", "perro", 2)
- **AND** `practica` contiene exactamente (1, "Consulta", 15000.00), (2, "Desparasitación", 8000.00), (3, "Vacuna antirrábica", 12000.00) y (4, "Vacuna quíntuple", 14000.00)

#### Scenario: El turno inicial con precios copiados y total calculado
- **GIVEN** un esquema recién creado y vacío
- **WHEN** se cargan los datos iniciales
- **THEN** `turno` contiene exactamente el turno 1, con `mascota_id = 2` y `total = 23000.00`
- **AND** `turno_practica` contiene exactamente (1, 1, 15000.00) y (1, 2, 8000.00)
- **AND** el `total` del turno es igual a la suma de sus `precio_unitario`

#### Scenario: Una carga que falla a mitad de camino no deja nada
- **GIVEN** un esquema vacío salvo por un dueño ya existente con email `ana.gomez@example.com`
- **WHEN** se cargan los datos iniciales
- **THEN** la base rechaza la carga con SQLSTATE `23505` y restricción `uq_duenio_email`
- **AND** `practica`, `mascota`, `ficha_duenio`, `turno` y `turno_practica` quedan sin filas, aunque las prácticas se hubieran escrito antes del rechazo dentro de la misma transacción
- **AND** `duenio` conserva sólo el dueño que ya existía

#### Scenario: Cargar dos veces sin recrear el esquema se rechaza sin cambios
- **GIVEN** una base que ya tiene los datos iniciales
- **WHEN** se intenta cargar los datos iniciales otra vez sin recrear el esquema
- **THEN** la base rechaza la carga por unicidad (SQLSTATE `23505`)
- **AND** cada tabla conserva exactamente la misma cantidad de filas que antes del intento

### Requirement: Estado del que parte el ejemplo del Ejercicio 4
Después de cargar los datos iniciales, los próximos `id` que genere la base SHALL ser los siguientes a los cargados (turno 2, dueño 3, mascota 4, práctica 5), de modo que el ejemplo de `POST /turnos/` de la consigna (mascota 1, prácticas 1 y 3) produzca el turno 2 con total `27000.00`. Trazabilidad: Ej. 4 (respuesta esperada de `POST /turnos/`); SU-01; caso C-06 de la consigna (lo ejercita el change de turnos).

#### Scenario: El turno del ejemplo recibe id 2 y total 27000.00
- **GIVEN** la base con los datos iniciales
- **WHEN** se guarda un turno para la mascota 1 con las prácticas 1 y 3, copiando sus precios del catálogo y sumándolos
- **THEN** el turno recibe `id = 2` y `total = 27000.00`
- **AND** sus filas de `turno_practica` tienen `precio_unitario` 15000.00 y 12000.00

#### Scenario: Las secuencias continúan después de los datos iniciales
- **GIVEN** la base con los datos iniciales
- **WHEN** se insertan un dueño, una mascota y una práctica nuevos
- **THEN** reciben `id` 3, 4 y 5, respectivamente

### Requirement: Caso C-08 de la consigna en un archivo .sql
El repositorio SHALL incluir en `test/` un archivo `.sql` con la sentencia `UPDATE practica SET precio = 0` sobre una práctica de los datos iniciales, y en comentarios la precondición (`python reiniciar.py`), cómo ejecutarlo contra la base del contenedor y el resultado esperado: la base rechaza la sentencia por la restricción `ck_practica_precio_positivo`. Ejecutado después de `python reiniciar.py`, MUST NOT modificar ningún precio. Trazabilidad: caso C-08 de la consigna; RN-04; formato de entrega ("El C-08 va en un archivo `.sql`").

#### Scenario: Ejecutar el .sql del caso C-08 después de reiniciar
- **GIVEN** la base recién reiniciada, con la práctica 1 "Consulta" a 15000.00
- **WHEN** se ejecuta la sentencia `UPDATE` del archivo `.sql` del caso C-08
- **THEN** la base la rechaza con SQLSTATE `23514` y un mensaje que nombra la restricción `ck_practica_precio_positivo`
- **AND** la práctica 1 sigue con precio 15000.00

#### Scenario: El archivo documenta precondición, ejecución y resultado esperado
- **GIVEN** el repositorio
- **WHEN** se lee el archivo `.sql` del caso C-08 en `test/`
- **THEN** sus comentarios indican que se corre después de `python reiniciar.py`, el comando para ejecutarlo en el contenedor `db` y el error esperado con el nombre `ck_practica_precio_positivo`
- **AND** el archivo no contiene credenciales reales
