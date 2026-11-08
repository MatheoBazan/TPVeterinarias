# Preguntas Abiertas

## Inconsistencias detectadas

### IN-01 — Cantidad de endpoints (RESUELTA, no es inconsistencia del PDF)
El PDF lista **17** filas en "Endpoints de referencia" (2 health, 6 duenios, 3 mascotas, 2 practicas, 3 turnos, 1 laboratorio). Un brief interno decía 15 por error de conteo. **Resolución**: la fuente es el PDF → 17.

### IN-02 — Códigos `RN-01` / `C-01` (RESUELTA, no es inconsistencia del PDF)
El PDF escribe `RN‑01` y `C‑01` con un guion no separable (U+2011) que la extracción de texto pierde; en las páginas renderizadas el guion se ve. **Resolución**: la KB usa `RN-01..RN-09` y `C-01..C-09`, igual que el PDF.

### IN-03 — "La mascota puede cambiar de dueño" sin endpoint
**PDF (contexto)**: la mascota puede cambiar de dueño. **Endpoints**: no hay PATCH/PUT de mascota. **Impacto**: requisito de negocio sin superficie en la API. **Resolución**: no implementar (no inventar requisitos); confirmar con la cátedra.

### IN-04 — "Si después cambia el precio del catálogo" sin endpoint de edición
**PDF**: el precio del catálogo puede cambiar; **endpoints**: solo POST/GET de prácticas. C-08 lo hace por SQL directo. **Resolución**: no agregar PATCH de práctica; probar el congelado con SQL directo en un test.

### IN-05 — Texto extraído del PDF con glitches
Los textos extraídos muestran `= 0` en lugar de `>= 0` (CHECK `total >= 0`), tablas desordenadas y paréntesis perdidos; la tabla de endpoints y la de reglas salen desordenadas. Se reconstruyeron con las imágenes/contexto; sin impacto en la KB. Nota: la tabla de modelo de dominio no indica ON DELETE para `ficha_duenio`, `turno.mascota_id` ni `turno_practica.practica_id` (ver PA-02).

## Preguntas abiertas (priorizadas)

| ID | Prioridad | Pregunta | Bloquea | Decisor |
|----|-----------|----------|---------|---------|
| PA-01 | Alta | Cómo distinguir sin pre-chequeo una violación de FK sobre un recurso de la ruta (`POST /duenios/{id}/ficha` con dueño inexistente → 404) de una de UNIQUE (→ 409). Propuesta: inspeccionar `sqlstate` (23503 FK / 23505 UNIQUE) y `constraint_name` del error de asyncpg (`e.orig.__cause__`) | Ficha, alta de mascota/turno | Equipo técnico | **RESUELTA** en `openspec/changes/duenios-fichas/design.md` (D-1 y D-2: traducción por `constraint_name` con un mapa por operación; rechazo no previsto → 409 genérico; aprobada con cambios por Matheo el 2026-11-05).
| PA-02 | Alta | ON DELETE no especificado: `ficha_duenio.duenio_id` (propuesta CASCADE), `turno.mascota_id` (RESTRICT), `turno_practica.practica_id` (RESTRICT). ¿Se confirman? (DD-05/06/07) | Esquema (Ej. 3) | Equipo / cátedra | **RESUELTA** en `openspec/changes/modelos-esquema-seed/design.md` (D-4, aprobada por Matheo el 2026-11-05).
| PA-03 | Alta | Seed exacto que reproduce el ejemplo de Ej. 4 (mascota 1 Toby/perro, práctica 1 Consulta 15000, práctica 3 Vacuna antirrábica 12000, turno seed id 1). Nombres/precios de prácticas 2 y 4 y de dueños/mascotas restantes | `reiniciar.py` | Equipo | **RESUELTA** en `openspec/changes/modelos-esquema-seed/design.md` (D-13, aprobada por Matheo el 2026-11-05).
| PA-04 | Media | Compatibilidad de Python 3.14 con asyncpg ≥0.30, SQLModel 0.0.24 y pydantic (wheels/soporte). El PDF solo exige ≥3.12; ¿fijar versiones en `requirements.txt` o usar 3.12/3.13? | Instalación | Equipo | **RESUELTA** en `openspec/changes/base-proyecto-conexion/design.md` (D-12).
| PA-05 | Media | Valor de `pages` cuando `total = 0` (¿0 o 1?) y regla exacta de "página más allá de `pages`" con la primera página siempre válida. Propuesta: `pages = 0`, `page=1` responde con `items=[]`, `page>max(pages,1)` → 422 | Paginación | Equipo | **RESUELTA** en `openspec/changes/archive/2026-11-06-mascotas-paginacion/design.md` (D-1: `pages = ceil(total / size)`, 0 sin mascotas; la página 1 siempre responde y `page > max(pages, 1)` → 422 con cuerpo en formato de validación, D-4; aprobada por Lautaro el 2026-11-06).
| PA-06 | Media | Cuerpo exacto de `/health/ready` ("Estado de la base") y del 503 | Health | Equipo | **RESUELTA** en `openspec/changes/base-proyecto-conexion/design.md` (D-9 y D-10).
| PA-07 | Media | Orden de ejecución y estado previo de los `.http` (C-05 borra el turno 1; C-06 crea el turno 2): ¿se exige `reiniciar.py` entre casos? | `test/` | Equipo |
| PA-08 | Media | Forma de activar `echo=True` para C-07 (env var `SQL_ECHO` propuesta) sin dejarlo siempre encendido | Evidencia C-07 | Equipo | **RESUELTA** en `openspec/changes/base-proyecto-conexion/design.md` (D-4).
| PA-09 | Baja | `GET /duenios/{id}/mascotas` con dueño inexistente → 404: requiere leer el dueño (lectura, no escritura; compatible con la regla de no pre-chequear escrituras) | Ej. 2 | Equipo | **RESUELTA** en `openspec/changes/duenios-fichas/design.md` (D-10: `selectinload` en la consulta del dueño, 404 si no existe y `[]` si no tiene mascotas; aprobada por Matheo el 2026-11-05).
| PA-10 | Baja | `fecha` sin zona horaria en el cuerpo: ¿422 o asumir UTC? | Contrato de turno | Equipo | **RESUELTA** en `openspec/changes/archive/2026-11-08-turnos-composicion/design.md` (D-3: `AwareDatetime`, una fecha sin zona responde 422; aprobada por Uriel el 2026-11-08).
| PA-11 | Baja | Formato del cuerpo de error 409/404 (`{"detail": ...}` por defecto de FastAPI) | Mensajes | Equipo | **RESUELTA** en `openspec/changes/duenios-fichas/design.md` (D-3: `{"detail": "<mensaje>"}` con `HTTPException`; aprobada por Matheo el 2026-11-05).
| PA-12 | Baja | Orden del listado de mascotas (propuesta: por `id`) | Paginación | Equipo | **RESUELTA** en `openspec/changes/archive/2026-11-06-mascotas-paginacion/design.md` (D-2: `ORDER BY id` ascendente, orden total y estable; aprobada por Lautaro el 2026-11-06).
| PA-13 | Baja | ¿`mascota_id` inexistente en `POST /turnos/` → 409? (SU-02) | Turnos | Equipo | **RESUELTA** en `openspec/changes/archive/2026-11-08-turnos-composicion/design.md` (D-2/D-3: 409 `No existe la mascota indicada` por la FK `turno_mascota_id_fkey`; aprobada por Uriel el 2026-11-08).
