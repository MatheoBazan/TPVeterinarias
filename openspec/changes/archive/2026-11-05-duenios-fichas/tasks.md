> **Governance MEDIO**: este change fija el patrón que copian C-04..C-06. No empezar el `apply` sin la revisión de Matheo de las decisiones marcadas ⚠ del `design.md` (tarea 0.1).
>
> **TDD estricto** (contra PostgreSQL real `veterinaria_test`, nunca SQLite ni mocks de la sesión): cada grupo sigue RED → GREEN → TRIANGULATE → REFACTOR y se ejecuta `pytest` en cada paso. Si un test pasa de entrada porque el código de un grupo anterior (o FastAPI) ya cubre la propiedad, comprobar que falla rompiendo temporalmente esa propiedad (mutación) y registrarlo en la evidencia TDD. Los módulos de test nuevos declaran `pytestmark = pytest.mark.integracion` y usan `base_con_seed` + `client` (seed de C-02: dueño 1 con ficha 1 y mascotas 1 y 2; dueño 2 sin ficha con la mascota 3).
>
> **Entregable en `test/`**: `test/duenios.http` (grupo 10) con los casos C-01, C-02 (email), C-03 y C-05 (primera parte) de la consigna.

## 0. Gobernanza y entorno

- [x] 0.1 Confirmar con Matheo la aprobación del `design.md`, en especial las decisiones ⚠: D-1 (traducción por nombre de restricción con mapa por operación), D-2 (rechazo no previsto → 409 genérico con log; **APROBADA con cambios**), D-7 (`DELETE` con sentencia única + `rowcount`), D-11 (`MascotaRead` en `app/modules/mascotas/schemas.py`; avisar a Lautaro/Uriel, quien tome C-04), D-12 (DTO: `EmailStr` con dominio normalizado, `str_strip_whitespace`, `null` en PATCH → 422), D-13 (`IdRuta` sólo con `le=2147483647`, sin `ge=1`: `/duenios/0` y `/duenios/-1` → 404; **APROBADA con cambios**); registrar la aprobación (fecha) en el encabezado de cada decisión — aprobado por Matheo el 2026-11-05 (D-2 y D-13 con cambios, ya reflejados en design, specs y tasks)
- [x] 0.2 Verificar que C-02 `modelos-esquema-seed` está aplicado (`openspec list --json`: tareas completas o archivado): `Duenio`, `FichaDuenio` y `Mascota` con sus restricciones (`uq_duenio_email`, `uq_ficha_duenio_duenio_id`, FK `ficha_duenio_duenio_id_fkey` CASCADE y `mascota_duenio_id_fkey` RESTRICT) y relaciones (`Duenio.ficha`, `Duenio.mascotas` con `passive_deletes="all"`); `app/main.py` importa `app.core.modelos`; existen las fixtures `base_con_seed`, `sesion` y `sentencias_sql` y el helper `error_postgres`
- [x] 0.3 `docker compose up -d --wait`; la base `veterinaria_test` existe; venv con `fastapi==0.162.0`, `sqlmodel==0.0.48`, `sqlalchemy==2.0.57`, `asyncpg==0.32.0` y `email-validator` instalado (`pip show`), `pip check` sin errores
- [x] 0.4 Safety net: `pytest` completo en verde; anotar la línea base "N tests passing" (se modificarán `app/main.py` y `tests/conftest.py`)

## 1. Traducción de rechazos (`app/core/errores.py`, D-1 y D-2)

