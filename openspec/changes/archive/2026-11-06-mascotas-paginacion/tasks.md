> **Governance MEDIO**: implementar con checkpoints y revisar las decisiones marcadas ⚠ del `design.md` (D-1 PA-05, D-4 cuerpo del 422 de página, D-7 DTO) antes de empezar (tarea 0.1).
>
> **TDD estricto** (contra PostgreSQL real `veterinaria_test`, nunca SQLite ni mocks de la sesión): cada grupo sigue RED → GREEN → TRIANGULATE → REFACTOR y se ejecuta `pytest` en cada paso. Si un test pasa de entrada porque FastAPI o el código de un grupo anterior ya cubre la propiedad, comprobar que falla rompiendo temporalmente esa propiedad (mutación) y registrarlo en la evidencia TDD. Los módulos de test nuevos declaran `pytestmark = pytest.mark.integracion` y usan `base_con_seed` (o `esquema_vacio`) + `client`; los conteos de sentencias usan `sentencias_app` (`.clear()` justo antes de la petición medida). Seed: dueño 1 Ana Gómez (mascotas 1 Toby/perro, 2 Mishi/gato), dueño 2 Carlos Ruiz (mascota 3 Luna/perro).
>
> **Entregable en `test/`**: `test/mascotas.http` (grupo 9) con el caso C-04 (primera parte) de la consigna.

## 0. Gobernanza y entorno

- [x] 0.1 Revisar con el equipo las decisiones ⚠ del `design.md` (D-1 `pages = 0` con `total = 0` y regla `page > max(pages, 1)` → 422; D-4 contar primero y 422 con cuerpo en formato de validación, `type` `pagina_fuera_de_rango` y `ctx.pages`; D-7 `MascotaRead` intacto + `MascotaCreate`, `MascotaConDuenioRead`, `PaginaMascotas`); registrar la aprobación (fecha y quién) en el encabezado de cada una *(aprobadas por Lautaro Mejias el 2026-11-06; registrado en D-1, D-4 y D-7 del design.md)*
- [x] 0.2 Verificar que C-03 `duenios-fichas` está archivado (`openspec list --json` sin él; `openspec/changes/archive/2026-11-05-duenios-fichas/` existe) y que existen `app/core/errores.py` (`Rechazo`, `traducir_rechazo`, `MensajeError`), `app/core/parametros.py` (`IdRuta`, `ENTERO_MAXIMO`), `ENTRADA` y `DuenioRead` en `app/modules/duenios/schemas.py`, `MascotaRead` en `app/modules/mascotas/schemas.py` y las fixtures `sentencias_app`, `base_con_seed`, `esquema_vacio`, `sesion` y el helper `bloques_http`
- [x] 0.3 `docker compose up -d --wait`; la base `veterinaria_test` responde; `.venv/Scripts/python.exe -c "from fastapi import status; status.HTTP_422_UNPROCESSABLE_CONTENT"` sin error
- [x] 0.4 Safety net: `pytest` completo en verde; anotar la línea base "N tests passing" (se modifican `app/main.py` y `app/modules/mascotas/schemas.py`)

## 1. Detalle de la mascota con su dueño (`GET /mascotas/{id}`, D-8)

- [x] 1.1 RED: `tests/test_mascotas.py::test_obtener_mascota_responde_200_con_su_duenio` parametrizado por mascota 1 (Toby / Ana Gómez) y mascota 3 (Luna / Carlos Ruiz), con el cuerpo exacto del spec → falla con 404 (la ruta no existe)
- [x] 1.2 GREEN: en `app/modules/mascotas/schemas.py` agregar `MascotaConDuenioRead(MascotaRead)` con `duenio: DuenioRead` (sin tocar `MascotaRead`); crear `app/modules/mascotas/service.py` con `obtener_mascota(session, mascota_id)` (`select(Mascota).where(...).options(joinedload(Mascota.duenio))`, `one_or_none`, `MascotaConDuenioRead.model_validate`); crear `app/modules/mascotas/router.py` (`APIRouter(prefix="/mascotas", tags=["mascotas"])`, `GET /{id}` de una línea con `id: IdRuta` llamando `service.obtener_mascota` por el módulo, D-10); `include_router(mascotas_router)` en `crear_app()` después de `duenios_router` → verde
- [x] 1.3 TRIANGULATE: `test_obtener_mascota_inexistente_responde_404` parametrizado (`999`, `0`, `2147483647`) con cuerpo exacto `{"detail": "No existe la mascota"}` → rojo hasta agregar `MASCOTA_INEXISTENTE` y el `HTTPException` 404; `test_obtener_mascota_con_id_invalido_responde_422` parametrizado (`abc` → `int_parsing`, `2147483648` → `less_than_equal`, `loc == ["path", "id"]`)
- [x] 1.4 TRIANGULATE (no-regresión): `test_mascotas_del_duenio_siguen_iguales` (`GET /duenios/1/mascotas` responde el cuerpo exacto de la spec `duenios-y-fichas`, sin clave `duenio`) → verde
- [x] 1.5 REFACTOR: `responses={404: {"model": MensajeError, ...}}` y `response_model=MascotaConDuenioRead` en la ruta; tests en verde

