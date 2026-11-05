# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Veterinaria** (Programación III, UTN — FastAPI + PostgreSQL).
> Cada change es atómico: un agente/persona puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

> **Atención con los códigos.** `C-NN` en este documento es el **ID de change**. Los casos de prueba de la consigna
> (`C-01..C-09`, ver `knowledge-base/11_casos_de_prueba_y_evaluacion.md`) se citan siempre como **"caso C-NN de la consigna"**
> o **"caso-NN"** para no confundirlos. Las reglas son `RN-01..RN-09`; las preguntas abiertas `PA-01..PA-13`.

**Equipo**: Matheo Bazan, Lautaro Mejias, Uriel Vega.
**Fuente de verdad**: `docs/MiniTP_Cap1a4_Consigna.pdf`, destilada en `knowledge-base/`.

## Resumen

| Change | Nombre | Ejercicio / Peso | Responsable | Depende de | Governance |
|--------|--------|------------------|-------------|------------|------------|
| C-01 | `base-proyecto-conexion` | Ej. 1 / 10 % | Matheo Bazan | — | MEDIO |
| C-02 | `modelos-esquema-seed` | Ej. 3 / 30 % | Matheo Bazan | C-01 | ALTO (MEDIO-ALTO) |
| C-03 | `duenios-fichas` | Ej. 2 + Ej. 5 (detalle dueño) / parte de 20 % y 15 % | Matheo Bazan | C-02 | MEDIO |
| C-04 | `mascotas-paginacion` | Ej. 2 + 4 + 5 / parte de 20 %, 15 %, 15 % | Lautaro Mejias / Uriel Vega — a repartir | C-03 | MEDIO |
| C-05 | `practicas-catalogo` | Ej. 2 / parte de 20 % | Lautaro Mejias / Uriel Vega — a repartir | C-03 | BAJO |
| C-06 | `turnos-composicion` | Ej. 4 + 5 / 15 % + parte de 15 % | Lautaro Mejias / Uriel Vega — a repartir | C-02, C-03 (recomendado antes: C-05) | MEDIO |
| C-07 | `laboratorio-async` | Ej. 6 / 10 % | Lautaro Mejias / Uriel Vega — a repartir | C-01 | MEDIO |
| C-08 | `entrega-final` | Entrega (checklist de los 6 criterios 10/20/30/15/15/10) | Compartido (los tres); coordina quien termine último | C-01..C-07 | BAJO |

Criterios de evaluación (pesos): Proyecto/conexión/ciclo de vida 10 % · Contratos y CRUD 20 % · Modelos/restricciones/relaciones 30 % · Altas con relaciones 15 % · Lecturas sin N+1 15 % · Asincronía sin bloqueos 10 %.

---

## Cómo usar este documento

1. Identificá el change que te toca (columna Responsable) y verificá que sus **Dependencias** estén archivadas (`[x]`).
2. Leé los archivos de **"Leer antes"** de ese change en `knowledge-base/` (son el contrato; el PDF manda si hay duda).
3. Corré `/opsx:propose <nombre-del-change>` (nombre kebab-case exacto de este documento) y luego `/opsx:apply <nombre-del-change>`.
4. Con `pytest` en verde y los `.http` del change escritos, corré `/opsx:archive <nombre-del-change>`.
5. Marcá el checkbox **Estado** del change (`[ ]` → `[x]`) en este archivo.

---

## Cómo trabajar un change

Guía rápida para el equipo:

- **Ver dónde estamos**: `openspec list` (changes activos) y `openspec status --change "<nombre>"`.
- **Crear el change**: `/opsx:propose <nombre>` (genera proposal, design, tasks y delta specs en `openspec/changes/<nombre>/`).
- **Implementar**: `/opsx:apply <nombre>` (TDD estricto: test en rojo, código mínimo, triangular, refactor).
- **Cerrar**: `/opsx:archive <nombre>` (sincroniza specs y archiva). Solo con `pytest` en verde.
- **Git (sugerido, no obligatorio)**: una rama por change, `feat/<nombre>` (p. ej. `feat/duenios-fichas`), para que Lautaro y Uriel no se pisen al trabajar en paralelo.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), **sin líneas de co-autor de IA**.
- **Antes de archivar**: `pytest` verde, `.http` del change agregados en `test/`, sin `.env` ni credenciales reales en el repo.
- **Dudas de dominio**: revisar `knowledge-base/10_preguntas_abiertas.md`; si la pregunta no está resuelta, decidirla en el `design.md` del change y anotarla.