- [x] 1.1 RED: `tests/test_errores.py::test_restriccion_violada_de_email_repetido_es_uq_duenio_email` (con `sesion` sobre `base_con_seed`: agregar un `Duenio` con `ana.gomez@example.com`, `commit` → `IntegrityError`; `restriccion_violada(exc) == "uq_duenio_email"`) → falla por `ImportError`
- [x] 1.2 GREEN: crear `app/core/errores.py` con `restriccion_violada(exc)` (lee `exc.orig.__cause__.constraint_name`) → verde
- [x] 1.3 TRIANGULATE: parametrizar por escritura rechazada → restricción esperada: ficha con `duenio_id=999` → `ficha_duenio_duenio_id_fkey`; segunda ficha del dueño 1 → `uq_ficha_duenio_duenio_id`; `delete(Duenio).where(Duenio.id == 1)` → `mascota_duenio_id_fkey`; y `INSERT` con `text()` de un dueño sin `email` (NOT NULL) → `None`
- [x] 1.4 RED: `test_traducir_rechazo_previsto_devuelve_su_codigo_y_mensaje` parametrizado (`uq_duenio_email` → 409 "Ya existe un dueño con ese email"; `ficha_duenio_duenio_id_fkey` → 404 "No existe el dueño") → falla (no existen `Rechazo` ni `traducir_rechazo`)
- [x] 1.5 GREEN: `Rechazo` (dataclass congelada) y `traducir_rechazo(exc, rechazos)` → verde
- [x] 1.6 TRIANGULATE: `test_traducir_rechazo_no_previsto_responde_409_generico_y_lo_registra` (mapa sin la restricción, mapa vacío y el error NOT NULL sin `constraint_name` → `HTTPException` 409 con `La base rechazó la escritura`; con `caplog` el `warning` trae restricción y SQLSTATE y no los valores); `test_despues_del_rollback_la_sesion_vuelve_a_leer` (tras `rollback`, `SELECT count(*) FROM duenio` = 2 en la misma sesión)
- [x] 1.7 REFACTOR: agregar `MensajeError(SQLModel)` con `detail: str`; docstrings de D-1; tests en verde

## 2. Detalle del dueño, id de ruta y caso C-01 (`GET /duenios/{id}`)

- [x] 2.1 RED: `tests/test_duenios.py::test_obtener_duenio_con_ficha_responde_200_con_la_ficha` (`GET /duenios/1` → cuerpo exacto del spec) → falla con 404 (la ruta no existe)
- [x] 2.2 GREEN: `app/modules/duenios/schemas.py` con `DuenioRead`, `FichaRead` y `DuenioConFichaRead(DuenioRead)` (D-12); `app/modules/duenios/service.py` con `obtener_duenio(session, duenio_id)` (`select(Duenio)...options(joinedload(Duenio.ficha))`, `one_or_none`, devuelve `DuenioConFichaRead.model_validate(...)`, D-6/D-15); `app/modules/duenios/router.py` con `APIRouter(prefix="/duenios", tags=["duenios"])` y `GET /{id}` de una línea que llama `service.obtener_duenio` por el módulo (D-14); `include_router` en `crear_app()` → verde
- [x] 2.3 TRIANGULATE: `test_obtener_duenio_sin_ficha_responde_ficha_null` (dueño 2, cuerpo exacto) y `test_obtener_duenio_inexistente_responde_404` (`{"detail": "No existe el dueño"}` exacto) → agregar la constante `DUENIO_INEXISTENTE` y el `HTTPException` 404
- [x] 2.4 RED: fixture `sentencias_app(app)` en `tests/conftest.py` (listener `before_cursor_execute` sobre `app.state.engine.sync_engine`, retirado en el teardown, D-17); caso C-01: `test_ruta_con_id_no_entero_responde_422_sin_ejecutar_el_handler` (espía `async` sobre `service.obtener_duenio` con `monkeypatch.setattr`; `GET /duenios/abc` → 422, `loc == ["path", "id"]`, `type == "int_parsing"`, espía sin llamadas, `sentencias_app` vacía) — pasa de entrada por FastAPI: mutación cambiando temporalmente el parámetro a `id: str` (el espía se llama → rojo) y registrarla; `test_id_sobre_la_cota_responde_422` parametrizado (`2147483648`, `99999999999`) → rojo: termina en error del servidor (confirma la premisa de D-13); `test_id_cero_o_negativo_responde_404` parametrizado (`0`, `-1`; sin `ge=1`, el handler corre y no hay fila)
- [x] 2.5 GREEN: `app/core/parametros.py` con `ENTERO_MAXIMO` e `IdRuta` (D-13); el router usa `id: IdRuta` → verde
- [x] 2.6 TRIANGULATE: `GET /duenios/2147483647` → 404 (el máximo en rango); `test_espia_registra_la_llamada_con_id_valido` (`GET /duenios/1` → 200 y el espía registró una llamada con `duenio_id == 1`: prueba que el espía intercepta)
- [x] 2.7 REFACTOR: extraer `_duenio_con_ficha(session, duenio_id)` (la reutiliza el PATCH); `responses={404: {"model": MensajeError, ...}}` en la ruta; tests en verde