## 2. Detalle sin N+1 (Ej. 5)

- [x] 2.1 RED/GREEN: `tests/test_mascotas_consultas.py::test_detalle_de_mascota_usa_una_sola_consulta` parametrizado por mascotas 1 y 3: exactamente 1 sentencia, un `SELECT` sobre `mascota` que contiene `JOIN duenio` → pasa de entrada por 1.2: mutación quitando temporalmente el `joinedload` (el service falla con `MissingGreenlet` → rojo) y registrarla
- [x] 2.2 TRIANGULATE: `test_id_de_ruta_invalido_no_envia_sentencias` (`GET /mascotas/abc` y `/2147483648` → `sentencias_app` vacía) → verde

## 3. Alta de mascota (`POST /mascotas/`, D-6 y D-7)

- [x] 3.1 RED: `test_crear_mascota_valida_responde_201` (`{"nombre": "Rocky", "especie": "perro", "duenio_id": 2}` → 201 cuerpo exacto `{"id": 4, ...}`; `GET /duenios/2/mascotas` devuelve las mascotas 3 y 4) → falla con 405
- [x] 3.2 GREEN: `MascotaCreate` (`model_config = ENTRADA` importado de `duenios.schemas`; `nombre` y `especie` `Field(min_length=1)`; `duenio_id: int = Field(le=ENTERO_MAXIMO)`); `service.crear_mascota` (`Mascota.model_validate(datos)`, `add`, `commit`, `MascotaRead.model_validate`); ruta `POST /` con `status_code=201` y `response_model=MascotaRead` → verde
- [x] 3.3 TRIANGULATE: `test_crear_mascota_guarda_los_textos_sin_espacios` (`"  Pelusa  "`, `" gato "`, dueño 1 → 201 con `"Pelusa"` y `"gato"`; leer la fila con `sesion` para confirmar lo guardado)
- [x] 3.4 REFACTOR: tests en verde

## 4. Alta con dueño inexistente → 409 (caso C-04, primera parte)

- [x] 4.1 RED: caso C-04 `test_crear_mascota_con_duenio_inexistente_responde_409` (`duenio_id` 999 → 409 cuerpo exacto `{"detail": "No existe el dueño indicado"}`; el cuerpo no contiene `mascota_duenio_id_fkey`, `foreign key`, `INSERT` ni `asyncpg`; `mascota` sigue con 3 filas) → falla (el `IntegrityError` se propaga → error del servidor)
- [x] 4.2 GREEN: `try/except IntegrityError` → `await session.rollback()` → `raise traducir_rechazo(exc, RECHAZOS_ALTA) from exc` con `RECHAZOS_ALTA = {"mascota_duenio_id_fkey": Rechazo(409, DUENIO_INDICADO_INEXISTENTE)}` → verde
- [x] 4.3 TRIANGULATE: parametrizar con `duenio_id` `0` y `-1` (→ 409 mismo cuerpo, 3 filas); `test_despues_de_un_409_la_siguiente_alta_funciona` (409 y luego 201 con 4 filas)
- [x] 4.4 RED/GREEN: `tests/test_mascotas_consultas.py::test_alta_con_duenio_inexistente_no_consulta_antes_de_escribir` (una sola sentencia, `INSERT INTO mascota`, ningún `SELECT`) → si pasa de entrada, mutación agregando temporalmente un `session.get(Duenio, ...)` antes del `add` (rojo) y registrarla
- [x] 4.5 REFACTOR: constantes `DUENIO_INDICADO_INEXISTENTE` y `RECHAZOS_ALTA` (`Final`); `responses={409: {"model": MensajeError, ...}}` en la ruta; tests en verde

## 5. Contrato de entrada del alta → 422

