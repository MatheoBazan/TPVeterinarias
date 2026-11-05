# Veterinaria (TP Programación III) — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.

API asincrónica para una veterinaria de barrio (dueños, fichas, mascotas, catálogo de prácticas y turnos), trabajo práctico de **Programación III — UTN, Tecnicatura Universitaria en Programación, Unidades 1 a 4**. La fuente de verdad es la consigna [docs/MiniTP_Cap1a4_Consigna.pdf](docs/MiniTP_Cap1a4_Consigna.pdf); ante cualquier duda entre la KB y el PDF, **manda el PDF**.

**Equipo**: Matheo Bazan, Lautaro Mejias, Uriel Vega.

---

## Stack Tecnológico

| Capa | Tecnología | Versión mínima (PDF) | Uso |
|------|------------|----------------------|-----|
| Lenguaje | Python | 3.12 (el equipo usa hasta 3.14) | Lenguaje |
| Framework web | FastAPI | 0.111 | Todos los handlers `async def` |
| Modelos | SQLModel | 0.0.24 | Modelos de tabla y contratos (DTO) |
| ORM / sesión | SQLAlchemy | 2.0, asincrónico | Motor, sesión y carga anticipada |
| Driver | asyncpg | 0.30 | Controlador asincrónico de PostgreSQL |
| Base de datos | PostgreSQL | 16 (Docker `postgres:16`) | Base de datos |
| Config | python-dotenv | 1.0 | Lectura de `.env` (`DATABASE_URL`) |
| Servidor | uvicorn | el que instala `fastapi[standard]` | Servidor ASGI |
| Tests (equipo) | pytest + httpx | — | TDD estricto en `tests/` contra `veterinaria_test` |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

> **No confundir**: `tests/` = suite pytest del equipo. `test/` = archivos `.http` (y el `.sql` del caso C-08) que **exige la consigna** como entregable.

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, objetivos de aprendizaje, alcance y fuera de alcance |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Actores (no hay auth: todos los endpoints son públicos) |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Tablas y columnas obligatorias, restricciones, índices, relaciones, seed |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | RN-01..RN-09 y su garante (base / DTO / HTTP) |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Historias de usuario por ejercicio |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Lifespan, alta de turno todo-o-nada, borrados, eager loading, laboratorio |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Estructura de carpetas, patrones, env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | Decisiones DD-XX y supuestos SU-XX |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Preguntas abiertas PA-XX a resolver en el `design.md` del change que las toca |
| [11_casos_de_prueba_y_evaluacion.md](knowledge-base/11_casos_de_prueba_y_evaluacion.md) | Casos C-01..C-09 de la consigna, criterios de evaluación y formato de entrega |

> ⚠️ Las preguntas de prioridad **Alta** de `10_preguntas_abiertas.md` (PA-01 FK→404 vs UNIQUE→409, PA-02 ON DELETE no especificados, PA-03 seed del ejemplo) se resuelven en el `propose` del change que las toca (C-02 y C-03) y se confirman con el responsable antes del `apply`.

---

## Skills Disponibles

Fuente de verdad: [.atl/skill-registry.md](.atl/skill-registry.md). Las skills de dominio están instaladas **en el proyecto** (`.claude/skills/`, fijadas en `skills-lock.json`), así que todo el grupo las tiene al clonar.

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | Modelos, restricciones, services, routers (C-02..C-06) | `sqlmodel`, `fastapi`, `postgresql-table-design` |
| **Async / Integración** | Lifespan, health, laboratorio sin bloqueos (C-01, C-07) | `fastapi`, `async-python-patterns` |
| **Testing** | TDD estricto con pytest + httpx, casos `.http` | `python-testing-patterns` |
| **Orquestación** | SDD / OPSX | `openspec-explore`, `openspec-propose`, `openspec-apply-change`, `openspec-archive-change`, `openspec-sync-specs`, `openspec-update-change` |