## 3. Detalle sin N+1 (Ej. 5)

- [x] 3.1 RED/GREEN: `tests/test_duenios_consultas.py::test_detalle_de_duenio_usa_una_sola_consulta` parametrizado por dueño 1 (con ficha) y dueño 2 (sin ficha): tras `sentencias_app.clear()`, la petición envía exactamente 1 sentencia, un `SELECT` que contiene `JOIN ficha_duenio` → pasa de entrada por 2.2: mutación quitando temporalmente el `joinedload` (el service falla con `MissingGreenlet` al armar el DTO → rojo) y registrarla
- [x] 3.2 REFACTOR: helper de test `sentencias_de_datos(lista)` si hace falta filtrar; tests en verde

## 4. Alta de dueño (`POST /duenios/`, RN-01, caso C-02)

- [x] 4.1 RED: `test_crear_duenio_valido_responde_201` (cuerpo `{"nombre": "Lucía Fernández", "email": "lucia.fernandez@example.com"}` → 201 `{"id": 3, ...}` exacto; `GET /duenios/3` → `"ficha": null`) → falla con 405
- [x] 4.2 GREEN: `DuenioCreate` (`extra="forbid"`, `str_strip_whitespace=True`, `nombre` `min_length=1`, `email: EmailStr`); `service.crear_duenio` (`Duenio.model_validate(datos)`, `add`, `commit`, `DuenioRead`); ruta `POST /` con `status_code=201` y `response_model=DuenioRead` → verde
- [x] 4.3 RED: caso C-02 `test_crear_duenio_con_email_repetido_responde_409` (`ana.gomez@example.com` → 409 `{"detail": "Ya existe un dueño con ese email"}` exacto; `duenio` sigue con 2 filas) → falla (el `IntegrityError` se propaga)
- [x] 4.4 GREEN: `try/except IntegrityError` → `await session.rollback()` → `raise traducir_rechazo(exc, RECHAZOS_EMAIL) from exc` (D-1, D-16) → verde
- [x] 4.5 TRIANGULATE: dominio en otra capitalización (`ana.gomez@EXAMPLE.com`) → 409; espacios y dominio normalizados (`"  Lucía Fernández  "`, `Lucia.Fernandez@EXAMPLE.COM`) → 201 con los valores normalizados; cuerpos inválidos parametrizados (sin email, sin nombre, email inválido, nombre `"   "`, campo `id`) → 422 con el `loc` del campo culpable y 2 filas; `test_despues_de_un_409_la_siguiente_alta_funciona` (409 y luego 201); el cuerpo del 409 no contiene `uq_duenio_email`, `duplicate key`, `INSERT` ni `asyncpg`
- [x] 4.6 RED/GREEN: `test_alta_con_email_repetido_no_consulta_antes_de_escribir` (con `sentencias_app`: una sola sentencia, `INSERT INTO duenio`, ningún `SELECT`) → si pasa de entrada, mutación agregando temporalmente un `SELECT` por email antes del `add` (rojo) y registrarla
- [x] 4.7 REFACTOR: constante `RECHAZOS_EMAIL`; `responses={409: ...}` en la ruta; tests en verde

## 5. Edición parcial (`PATCH /duenios/{id}`)

