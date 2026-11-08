# Tasks — turnos-composicion (C-06)

> **Governance MEDIO**: D-1 (precio copiado por la base en un `INSERT … SELECT`; práctica inexistente rechazada por el `NOT NULL`) se confirma con el equipo antes del apply.
>
> **TDD estricto** contra PostgreSQL real (`veterinaria_test`), nunca SQLite ni mocks de la sesión: cada grupo sigue RED → GREEN → TRIANGULATE → REFACTOR y corre `pytest` en cada paso. Si un test pasa de entrada porque otro grupo (o FastAPI/Pydantic) ya cubre la propiedad, romperla temporalmente (mutación), ver el rojo y anotarlo. Los módulos de test nuevos declaran `pytestmark = pytest.mark.integracion` y usan `base_con_seed` + `client` (seed: mascotas 1 Toby perro, 2 Mishi gato, 3 Luna perro; prácticas 1 Consulta 15000.00, 2 Desparasitación 8000.00, 3 Vacuna antirrábica 12000.00, 4 Vacuna quíntuple 14000.00; turno 1 de Mishi con prácticas 1 y 2, total 23000.00).
>
> **Entregable en `test/`**: `test/turnos.http` (grupo 6).

## 0. Línea base

- [x] 0.1 `docker compose up -d --wait` y `pytest` completo en verde; anotar "N tests passing" (se modifica `app/main.py`)

## 1. Detalle de turno (`GET /turnos/{id}`, D-3, D-4)

- [x] 1.1 RED: `tests/test_turnos.py::test_detalle_del_turno_del_seed` (`GET /turnos/1` → 200 con el cuerpo exacto del escenario "Detalle del turno del seed") → falla con 404 (la ruta no existe)
- [x] 1.2 GREEN: `turnos/schemas.py` con `MascotaDeTurnoRead`, `PracticaDeTurnoRead`, `TurnoRead` (`field_serializer("fecha")` a UTC); `turnos/service.py` con `obtener_turno(session, turno_id)` (consulta de D-4 con `populate_existing`) y `a_lectura(turno)` (prácticas ordenadas por `practica_id`); `turnos/router.py` con `GET /{id}` (`IdRuta`, `response_model=TurnoRead`, 404 documentado con `MensajeError`); `include_router` en `crear_app()` → verde
- [x] 1.3 TRIANGULATE: `GET /turnos/999` → 404 `{"detail": "No existe el turno"}`; `GET /turnos/abc` → 422 sin sentencias SQL
- [x] 1.4 RED/GREEN: `tests/test_turnos_consultas.py::test_detalle_usa_dos_consultas_con_una_y_tres_practicas` (insertar con `sesion_seed` un turno con 1 práctica y otro con 3; tras `sentencias_app.clear()`, cada `GET` envía exactamente 2 `SELECT`: el primero con `JOIN mascota`, el segundo sobre `turno_practica` con `JOIN practica`) → si pasa de entrada, mutación quitando el `joinedload(TurnoPractica.practica)` → rojo (N+1 o `MissingGreenlet`), anotarla
- [x] 1.5 REFACTOR: tipos y nombres; tests en verde

## 2. Contrato de alta: 422 (RN-05, PA-10, D-3)

- [x] 2.1 RED: `tests/test_turnos_alta.py::test_lista_de_practicas_vacia_responde_422` (`loc == ["body", "practicas"]`, y `sentencias_app == []`) → falla con 405 (no existe `POST`)
- [x] 2.2 GREEN: `PracticaDeTurnoCreate` y `TurnoCreate` (D-3, `ENTRADA` importada de `duenios.schemas` como en C-04); ruta `POST /` con `status_code=201`, `response_model=TurnoRead` y 409 documentado; service `crear_turno` mínimo → verde
- [x] 2.3 TRIANGULATE (parametrizado, todos 422, `turno` sigue con 1 fila): fecha sin zona (`loc == ["body", "fecha"]`, PA-10); `motivo` `"   "`; `total` en el cuerpo; `precio_unitario` dentro de una práctica; `id` en el cuerpo; `practicas` ausente; `mascota_id` y `practica_id` `2147483648`
- [x] 2.4 REFACTOR: tests en verde

## 3. Reserva válida (RN-06, caso C-06 de la consigna, D-1, D-5)

