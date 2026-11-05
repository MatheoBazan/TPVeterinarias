# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Flujo de trabajo OPSX/SDD con TDD estricto
**Decisión**: trabajo universitario con OpenSpec (OPSX) y TDD estricto. **Contexto**: grupo de 3 (Matheo Bazan, Lautaro Mejias, Uriel Vega). **Justificación**: política de la facultad. **Trade-off**: más ceremonia para un TP breve.

### DD-02 — Versiones del stack
**Decisión**: respetar los mínimos del PDF (Python ≥3.12, FastAPI ≥0.111, SQLModel ≥0.0.24, SQLAlchemy 2.0 async, asyncpg ≥0.30, PostgreSQL ≥16, python-dotenv ≥1.0, uvicorn de `fastapi[standard]`); desarrollo local con Python 3.14. **Trade-off**: compatibilidad de wheels con 3.14 por validar (ver `10`).

### DD-03 — Base de desarrollo en Docker
**Decisión**: `postgres:16` con `docker-compose.yml` en el repo; `DATABASE_URL` en `.env` no versionado, `env.example` sin secretos. **Justificación**: reproducibilidad y PostgreSQL ≥16 exigido.

### DD-04 — Pruebas: pytest + httpx, base separada, dos carpetas
**Decisión**: suite pytest en `tests/` (httpx `AsyncClient`/`ASGITransport`, `TEST_DATABASE_URL` → `veterinaria_test`, `requirements-dev.txt`); los `.http` y el `.sql` de C-08 en `test/` exactamente como exige el PDF. **Justificación**: TDD estricto exige tests automáticos; el PDF exige `.http`. **Trade-off**: duplicar cobertura (automática + `.http`) y riesgo de confundir carpetas (documentado).

### DD-05 — `ficha_duenio.duenio_id` ON DELETE CASCADE (propuesta; el PDF no lo especifica)
**Decisión**: CASCADE. **Contexto**: relación uno a uno en la que la ficha no tiene sentido sin su dueño; `DELETE /duenios/{id}` solo debe responder 409 por mascotas (RN-08), así un dueño con ficha y sin mascotas se borra con 204. **Alternativas**: RESTRICT (obligaría a 409 por la ficha, contradice los códigos del endpoint), SET NULL (rompe NOT NULL/UNIQUE de sentido). **Trade-off**: borrado en cadena de la ficha. Listada en `10`.

### DD-06 — `turno.mascota_id` ON DELETE RESTRICT (propuesta)
**Decisión**: RESTRICT. **Justificación**: asociación; no existe `DELETE /mascotas`; un turno no debe perder su mascota. Listada en `10`.

### DD-07 — `turno_practica.practica_id` ON DELETE RESTRICT (propuesta)
**Decisión**: RESTRICT. **Justificación**: no existe `DELETE /practicas`; el historial de precios cobrados debe sobrevivir. Listada en `10`.

### DD-08 — Sin pre-chequeos de existencia; escribir y atrapar `IntegrityError`
**Decisión**: según el PDF, el service no consulta "¿ya existe?"; hace rollback y responde 409 con mensaje propio. **Justificación**: evita la ventana de carrera (sec. 4.10). **Abierto**: cómo distinguir FK en recurso de ruta (404) de UNIQUE (409): ver `10`.

### DD-09 — Todo o nada en el alta de turno; RN-07 por PK compuesta
**Decisión**: turno + `turno_practica` en una transacción; práctica repetida se rechaza con la PK compuesta (409), **no** en el DTO; lista vacía → 422 en el DTO (`min_length=1`).

### DD-10 — Precio congelado y total del servidor
**Decisión**: el DTO no lleva precio ni total; se copia `practica.precio` a `turno_practica.precio_unitario` y `turno.total` = suma calculada por el servidor, con `Decimal`.

### DD-11 — Formato de respuesta del turno
**Decisión**: `fecha` en UTC con `Z`; dinero como string con 2 decimales (`"27000.00"`); `mascota {id, nombre, especie}`; `practicas [{practica_id, nombre, precio_unitario}]`. `fecha` es `TIMESTAMP WITH TIME ZONE`.

### DD-12 — Índices
**Decisión**: índices explícitos en `mascota.duenio_id`, `turno.mascota_id`, `turno_practica.practica_id`; ninguno propio en `turno_practica.turno_id` (es la columna izquierda de la PK compuesta); `ficha_duenio.duenio_id` ya tiene índice por UNIQUE. Explicación obligatoria en el README.