- [x] 5.1 RED: `test_patch_solo_nombre_conserva_el_email_y_la_ficha` (`PATCH /duenios/1` `{"nombre": "Ana María Gómez"}` → 200 cuerpo exacto con la ficha 1) → falla con 405
- [x] 5.2 GREEN: `DuenioUpdate` (`nombre` y `email` opcionales, `extra="forbid"`, `str_strip_whitespace=True`, `min_length=1`); `service.actualizar_duenio` con `_duenio_con_ficha` → 404, `sqlmodel_update(datos.model_dump(exclude_unset=True))`, `commit`, `DuenioConFichaRead` (D-8); ruta `PATCH /{id}` → verde
- [x] 5.3 TRIANGULATE: sólo email (dueño 2 → `carlos.ruiz@example.org`, nombre intacto); `{}` → 200 sin cambios; propio email → 200; `PATCH /duenios/999` → 404 y 2 filas
- [x] 5.4 RED: `test_patch_con_email_de_otro_duenio_responde_409_y_no_cambia_nada` (`PATCH /duenios/2` `{"nombre": "Carlos R.", "email": "ana.gomez@example.com"}` → 409; `GET /duenios/2` conserva nombre y email) → falla (error del servidor)
- [x] 5.5 GREEN: `try/except IntegrityError` con `RECHAZOS_EMAIL` → verde
- [x] 5.6 RED: `test_patch_con_null_responde_422` parametrizado (`{"nombre": null}`, `{"email": null}`) → falla (la base rechaza el NOT NULL y la Decisión 2 lo traduce a un 409 genérico en vez de 422)
- [x] 5.7 GREEN: `field_validator("nombre", "email")` que rechaza `None` (D-12) → verde
- [x] 5.8 TRIANGULATE: `{"email": "no-es-un-email"}`, `{"nombre": ""}`, `{"id": 5}` → 422 y el dueño 2 sin cambios
- [x] 5.9 RED/GREEN: `test_patch_obtiene_la_ficha_en_la_misma_consulta` (con `sentencias_app`: exactamente un `SELECT` con `JOIN ficha_duenio` y un `UPDATE duenio`; ninguna sentencia filtra por `email`)
- [x] 5.10 REFACTOR: `responses={404: ..., 409: ...}`; tests en verde

## 6. Ficha del dueño (`POST /duenios/{id}/ficha`, RN-03, caso C-03, PA-01)

- [x] 6.1 RED: `test_crear_ficha_para_duenio_sin_ficha_responde_201` (`POST /duenios/2/ficha` → 201 `{"id": 2, "duenio_id": 2, ...}` exacto; `GET /duenios/2` la muestra) → falla con 404/405
- [x] 6.2 GREEN: `FichaCreate` (`telefono`, `direccion` con `min_length=1`, `extra="forbid"`, `str_strip_whitespace=True`); `service.crear_ficha` (`FichaDuenio.model_validate(datos, update={"duenio_id": duenio_id})`, `add`, `commit`, `FichaRead`, D-9); ruta `POST /{id}/ficha` con 201 → verde
- [x] 6.3 RED: caso C-03 `test_segunda_ficha_responde_409_y_conserva_la_primera` (`POST /duenios/1/ficha` → 409 `{"detail": "El dueño ya tiene una ficha"}`; la ficha 1 conserva teléfono y dirección) → falla (error del servidor)
- [x] 6.4 GREEN: `RECHAZOS_FICHA` con `uq_ficha_duenio_duenio_id` → 409 y el `try/except` → verde
- [x] 6.5 RED: `test_ficha_de_duenio_inexistente_responde_404` (`POST /duenios/999/ficha` → 404 `{"detail": "No existe el dueño"}`; `ficha_duenio` con 1 fila) → falla (la FK no está en el mapa → 409 genérico en vez del 404)
- [x] 6.6 GREEN: agregar `ficha_duenio_duenio_id_fkey` → 404 a `RECHAZOS_FICHA` → verde
- [x] 6.7 TRIANGULATE: cuerpos inválidos parametrizados (sin `direccion`, `telefono` vacío, con `duenio_id`) → 422 y el dueño 2 sigue sin ficha; con `sentencias_app`: ficha de dueño inexistente y segunda ficha → una sola sentencia, `INSERT INTO ficha_duenio`
- [x] 6.8 REFACTOR: `responses={404: ..., 409: ...}`; tests en verde