---

## Árbol de dependencias

```
C-01 base-proyecto-conexion                      [Matheo]
 ├── C-07 laboratorio-async                      [Lautaro/Uriel]   (solo depende de C-01)
 │
 └── C-02 modelos-esquema-seed                   [Matheo]
      └── C-03 duenios-fichas                    [Matheo]          (patrón de referencia)
           ├── C-04 mascotas-paginacion          [Lautaro/Uriel]
           ├── C-05 practicas-catalogo           [Lautaro/Uriel]
           │     ·· (recomendado antes de C-06; no estricto: el seed carga prácticas)
           └── C-06 turnos-composicion           [Lautaro/Uriel]   (también depende de C-02)

C-08 entrega-final  ←  C-01 .. C-07 (todos)      [los tres]
```

### Paralelismo por fase

```
GATE 0: (inicio)
  → C-01 base-proyecto-conexion        [Matheo]            (nada paralelo: todo depende de él)

GATE 1: C-01 ✓                          ← FORK
  → C-02 modelos-esquema-seed          [Matheo]            (camino crítico)
  → C-07 laboratorio-async             [Lautaro o Uriel]   (independiente del modelo de datos)

GATE 2: C-02 ✓
  → C-03 duenios-fichas                [Matheo]            (camino crítico; fija el patrón)
  (C-07 puede seguir en curso)

GATE 3: C-03 ✓                          ← FORK
  → C-04 mascotas-paginacion           [Lautaro o Uriel]
  → C-05 practicas-catalogo            [Lautaro o Uriel]
  → C-06 turnos-composicion            [Lautaro o Uriel]   (el más pesado; recomendado tener C-05 antes, o seed)
  (Matheo queda libre: revisa PRs, arranca el borrador de README/`test/` de C-08)

GATE 4: C-01..C-07 ✓
  → C-08 entrega-final                 [Matheo + Lautaro + Uriel]
```

### Camino crítico (5 changes — mínimo irreducible)

`C-01 → C-02 → C-03 → C-06 → C-08`

C-04, C-05 y C-07 quedan fuera del camino crítico estricto, pero son necesarios para el 100 % de la nota (C-08 los exige).

### Plan óptimo con 3 personas

El reparto entre Lautaro y Uriel de los changes restantes **no está decidido**; la tabla sólo muestra una distribución posible de carga (Persona B / Persona C son intercambiables).

| Paso | Matheo (dueño C-01..C-03) | Persona B (Lautaro/Uriel) | Persona C (Lautaro/Uriel) |
|------|---------------------------|---------------------------|---------------------------|
| 1 | C-01 base-proyecto-conexion | — (lee KB, prepara) | — (lee KB, prepara) |
| 2 | C-02 modelos-esquema-seed | C-07 laboratorio-async | — (revisa modelo propuesto en C-02) |
| 3 | C-03 duenios-fichas | C-07 (cierre) | — / ayuda a revisar |
| 4 | Revisión + borrador README y `test/` | C-06 turnos-composicion | C-05 practicas-catalogo → C-04 mascotas-paginacion |
| 5 | C-08 (README, `.http` consolidados) | C-06 (cierre) + C-08 | C-04 (cierre) + C-08 |
| 6 | C-08 pasada final del checklist (coordina quien termine último) | C-08 | C-08 |

---

## FASE 1 — Fundación (Ej. 1, 10 %)