- [x] 5.1 RED/GREEN: `test_crear_mascota_con_cuerpo_invalido_responde_422` parametrizado con los 8 cuerpos del spec (faltan `nombre`/`especie`/`duenio_id`; `nombre` `"   "`; `especie` `""`; `duenio_id` `"abc"`; `duenio_id` `2147483648`; campo `id`), cada uno con su `loc` y `type` esperados, y `mascota` con 3 filas → los que pasen de entrada por 3.2 se prueban por mutación (quitar temporalmente `le=ENTERO_MAXIMO` → `2147483648` termina en error del servidor; quitar `extra="forbid"` → `id` se acepta) y se registran
- [x] 5.2 REFACTOR: tests en verde

## 6. Envoltorio del listado (`GET /mascotas/`, D-2, D-5, PA-12)

- [x] 6.1 RED: `tests/test_mascotas_paginacion.py::test_listado_por_defecto_devuelve_el_envoltorio` (cuerpo exacto del spec: 3 items, `total` 3, `page` 1, `size` 20, `pages` 1) → falla con 405
- [x] 6.2 GREEN: en `schemas.py` agregar `PaginaMascotas` (`items: list[MascotaRead]`, `total`, `page`, `size`, `pages`) y las constantes `TAMANIO_POR_DEFECTO = 20`, `TAMANIO_MAXIMO = 100`; `service.listar_mascotas(session, page, size)` con `select(func.count()).select_from(Mascota)` y `select(Mascota).order_by(Mascota.id).offset((page - 1) * size).limit(size)`, `pages = (total + size - 1) // size`; ruta `GET /` con los alias `Pagina` y `TamanioPagina` (`Annotated[int, Query(...)]`, defaults en la asignación, D-3) → verde
- [x] 6.3 TRIANGULATE: `test_ultima_pagina_incompleta` (`?page=2&size=2` → cuerpo exacto con Luna, `pages` 2); `test_pagina_en_el_borde` parametrizado (`?page=1&size=3` → ids `[1, 2, 3]`, `pages` 1; `?page=3&size=1` → ids `[3]`, `pages` 3); `test_tamanios_en_el_limite` (`size=1` → id 1, `pages` 3; `size=100` → 3 items, `pages` 1)
- [x] 6.4 TRIANGULATE (PA-12): `test_listado_ordenado_por_id_aunque_cambie_el_orden_fisico` (con `sesion`: `UPDATE mascota SET nombre = 'Toby' WHERE id = 1` + `commit` deja la fila 1 última en el heap; `GET /mascotas/` → ids `[1, 2, 3]`) → mutación quitando temporalmente el `order_by` (rojo) y registrarla
- [x] 6.5 TRIANGULATE (PA-05): `test_listado_vacio_responde_la_primera_pagina` con `esquema_vacio` (cuerpo exacto `{"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}`)
- [x] 6.6 REFACTOR: `response_model=PaginaMascotas` y descripción de la ruta con la regla de rango; tests en verde

## 7. Tamaño y número de página inválidos (validación de query, D-3)

- [x] 7.1 RED/GREEN: `test_tamanio_invalido_responde_422` parametrizado (`size=0` → `greater_than_equal`, `101` → `less_than_equal`, `-5` → `greater_than_equal`, `abc` → `int_parsing`; `loc == ["query", "size"]`) y `test_pagina_invalida_responde_422` parametrizado (`page=0`, `-1` → `greater_than_equal`; `abc` → `int_parsing`; `loc == ["query", "page"]`) → lo que pase de entrada por 6.2 se prueba por mutación (quitar temporalmente `le=TAMANIO_MAXIMO` → `size=101` da 200; quitar `ge=1` de `page` → `page=0` llega al service) y se registra
- [x] 7.2 TRIANGULATE: en `tests/test_mascotas_consultas.py`, `test_parametros_invalidos_no_envian_sentencias` (`?size=0`, `?page=abc` → `sentencias_app` vacía)

## 8. Página fuera de rango → 422 (PA-05, D-1 y D-4)