## 7. Mascotas del dueño (`GET /duenios/{id}/mascotas`, PA-09)

- [x] 7.1 RED: `test_mascotas_de_duenio_con_dos_mascotas` (`GET /duenios/1/mascotas` → lista exacta del spec, ordenada por `id`) → falla con 404
- [x] 7.2 GREEN: `app/modules/mascotas/schemas.py` con `MascotaRead` (`id`, `nombre`, `especie`, `duenio_id`; D-11); `service.listar_mascotas` (`selectinload(Duenio.mascotas)`, 404 si no hay dueño, `sorted(..., key=attrgetter("id"))`, D-10); ruta `GET /{id}/mascotas` con `response_model=list[MascotaRead]` → verde
- [x] 7.3 TRIANGULATE: dueño 2 → `[Luna]`; dueño 3 recién creado → `[]`; `GET /duenios/999/mascotas` → 404; orden por `id` con mascotas insertadas por `sesion` en distinto orden alfabético
- [x] 7.4 RED/GREEN: `test_mascotas_del_duenio_usan_dos_consultas` parametrizado por 1, 2 y 4 mascotas (dueño 3 con cuatro mascotas insertadas con `sesion`) → 2 sentencias (`duenio` y `mascota`); dueño inexistente → 1 sentencia; si pasa de entrada, mutación quitando el `selectinload` (`MissingGreenlet` → rojo) y registrarla
- [x] 7.5 REFACTOR: `responses={404: ...}`; tests en verde

## 8. Borrado (`DELETE /duenios/{id}`, RN-08, caso C-05 primera parte)

- [x] 8.1 RED: `test_borrar_duenio_sin_mascotas_ni_ficha_responde_204` (dueño 3 creado con `POST`, `DELETE /duenios/3` → 204 sin cuerpo; `duenio` vuelve a los dueños 1 y 2) → falla con 405
- [x] 8.2 GREEN: `service.borrar_duenio` con `await session.exec(delete(Duenio).where(Duenio.id == duenio_id))` + `commit` (D-7); ruta `DELETE /{id}` con `status_code=204` → verde
- [x] 8.3 RED: `test_borrar_duenio_inexistente_responde_404` (`DELETE /duenios/999` → 404 `{"detail": "No existe el dueño"}`) → falla (responde 204)
- [x] 8.4 GREEN: `rowcount == 0` → 404 → verde; TRIANGULATE: borrar dos veces el mismo dueño → 204 y luego 404
- [x] 8.5 RED: caso C-05 `test_borrar_duenio_con_mascotas_responde_409_y_no_borra_nada` (`DELETE /duenios/1` → 409 `{"detail": "No se puede borrar el dueño: tiene mascotas a su nombre"}`; con `sesion`: dueño 1, ficha 1 y mascotas 1 y 2 siguen) → falla (error del servidor)
- [x] 8.6 GREEN: `RECHAZOS_BORRADO` con `mascota_duenio_id_fkey` → 409 y el `try/except` alrededor del `exec` → verde
- [x] 8.7 TRIANGULATE: `test_borrar_duenio_con_ficha_y_sin_mascotas_borra_la_ficha` (dueño 3 con ficha → 204; `GET /duenios/3` → 404; `ficha_duenio` sin filas con `duenio_id = 3`); con `sentencias_app`: en 204, 404 y 409 la única sentencia es `DELETE FROM duenio` (sin `SELECT`, ni sentencias sobre `mascota` o `ficha_duenio`)
- [x] 8.8 REFACTOR: `responses={404: ..., 409: ...}`; tests en verde

## 9. Contrato del router (todas las rutas)