### [C-01] `base-proyecto-conexion`
- **Estado**: `[ ]` pendiente
- **Responsable**: Matheo Bazan
- **Ejercicio / peso**: Ej. 1 — Proyecto, conexión y ciclo de vida (10 %)
- **Scope**:
  - Estructura `app/main.py`, `app/core/config.py` (`DATABASE_URL` desde entorno con `python-dotenv`), `app/core/database.py`
  - Engine async + session factory **creados en el lifespan**, guardados en `app.state`; `engine.dispose()` al apagar; dependencia `get_session` (una sesión por request, `expire_on_commit=False`)
  - Módulo `health`: `GET /health/live` (sin base) y `GET /health/ready` (`SELECT 1`; **503** si la base no responde) — PA-06 (cuerpo exacto) se decide en el design
  - `requirements.txt`, `requirements-dev.txt` (pytest, httpx), `env.example`, `.gitignore` (excluye `.env`) — PA-04 (versiones/Python) se decide acá
  - `docker-compose.yml` con `postgres:16`: base de desarrollo y base de test (`veterinaria_test`)
  - Infraestructura pytest: `tests/conftest.py` contra `veterinaria_test`
  - Primer archivo `.http` en `test/` (health)
  - Esqueleto del `README.md` con los pasos desde cero
  - NO incluye esqueleto vacío de los demás módulos: cada módulo lo crea su propio change
  - Tests: live sin DB, ready OK y ready 503, lifespan crea/dispone el engine, una sesión por request
- **Dependencias**: ninguna
- **Governance**: MEDIO (infraestructura base; define el ciclo de vida del que cuelga todo)
- **Reglas / casos cubiertos**: sin RN; base para el caso C-01 de la consigna (422 de ruta no entera se cierra en C-03)
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` (lifespan, sesión por request, estructura)
  - `knowledge-base/02_descripcion_general.md` (stack y alcance)
  - `knowledge-base/09_decisiones_y_supuestos.md`
  - `knowledge-base/10_preguntas_abiertas.md` §PA-04, PA-06

---

## FASE 2 — Esquema de datos (Ej. 3, 30 %)

> Parte del 30 % que más pesa en la nota y de la que todos dependen: revisión cruzada obligatoria del equipo antes de archivar.

### [C-02] `modelos-esquema-seed`
- **Estado**: `[ ]` pendiente
- **Responsable**: Matheo Bazan
- **Ejercicio / peso**: Ej. 3 — Modelos, restricciones y relaciones (30 %)
- **Scope**:
  - Modelos de las **6 tablas** en sus módulos: `duenios` (Duenio + FichaDuenio), `mascotas`, `practicas`, `turnos` (Turno + TurnoPractica)
  - Restricciones: FK con regla ON DELETE (RN-08 RESTRICT dueño→mascota, RN-09 CASCADE turno→turno_practica), UNIQUE (RN-01 email, RN-02 nombre práctica, RN-03 `ficha_duenio.duenio_id`), CHECK (RN-04 `precio > 0`, `total >= 0`, `precio_unitario > 0`), PK compuesta de `turno_practica` (RN-07), índices con justificación
  - Navegación en ambos extremos con `back_populates`; `Duenio.ficha` con `uselist=False`; `Turno.practicas` con `passive_deletes`
  - `reiniciar.py` en la raíz: `drop_all` + `create_all` + seed que reproduce el ejemplo del Ej. 4
  - Archivo `.sql` del caso C-08 de la consigna: `UPDATE practica SET precio = 0` rechazado por el CHECK
  - README: explicación (1–2 líneas) de por qué `turno_practica.turno_id` no lleva índice propio (columna izquierda de la PK compuesta, ya es B-tree)
  - Resuelve **PA-02** (ON DELETE de ficha, `turno.mascota_id`, `turno_practica.practica_id`) y **PA-03** (seed exacto)
  - Tests: constraints rechazadas por la base (UNIQUE, CHECK, FK, RESTRICT, CASCADE), `reiniciar.py` sobre base vacía
- **Dependencias**: `C-01`
- **Governance**: ALTO (MEDIO-ALTO): define el esquema del que dependen todos los demás changes; cambios posteriores son costosos. Proponer el design y esperar revisión de los otros dos antes de `apply`.
- **Reglas / casos cubiertos**: RN-01, RN-02, RN-03, RN-04, RN-07, RN-08, RN-09 (garantes en base); caso C-08 de la consigna
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` (completo)
  - `knowledge-base/05_reglas_de_negocio.md` (matriz regla → garante)
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-05/06/07
  - `knowledge-base/10_preguntas_abiertas.md` §PA-02, PA-03
  - `knowledge-base/11_casos_de_prueba_y_evaluacion.md` (caso C-08)