- [x] 8.1 RED: `test_pagina_mas_alla_de_pages_responde_422` (`?page=3&size=2` → 422 cuerpo exacto `{"detail": [{"type": "pagina_fuera_de_rango", "loc": ["query", "page"], "msg": "La página pedida no existe", "input": 3, "ctx": {"pages": 2}}]}`) → falla (200 con `items: []`)
- [x] 8.2 GREEN: en `service.listar_mascotas`, después del conteo, `if page > max(pages, 1): raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=[...])` con la constante `PAGINA_INEXISTENTE` → verde
- [x] 8.3 TRIANGULATE: `?page=2` con los valores por defecto → 422 con `ctx` `{"pages": 1}`; con `esquema_vacio`, `?page=1` → 200 y `?page=2` → 422 con `ctx` `{"pages": 0}` (mutación: cambiar temporalmente `max(pages, 1)` por `pages` → la página 1 vacía da 422 → rojo; registrarla)
- [x] 8.4 REFACTOR: extraer el armado del detalle del 422 a una función privada si mejora la lectura; `responses={422: ...}` documentado; tests en verde

## 9. Listado sin N+1 (Ej. 5, D-5)

- [x] 9.1 RED/GREEN: `tests/test_mascotas_consultas.py::test_listado_usa_dos_consultas` parametrizado por `size` 1, 3 y 20 con 25 mascotas (22 agregadas con `sesion` y `text("INSERT INTO mascota ...")`): exactamente 2 sentencias, la primera con `count`, ambas `FROM mascota`, ninguna con `duenio` → verde de entrada por 6.2: mutación agregando temporalmente `joinedload(Mascota.duenio)` a la consulta de la página (aparece `duenio` → rojo) y registrarla
- [x] 9.2 TRIANGULATE: `test_pagina_fuera_de_rango_solo_cuenta` (`?page=5` → 422 y exactamente 1 sentencia con `count`)

## 10. Entregable `test/mascotas.http` (D-12)

- [x] 10.1 RED: `tests/test_mascotas_http.py::test_mascotas_http_documenta_el_caso_c04` (el archivo existe, contiene "Caso C-04" y `POST {{base}}/mascotas/`, cada bloque `###` tiene `# Esperado:`) y `test_mascotas_http_corre_en_orden_con_los_codigos_esperados` (con `bloques_http` sobre `base_con_seed`: 13 bloques, cada código coincide) → falla (no existe el archivo)
- [x] 10.2 GREEN: escribir `test/mascotas.http` con el encabezado (correr en orden y una vez tras `python reiniciar.py`; `[modifica]`; ids consumidos por el 409) y los 13 bloques de la tabla de D-12, cada uno con `# Esperado: <código> <cuerpo>` → verde
- [x] 10.3 Verificación manual: `python reiniciar.py`, `uvicorn app.main:app`, ejecutar cada bloque (REST Client o `curl`) y comparar código **y cuerpo** con su comentario; corregir el comentario o el código si difieren *(equivalente sin servidor/credenciales: `tests/test_mascotas_http.py` ejecuta los 13 bloques con httpx contra `veterinaria_test` y compara códigos; los cuerpos de los comentarios coinciden con los de la spec, cubiertos por `test_mascotas*.py`)*

## 11. Integración y cierre

- [x] 11.1 `pytest` completo en verde: línea base de 0.4 + los tests nuevos, sin fallos ni advertencias nuevas; `GET /duenios/{id}/mascotas` sin cambios
- [x] 11.2 `python reiniciar.py` sobre una base vacía sigue funcionando y `/docs` muestra las tres rutas de `mascotas` con sus `responses` *(verificado vía `recrear_esquema` de las fixtures y `app.openapi()`: POST / 201,409,422; GET / 200,422; GET /{id} 200,404,422)*
- [x] 11.3 Revisar reglas duras: handlers `async def`, router sin lógica, sin consultas previas, `extra="forbid"` en `MascotaCreate`, type hints en todas las firmas, sin `float`, nombres en español sin ñ
- [x] 11.4 Marcar **PA-05** y **PA-12** como **RESUELTA** en `knowledge-base/10_preguntas_abiertas.md`, apuntando a `openspec/changes/mascotas-paginacion/design.md` (D-1 y D-2), y verificar que `openspec validate mascotas-paginacion --strict` pasa
- [x] 11.5 Completar la evidencia TDD (tabla Task / Test File / Layer / Safety Net / RED / GREEN / TRIANGULATE / REFACTOR, con las mutaciones registradas)

## Workflow follow-up

- `/opsx:archive mascotas-paginacion` con `pytest` en verde y `test/mascotas.http` escrito; marcar `[x]` el estado de C-04 en `CHANGES.md`.
- Al integrar con C-05, conservar ambos `include_router` en `app/main.py`.
- Commit Conventional (`feat(mascotas): ...`) sin líneas de co-autor de IA; `push` sólo con confirmación del integrante.