- [x] 9.1 TRIANGULATE caso C-01 en las demás rutas: `PATCH /duenios/abc`, `DELETE /duenios/abc`, `POST /duenios/abc/ficha` y `GET /duenios/abc/mascotas` → 422 con `loc == ["path", "id"]`; nada cambió en la base
- [x] 9.2 RED/GREEN: `test_openapi_declara_los_codigos_de_la_consigna` (lee `/openapi.json`: `POST /duenios/` → 201, 409, 422; `GET /duenios/{id}` → 200, 404, 422; `PATCH` → 200, 404, 409, 422; `DELETE` → 204, 404, 409; `POST .../ficha` → 201, 404, 409; `GET .../mascotas` → 200, 404; los 404/409 referencian el esquema `MensajeError`) → completar los `responses` que falten
- [x] 9.3 `test_handlers_de_duenios_son_async` (todas las rutas del router: `inspect.iscoroutinefunction(route.endpoint)`); revisión: cada handler es una sola línea `return await service.<funcion>(...)`, sin queries ni `if` en `router.py`
- [x] 9.4 REFACTOR: orden y nombres de las funciones del service según D-14; tests en verde

## 10. Casos `.http` (`test/duenios.http`)

- [x] 10.1 RED: `tests/test_duenios_http.py::test_duenios_http_documenta_los_casos_de_la_consigna` (el archivo existe; contiene `GET {{base}}/duenios/abc` y los rótulos "Caso C-01", "Caso C-02", "Caso C-03", "Caso C-05"; cada bloque `###` tiene un comentario `# Esperado:`) → falla porque el archivo no existe
- [x] 10.2 GREEN: escribir `test/duenios.http` con las 21 peticiones de D-19, en ese orden, con el aviso inicial (correr una vez y en orden después de `python reiniciar.py`; marcas **[modifica]**) → verde
- [x] 10.3 TRIANGULATE: helper `bloques_http(ruta)` en `tests/soporte.py` (separa por `###`, lee método, URL, cabeceras, cuerpo y el primer código de `# Esperado:`); `test_duenios_http_corre_en_orden_con_los_codigos_esperados` (con `base_con_seed`: envía cada bloque con `client`, reemplazando `{{base}}`, y compara el código de estado con el del comentario)
- [x] 10.4 REFACTOR: tests en verde

## 11. Verificación final

- [x] 11.1 `pytest` completo en verde: línea base de 0.4 + los tests nuevos, sin tests omitidos por falta de base
- [x] 11.2 Manual: `python reiniciar.py` sobre la base de desarrollo, `uvicorn app.main:app`, ejecutar cada petición de `test/duenios.http` en orden con `curl` y comparar código y cuerpo con su comentario; registrar la salida en el resumen del `apply`
- [x] 11.3 Revisión contra las reglas duras: todos los handlers `async def`; ninguna consulta "¿ya existe?" antes de una escritura (sin `SELECT` por email ni por `duenio_id` antes de escribir); el router no devuelve modelos de tabla; `extra="forbid"` en `DuenioCreate`, `DuenioUpdate` y `FichaCreate`; sin `session.execute` (deprecado en SQLModel), sin `asyncio.gather` sobre la sesión, sin `TODO`; `app/modules/laboratorio/cliente.py` sin tocar
- [x] 11.4 Marcar PA-01, PA-09 y PA-11 como **RESUELTAS** en `knowledge-base/10_preguntas_abiertas.md`, apuntando a este `design.md` (como C-01 con PA-04/06/08)
- [x] 11.5 `openspec validate duenios-fichas --strict` sin errores; completar la tabla "TDD Cycle Evidence" en el resumen del `apply`
- [x] 11.6 Guardar en engram (`opsx/duenios-fichas/apply`) el resultado y el aviso para C-04..C-06: copiar el patrón (constantes `RECHAZOS_*` por operación + `traducir_rechazo`), reutilizar `IdRuta`, `MensajeError` y `MascotaRead`