Cargá la skill correspondiente al contexto ANTES de escribir código. Para SQLAlchemy 2.0 async (eager loading, `AsyncSession`) no hay skill confiable: consultar la documentación oficial (context7).

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`). Se versiona en el repo para que todo el grupo use las mismas reglas; regenerarlo con `/active-orchestrator:registry` después de instalar o quitar skills. Esta tabla sólo mapea skill→rol.

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 8 changes en 4 fases.
- **Camino crítico** (5): `C-01 → C-02 → C-03 → C-06 → C-08`.
- **Paralelismo**: C-07 arranca apenas cierra C-01; C-04, C-05 y C-06 arrancan en paralelo cuando cierra C-03.
- **Responsables**: Matheo Bazan → C-01, C-02, C-03. Lautaro Mejias / Uriel Vega → C-04..C-07 (a repartir entre ellos). C-08 compartido.
- **Primer change**: `C-01` (`base-proyecto-conexion`).

> Ojo con los códigos: `C-NN` en `CHANGES.md` es el **ID de change**; los casos de prueba de la consigna se citan como "caso C-NN de la consigna".

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes".

---

## Reglas Duras (específicas del proyecto)

> Reglas **globales** ya definidas en `~/.claude/CLAUDE.md` (orquestador OPSX, governance por dominio, TDD estricto, engram): el proyecto las **hereda**, no se repiten acá. Los integrantes que no tengan ese global igual deben seguir el flujo OPSX y TDD descrito en `CHANGES.md`.

Reglas confirmadas por el equipo. Son contrato; romperlas es un defecto.

### Consigna (lo que se corrige)

1. **Esquema intocable** — NUNCA renombrar ni quitar tablas o columnas de la consigna → sólo se pueden **agregar** columnas. El esquema se crea con `SQLModel.metadata.create_all` desde `reiniciar.py`. NUNCA Alembic, repositorios, Unit of Work, colas de tareas ni autenticación (fuera de alcance del TP).
2. **Async sin bloqueos** — NUNCA un handler con `def` → siempre `async def`. NUNCA una llamada bloqueante dentro del event loop (`time.sleep`, I/O sincrónica, driver sincrónico) → sacarla del loop con `await asyncio.to_thread(...)` / `run_in_threadpool`. NUNCA modificar `app/modules/laboratorio/cliente.py` (lo entrega la cátedra).
3. **La base es el garante** — NUNCA una consulta previa "¿ya existe?" para validar unicidad o claves foráneas → escribir, atrapar `IntegrityError`, hacer `rollback` y responder 409 con mensaje propio. NUNCA borrar en cascada desde el ORM → `ON DELETE CASCADE` / `RESTRICT` en la base y `passive_deletes` en la relación. NUNCA `float` para dinero → `Decimal` (columnas `NUMERIC`).
4. **Lecturas eager** — NUNCA depender de la carga perezosa (en async falla con `MissingGreenlet`) → `joinedload` para relaciones "a uno" y `selectinload` para colecciones, declarados en la misma consulta, con un número fijo de queries (verificable con `echo=True`).

### Capas y contratos

5. **Router delgado** — NUNCA lógica ni queries en `router.py` → el router recibe, delega en `service.py` y declara `status_code` y `response_model`. El service recibe la `AsyncSession` por parámetro.
6. **DTO separados** — NUNCA usar el modelo de tabla como contrato HTTP → `schemas.py` con `Create` / `Update` / `Read`, separado de `models.py`. Los DTO de alta no llevan `id`. El precio de las prácticas y el total NUNCA viajan en el DTO del turno.
7. **`extra='forbid'` en DTOs de entrada** — NUNCA aceptar en silencio campos no declarados → `model_config = ConfigDict(extra="forbid")` en los `Create` / `Update` (un campo extra responde 422).
8. **Estilo Python** — `snake_case`, type hints en todas las firmas, y nombres del dominio en español sin ñ, igual que la consigna (`duenio`, `mascota`, `turno_practica`, `precio_unitario`).

### Tests y entrega

9. **Sin mocks de la base** — NUNCA SQLite ni mocks de la sesión → los tests corren contra PostgreSQL real (`veterinaria_test` en Docker), para que FK, UNIQUE y CHECK se disparen de verdad.
10. **Change completo** — NUNCA archivar un change sin sus tests pytest en `tests/` (verdes) y sus casos `.http` en `test/`, con la respuesta esperada en un comentario. `python reiniciar.py` siempre tiene que funcionar sobre una base vacía (si no, el TP no se corrige).
11. **Sin secretos** — NUNCA credenciales reales en el repo → `.env` en `.gitignore`; `env.example` con la forma del valor y sin secretos (si no, el TP no se corrige).

### Git

12. **Commits sin IA** — NUNCA líneas `Co-Authored-By` de IA ni "Generated with…" en commits o PRs → Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). NUNCA `push` sin confirmación del integrante.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias
3. /opsx:propose <nombre-del-change>             → proposal + design + specs + tasks
4. /opsx:apply <nombre-del-change>               → TDD estricto, cargando skills, respetando las reglas duras
5. /opsx:archive <nombre-del-change> + [x]       → cerrar el change (pytest verde + .http escritos)
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen; ante conflicto con el PDF de la consigna, manda el PDF.