### DD-13 — Relaciones y borrado en cascada delegado a la base
**Decisión**: `back_populates` en ambos extremos; `Duenio.ficha` con `uselist=False`; los cinco lados "uno" (`Turno.practicas`, `Duenio.ficha`, `Duenio.mascotas`, `Mascota.turnos`, `Practica.turnos`) con `passive_deletes="all"` y sin `cascade_delete` (la base decide: CASCADE o RESTRICT). Antes decía `passive_deletes=True`; se cambió a `"all"` porque con `True` el ORM igual emite `UPDATE ... SET NULL`/`DELETE` sobre las hijas que están cargadas en la sesión (ver D-7 de `openspec/changes/modelos-esquema-seed/design.md`).

### DD-14 — Carga anticipada, nunca perezosa
**Decisión**: `joinedload` para a-uno, `selectinload` para colecciones, en la misma consulta; número fijo de consultas; evidencia C-07 con `echo=True` (bandera por env var para activarlo).

### DD-15 — Lifespan y sesión
**Decisión**: motor y fábrica en el `lifespan`, en `app.state`, `dispose` al apagar; `get_session` por `Depends`, una sesión por petición, `expire_on_commit=False`.

### DD-16 — Health
**Decisión**: `live` no toca la base (`{"estado": "vivo"}`); `ready` ejecuta `SELECT 1` y responde 503 si falla. El cuerpo exacto de "Estado de la base" no está especificado: usar p. ej. `{"estado": "listo"}` / `{"estado": "sin base"}` (**Suposición**, ver `10`).

### DD-17 — Laboratorio fuera del bucle
**Decisión**: `cliente.py` no se modifica; el handler lo invoca con `asyncio.to_thread` / `run_in_threadpool`.

### DD-18 — Paginación de mascotas
**Decisión**: envoltorio `{items, total, page, size, pages}`; `size` default 20, rango 1–100; `page` mayor a `pages` → 422; primera página siempre responde.

### DD-19 — Git
**Decisión**: repo privado de GitHub; Conventional Commits **sin** líneas de co-autor de IA.

### DD-20 — Fuera de alcance
Sin auth, repositorios/UoW, colas ni Alembic; esquema por `create_all`.

## Supuestos inferidos

### SU-01 — Seed que reproduce el ejemplo del PDF
**Supuesto**: el seed fija mascota 1 = "Toby" (perro), práctica 1 = "Consulta" 15000.00, práctica 3 = "Vacuna antirrábica" 12000.00 y turno seed con id 1 (el del ejemplo recibe id 2). **Origen**: respuesta de `POST /turnos/` del Ej. 4. **Riesgo**: el corrector compara contra el ejemplo y no coincide. **Validar**: test que ejecute el cuerpo de ejemplo y compare con la respuesta.

### SU-02 — FK de mascota inexistente en el turno → 409
**Supuesto**: igual que C-04 (mascota con dueño inexistente → 409), un `mascota_id` inexistente en `POST /turnos/` responde 409. **Origen**: tabla de endpoints (codes 201/409/422 sin 404). **Riesgo**: bajo.

### SU-03 — Ids autoincrementales y reinicio
**Supuesto**: `reiniciar.py` hace `drop_all` + `create_all`, reiniciando secuencias. **Riesgo**: ids del seed distintos de los esperados.

### SU-04 — Orden de ejecución de los `.http`
**Supuesto**: cada caso corre tras `python reiniciar.py`; los casos C-05/C-06 dependen del estado (p. ej. borrar el turno 1; crear el turno 2). **Validar**: documentar el orden en `test/`.

### SU-05 — Validación de email con formato
**Supuesto**: `EmailStr` (requiere `email-validator`, incluido en `fastapi[standard]`). **Riesgo**: bajo; el PDF solo exige unicidad.

### SU-06 — API pública
**Supuesto**: todos los endpoints públicos; el despliegue es solo local/académico.

### SU-07 — Nombres de prácticas 2 y 4 del seed
**Supuesto**: libres (p. ej. "Desparasitación"). **Riesgo**: nulo mientras 1 y 3 coincidan.

### SU-08 — Zona horaria de `fecha`
**Supuesto**: se acepta ISO 8601 con offset; el valor se normaliza a UTC al responder. Una `fecha` sin offset: comportamiento abierto (ver `10`).

### SU-09 — Códigos de reglas
**Supuesto**: usar `RN-01..RN-09` y `C-01..C-09`, igual que el PDF (que usa un guion no separable; la extracción de texto lo pierde, ver IN-02).