- [x] 3.1 RED: `test_caso_c06_ejemplo_de_la_consigna` (cuerpo del PDF → 201 con el cuerpo exacto del escenario "Caso C-06"; `turno_practica` tiene 2 filas con `turno_id` 2 y precios 15000.00 y 12000.00) → falla
- [x] 3.2 GREEN: `crear_turno` según D-1 (`flush` del `Turno` con `total=0`, `INSERT … SELECT` de `unnest(ids) WITH ORDINALITY LEFT JOIN practica` con `RETURNING precio_unitario`, `total = sum(...)`, `commit`) y D-5 (devuelve `obtener_turno`) → verde
- [x] 3.3 TRIANGULATE: prácticas `[4, 1, 2]` → 201 ordenadas 1, 2, 4 y total `"37000.00"`; `GET /turnos/{id}` del turno creado devuelve el mismo cuerpo que el 201
- [x] 3.4 RED/GREEN: `test_precio_congelado_ante_cambio_del_catalogo` (crear turno con la práctica 1; `UPDATE practica SET precio = 20000 WHERE id = 1` con `sesion_seed`; `GET` sigue mostrando `"15000.00"` y el mismo total) → si pasa de entrada, mutación leyendo `tp.practica.precio` en `a_lectura` → rojo, anotarla
- [x] 3.5 REFACTOR: comentario en el service que explica D-1 en dos líneas; tests en verde

## 4. Rechazos del alta: 409 todo o nada (RN-07, PA-13, caso C-04 de la consigna, D-1, D-2)

- [x] 4.1 RED: `test_caso_c04_practica_inexistente_no_guarda_nada` (prácticas `[1, 999]` → 409 `{"detail": "No existe la práctica indicada"}`; `turno` 1 fila, `turno_practica` 2 filas) → falla con el 409 genérico `La base rechazó la escritura` (o 500)
- [x] 4.2 GREEN: `RECHAZOS_ALTA` y el helper de traducción de D-2 (`NotNullViolationError` sobre `precio_unitario` → práctica inexistente; si no, `traducir_rechazo`); `try/except IntegrityError` con `rollback` que envuelve `flush`, el `INSERT … SELECT` y el `commit` → verde
- [x] 4.3 TRIANGULATE: práctica repetida `[1, 1]` → 409 `Una práctica no puede repetirse en el mismo turno`; `mascota_id` 999 → 409 `No existe la mascota indicada`; `practica_id` `0` y `-1` → 409 práctica inexistente; en todos, `turno` 1 fila y el cuerpo no contiene nombres de restricciones, `NULL`, `INSERT` ni `asyncpg`
- [x] 4.4 RED/GREEN: `tests/test_turnos_consultas.py::test_alta_rechazada_no_consulta_antes_de_escribir` (práctica 999; sin contar `BEGIN`/`COMMIT`/`ROLLBACK`, la primera sentencia es `INSERT INTO turno` y ningún `SELECT` la precede) → si pasa de entrada, mutación con un `select(Practica)` previo → rojo, anotarla
- [x] 4.5 TRIANGULATE: después de un 409, `POST` válido → 201 (la sesión quedó usable)
- [x] 4.6 REFACTOR: tests en verde

## 5. Borrado (`DELETE /turnos/{id}`, RN-09, caso C-05 de la consigna, D-6)

- [x] 5.1 RED: `test_caso_c05_borrar_turno_borra_sus_practicas` (`DELETE /turnos/1` → 204 sin cuerpo; `GET /turnos/1` → 404; `turno_practica` sin filas de `turno_id` 1; `GET /practicas/` sigue con 4) → falla con 405
- [x] 5.2 GREEN: `borrar_turno` (D-6) y ruta `DELETE /{id}` con `status_code=204` y 404 documentado → verde
- [x] 5.3 TRIANGULATE: `DELETE /turnos/999` → 404 `{"detail": "No existe el turno"}`; la única sentencia de un `DELETE` exitoso (sin control de transacción) es `DELETE FROM turno` (la cascada la hace la base, no el ORM)
- [x] 5.4 REFACTOR: tests en verde

## 6. Entregable `test/turnos.http` (D-7)

- [x] 6.1 RED: `tests/test_turnos_http.py` (como `test_practicas_http.py`): el archivo existe, menciona `Caso C-04`, `Caso C-05`, `Caso C-06`, `Caso C-07` y `SQL_ECHO`, cada bloque tiene `# Esperado:`, y corrido en orden con `base_con_seed` + `client` cada bloque responde su código esperado → falla (no existe el archivo)
- [x] 6.2 GREEN: escribir `test/turnos.http` en el orden de D-7, con la cabecera de ejecución (una vez, tras `python reiniciar.py`) y la nota de la evidencia del caso C-07 con `SQL_ECHO=1` → verde
- [x] 6.3 Verificación manual: `python reiniciar.py`, `uvicorn app.main:app` con `SQL_ECHO=1`, correr el `.http` en orden y ver dos `SELECT` en consola para `GET /turnos/3` y `GET /turnos/4`

## 7. Cierre

- [x] 7.1 `pytest` completo en verde (línea base + los nuevos) y `python reiniciar.py` sobre base vacía sin errores
- [x] 7.2 Resolver PA-10 y PA-13 en `knowledge-base/10_preguntas_abiertas.md` apuntando a este design (D-3)

## Workflow follow-up

- `/opsx:archive turnos-composicion` con `pytest` en verde.
- Marcar C-06 como `[x]` en `CHANGES.md`.