---

## FASE 3 — Patrón de referencia y recursos (Ej. 2, 4, 5)

### [C-03] `duenios-fichas`
- **Estado**: `[ ]` pendiente
- **Responsable**: Matheo Bazan
- **Ejercicio / peso**: Ej. 2 (Contratos y CRUD, 20 %) + Ej. 5 para el detalle del dueño (Lecturas sin N+1, 15 %)
- **Scope**:
  - DTOs: `DuenioCreate`, `DuenioUpdate`, `DuenioRead`, `FichaCreate`, `FichaRead`
  - Service + router de `duenios` (todos los handlers `async`)
  - `POST /duenios/` (201; email duplicado → 409)
  - `GET /duenios/{id}` con ficha (eager loading, número fijo de consultas)
  - `PATCH /duenios/{id}` (`exclude_unset`)
  - `DELETE /duenios/{id}` (204 / 404 / **409** RESTRICT)
  - `POST /duenios/{id}/ficha` (201 / 404 / 409)
  - `GET /duenios/{id}/mascotas` (200 / 404)
  - `IntegrityError` → rollback → 409 con mensaje propio, **sin pre-chequeos**
  - **Establece el patrón de referencia** (router / service / schemas + helper de traducción de `IntegrityError`) que reutilizan C-04, C-05 y C-06
  - Resuelve **PA-01** (FK vs UNIQUE vía `sqlstate`/`constraint_name`), **PA-09**, **PA-11**
  - `.http`: casos C-01 (ruta no entera → 422), C-02 (email), C-03 (segunda ficha), C-05 primera parte (borrar dueño con mascotas → 409) de la consigna
  - Tests: cada código HTTP, PATCH parcial, conteo de consultas del detalle
- **Dependencias**: `C-02`
- **Governance**: MEDIO (lógica de negocio + patrón que se replica; revisar con cuidado antes de que otros lo copien)
- **Reglas / casos cubiertos**: RN-01, RN-03, RN-08; casos C-01, C-02 (email), C-03, C-05 (primera parte) de la consigna
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` (dueños y fichas)
  - `knowledge-base/05_reglas_de_negocio.md` §Dueños y fichas, §Excepciones globales
  - `knowledge-base/07_flujos_principales.md`
  - `knowledge-base/08_arquitectura_propuesta.md` (capas y manejo de errores)
  - `knowledge-base/10_preguntas_abiertas.md` §PA-01, PA-09, PA-11

### [C-04] `mascotas-paginacion`
- **Estado**: `[ ]` pendiente
- **Responsable**: Lautaro Mejias / Uriel Vega — a repartir entre ellos
- **Ejercicio / peso**: Ej. 2 + Ej. 4 + Ej. 5 (alta con relación, paginación, lectura sin N+1)
- **Scope**:
  - `POST /mascotas/` (el `duenio_id` viaja como id; dueño inexistente → **409** por FK)
  - `GET /mascotas/` con envoltorio `{items, total, page, size, pages}`; `size` 20 por defecto, rango 1..100; página más allá de `pages` → 422; la primera página siempre responde
  - `GET /mascotas/{id}` con su dueño (`joinedload`)
  - Reutiliza el patrón de C-03; necesita `Duenio`
  - Resuelve **PA-05** (`pages` con `total = 0`, regla de página fuera de rango) y **PA-12** (orden por `id`)
  - `.http`: caso C-04 primera parte de la consigna (mascota con dueño inexistente → 409)
  - Tests: paginación (vacía, en el borde, fuera de rango, `size` inválido), 409 por FK, número fijo de consultas
- **Dependencias**: `C-03`
- **Governance**: MEDIO (lógica de paginación y altas con relación)
- **Reglas / casos cubiertos**: FK de mascota (regla derivada); caso C-04 (primera parte) de la consigna
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` (mascotas)
  - `knowledge-base/05_reglas_de_negocio.md` §Reglas derivadas
  - `knowledge-base/04_modelo_de_datos.md` §mascota
  - `knowledge-base/10_preguntas_abiertas.md` §PA-05, PA-12

### [C-05] `practicas-catalogo`
- **Estado**: `[ ]` pendiente
- **Responsable**: Lautaro Mejias / Uriel Vega — a repartir entre ellos
- **Ejercicio / peso**: Ej. 2 (Contratos y CRUD, 20 %)
- **Scope**:
  - `POST /practicas/` (`precio > 0` en el DTO con `Decimal` → 422; `nombre` UNIQUE → 409)
  - `GET /practicas/`
  - `.http`: caso C-02 de la consigna (nombre de práctica repetido) y las notas de ejecución del caso C-08 (`.sql`)
  - Tests: 201, 409 por nombre duplicado, 422 por precio ≤ 0, `Decimal` serializado como string
- **Dependencias**: `C-03` (patrón). Recomendado antes de C-06 (no estricto: el seed ya carga prácticas).
- **Governance**: BAJO (CRUD simple sobre el patrón ya establecido)
- **Reglas / casos cubiertos**: RN-02, RN-04; caso C-02 (práctica) y runner del caso C-08 de la consigna
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` (prácticas)
  - `knowledge-base/05_reglas_de_negocio.md` §Catálogo de prácticas
  - `knowledge-base/04_modelo_de_datos.md` §practica

### [C-06] `turnos-composicion`
- **Estado**: `[ ]` pendiente
- **Responsable**: Lautaro Mejias / Uriel Vega — a repartir entre ellos
- **Ejercicio / peso**: Ej. 4 (Altas con relaciones, 15 %) + Ej. 5 (Lecturas sin N+1, 15 %). El change más pesado.
- **Scope**:
  - `POST /turnos/` con `practicas` anidadas (`min_length=1` → 422); el precio se copia del catálogo a `turno_practica.precio_unitario`; el total lo calcula el servidor (ni precio ni total viajan en el DTO)
  - **Una sola transacción, todo o nada**: práctica inexistente → 409 y no queda guardado nada; práctica repetida → 409 por PK compuesta (no rechazar en el DTO)
  - `GET /turnos/{id}`: `joinedload` de mascota + `selectinload` de prácticas, número fijo de consultas
  - `DELETE /turnos/{id}` (204 / 404, borrado en cascada por la base)
  - Formato de respuesta **exactamente** como el ejemplo del PDF (UTC con `Z`, dinero como string)
  - Resuelve **PA-10** (`fecha` sin zona horaria) y **PA-13** (`mascota_id` inexistente → 409); PA-08 (`SQL_ECHO`) se decide acá o en C-08
  - `.http`: caso C-04 segunda parte (turno con práctica inexistente → 409 y nada guardado), C-05 segunda parte (borrar turno → 204 y sus prácticas ya no están), C-06 (turno con dos prácticas), C-07 (detalle con una y con tres prácticas) + evidencia de consola (`echo=True`)
  - Tests: atomicidad (rollback completo), precio congelado ante cambio de catálogo por SQL, duplicado, cascada, conteo de consultas con 1 y 3 prácticas
- **Dependencias**: `C-02`, `C-03` (patrón). Recomendado antes: `C-05`.
- **Governance**: MEDIO (transaccionalidad, precio congelado, N+1; el change con más reglas de negocio)
- **Reglas / casos cubiertos**: RN-05, RN-06, RN-07, RN-09; casos C-04 (segunda parte), C-05 (segunda parte), C-06, C-07 de la consigna
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` (reserva de turno)
  - `knowledge-base/05_reglas_de_negocio.md` §Turnos
  - `knowledge-base/04_modelo_de_datos.md` §turno, §turno_practica
  - `knowledge-base/06_funcionalidades.md` (turnos)
  - `knowledge-base/10_preguntas_abiertas.md` §PA-08, PA-10, PA-13

### [C-07] `laboratorio-async`
- **Estado**: `[ ]` pendiente
- **Responsable**: Lautaro Mejias / Uriel Vega — a repartir entre ellos
- **Ejercicio / peso**: Ej. 6 — Asincronía sin bloqueos (10 %)
- **Scope**:
  - `app/modules/laboratorio/cliente.py` **exactamente como lo entrega la cátedra (sin modificar)**
  - `GET /laboratorio/stock/{vacuna}` que llama a la biblioteca sincrónica **fuera del bucle de eventos** (threadpool: `run_in_threadpool` / `asyncio.to_thread`)
  - Test que demuestra que `/health/live` responde de inmediato mientras hay 3 llamadas al laboratorio en vuelo
  - `.http`: caso C-09 de la consigna
  - Puede arrancar apenas termina C-01, en paralelo con C-02 (no toca la base)
- **Dependencias**: `C-01`
- **Governance**: MEDIO (concurrencia; un bloqueo del event loop es un error sutil)
- **Reglas / casos cubiertos**: caso C-09 de la consigna
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` (asincronía)
  - `knowledge-base/06_funcionalidades.md` (laboratorio)
  - `knowledge-base/11_casos_de_prueba_y_evaluacion.md` (caso C-09)
  - `knowledge-base/02_descripcion_general.md`

---

## FASE 4 — Entrega

### [C-08] `entrega-final`
- **Estado**: `[ ]` pendiente
- **Responsable**: Compartido (Matheo Bazan, Lautaro Mejias, Uriel Vega); coordina quien termine último
- **Ejercicio / peso**: Entrega — checklist de los 6 criterios (10 / 20 / 30 / 15 / 15 / 10)
- **Scope**:
  - `README.md` final desde cero: venv, dependencias, `.env` (desde `env.example`), `docker compose up`, `python reiniciar.py`, arranque del servidor, cómo correr `pytest` y los `.http`, explicación del índice de `turno_practica.turno_id`
  - Consolidación de `test/*.http` cubriendo los casos C-01..C-09 de la consigna **en orden**, corriendo después de `python reiniciar.py` (PA-07: aclarar si se exige reiniciar entre casos)
  - Archivo de evidencia del caso C-07 (fragmento de consola con las consultas del detalle de un turno con una y con tres prácticas)
  - Pasada final por el checklist de criterios de evaluación (pesos 10/20/30/15/15/10)
  - Verificar las condiciones de "no se corrige si…": el proyecto levanta, el esquema se crea con `python reiniciar.py` sobre base vacía, **sin credenciales reales en el repo** (`.env` excluido, sólo `env.example`)
  - Tests: suite completa en verde sobre base limpia
- **Dependencias**: `C-01, C-02, C-03, C-04, C-05, C-06, C-07`
- **Governance**: BAJO (documentación y verificación; sin lógica nueva), con vigilancia sobre credenciales
- **Reglas / casos cubiertos**: casos C-01..C-09 de la consigna; todos los RN como verificación final
- **Leer antes**:
  - `knowledge-base/11_casos_de_prueba_y_evaluacion.md` (completo)
  - `knowledge-base/01_vision_y_objetivos.md`
  - `knowledge-base/10_preguntas_abiertas.md` §PA-07, PA-08
  - `docs/MiniTP_Cap1a4_Consigna.pdf` (formato de entrega)

---

## Tabla resumen y primer change

| Fase | Changes | Nota |
|------|---------|------|
| 1 Fundación | C-01 | Primero, bloquea todo |
| 2 Esquema | C-02 | 30 % de la nota; revisión cruzada |
| 3 Recursos | C-03, C-04, C-05, C-06, C-07 | C-03 fija el patrón; C-04/05/06 en paralelo tras C-03; C-07 desde C-01 |
| 4 Entrega | C-08 | Todos |

**Primer change recomendado**: `C-01` (`base-proyecto-conexion`) → `/opsx:propose base-proyecto-conexion`
