# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

Project: ProyectoVeterinaria (UTN Programacion III). Backend-only: FastAPI + SQLModel + SQLAlchemy 2.0 async + asyncpg + PostgreSQL 16 + pytest/httpx, strict TDD. No UI.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| FastAPI endpoints, dependencies, Pydantic models, routers | fastapi | .claude/skills/fastapi/SKILL.md |
| SQLModel models, sessions, queries, relationships, create/update/delete | sqlmodel | .claude/skills/sqlmodel/SKILL.md |
| asyncio, async/await, async I/O, concurrency | async-python-patterns | .claude/skills/async-python-patterns/SKILL.md |
| pytest, fixtures, mocking, TDD, test suites | python-testing-patterns | .claude/skills/python-testing-patterns/SKILL.md |
| PostgreSQL schema, types, constraints, indexes | postgresql-table-design | .claude/skills/postgresql-table-design/SKILL.md |
| OpenSpec: explore / propose / apply / archive / sync / update change | openspec-explore, openspec-propose, openspec-apply-change, openspec-archive-change, openspec-sync-specs, openspec-update-change | .claude/skills/openspec-*/SKILL.md |
| Fix bug / small behavior change at narrowest layer | surgical-patch | ~/.claude/skills/surgical-patch/SKILL.md |
| Restructure code preserving behavior | safe-refactor | ~/.claude/skills/safe-refactor/SKILL.md |
| Ambiguous failure, unknown cause | investigate-first | ~/.claude/skills/investigate-first/SKILL.md |
| Validation-only / completion check / gate run | verify-and-stop | ~/.claude/skills/verify-and-stop/SKILL.md |
| New feature work with overbuilding risk | lean-build | ~/.claude/skills/lean-build/SKILL.md |

Not applicable (frontend/design/motion/video/marketing, no UI in this project): animate, animation-vocabulary, apple-design, banner-design, brand, brandkit, design-system, design-taste-frontend, emil-design-eng, find-animation-opportunities, high-end-visual-design, image-to-code, imagegen-frontend-web, impeccable, improve-animations, performance, redesign-existing-projects, remotion-best-practices, slides, ui-styling, ui-ux-pro-max, dataviz. Also skipped: workflow/meta skills (active-orchestrator, kb-creator, roadmap-generator, agent-instruction, find-skill, skill-creator, caveman*, ponytail, graphify, cavecrew).

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### fastapi
- All handlers `async def`. Use `Annotated[T, Depends(...)]` and define reusable aliases (`SessionDep = Annotated[AsyncSession, Depends(get_session)]`). Same for Path/Query.
- No `...` (Ellipsis) as default for required params/fields; no `RootModel`.
- Declare a return type or `response_model` on every endpoint (filters/serializes output); never return table models when a public DTO exists.
- APIRouter owns prefix/tags/dependencies; `include_router` plain. Don't use ORJSONResponse/UJSONResponse (deprecated).
- Run with `fastapi dev` / `fastapi run`; entrypoint in `pyproject.toml` `[tool.fastapi]`.
- Ignore SSE streaming, `app.frontend()`, OpenTelemetry sections: not relevant.
- PROJECT OVERRIDES: engine + session factory are created in the `lifespan` and stored in `app.state`; `get_session` via `Depends` with `expire_on_commit=False`. NO repositories / Unit of Work layer. NO auth/security dependencies. Schema via `SQLModel.metadata.create_all` (no Alembic). Pre-checks "already exists?" are forbidden: write, catch IntegrityError, rollback, return 409.

### sqlmodel
- Import from `sqlmodel` (Field, Relationship, SQLModel, select). Table models: `class X(XBase, table=True)`; DTOs are separate non-table classes: Base / Create / Update (all-optional; `model_dump(exclude_unset=True)` + `sqlmodel_update`) / Public. Never mix request/response-only fields into table models.
- Build rows with `Model.model_validate(create_dto)`. Datetimes: plain `datetime` with aware UTC values (`datetime.now(UTC)`); do not set `DateTime(timezone=True)` manually.
- Relationships via `Relationship(back_populates=...)`; link tables with extra fields are full table models. Keep table models in one module or use `TYPE_CHECKING` + string annotations.
- `ondelete="SET NULL"` needs a nullable FK; cascades via `cascade_delete=True` + `ondelete`.
- Call `create_all` only after all table models are imported.
- PROJECT OVERRIDES (the skill's examples are sync): use `AsyncSession` (`sqlmodel.ext.asyncio.session.AsyncSession`) with `await session.exec(select(...))`, `await session.commit()/refresh()`; engine via `create_async_engine("postgresql+asyncpg://...")`; session factory (`async_sessionmaker` / `sessionmaker(class_=AsyncSession, expire_on_commit=False)`) created in lifespan (the skill's "no sessionmaker" does NOT apply). `create_all` via `async with engine.begin() as conn: await conn.run_sync(SQLModel.metadata.create_all)`. NO lazy loading: use `selectinload` (collections) / `joinedload` (to-one) via `.options(...)`. Money as `Decimal` (`Numeric(p,s)` via `sa_type`). SQLite examples ignored: PostgreSQL 16 only.

### async-python-patterns
- Never forget `await`; never block the loop (no `time.sleep`, sync DB/HTTP in handlers); use `asyncio.sleep` and async drivers.
- `asyncio.gather(..., return_exceptions=True)` for concurrency; `asyncio.timeout`/`wait_for` for timeouts; re-raise `CancelledError` after cleanup.
- Use `async with` / `async for` for resources.
- Tests: pytest-asyncio (or anyio) for coroutine tests.
- PROJECT: an AsyncSession is not concurrency-safe; never `gather` queries on the same session.

### python-testing-patterns
- pytest, AAA structure, names `test_<unit>_<scenario>_<expected>`, one behavior per test, isolated tests (no order dependence).
- Shared fixtures in `conftest.py`; `tests/` with unit/integration split; register markers (`@pytest.mark.integration`).
- `@pytest.mark.parametrize` for triangulation (>= 2 cases per behavior); `pytest.raises` for errors.
- Mock only external boundaries; no tautological assertions.
- PROJECT: integration tests via `httpx.AsyncClient` + `ASGITransport(app=app)` against real PostgreSQL (Docker) with async fixtures; strict TDD (RED -> GREEN -> TRIANGULATE -> REFACTOR). Prefer real DB over mocks for persistence behavior.

### postgresql-table-design
- PK: `BIGINT GENERATED ALWAYS AS IDENTITY` (SQLModel `int | None` autoincrement PK is fine); UUID only if needed.
- `NUMERIC(p,s)` for money, `TIMESTAMPTZ` for times, `TEXT` for strings (CHECK for length); never `money`/`serial`/`timestamp`/`varchar(n)` blindly.
- NOT NULL wherever semantically required; CHECK constraints (e.g. `price >= 0`); UNIQUE constraints enforce uniqueness (relied on by the IntegrityError -> 409 flow).
- Index FK columns manually (Postgres does not); index real query paths only.
- Specify FK `ON DELETE` behavior explicitly.
- PROJECT OVERRIDES: schema is created by `SQLModel.metadata.create_all`, not hand-written DDL or Alembic; express constraints/indexes via SQLModel `Field(index=True, unique=True, sa_type=...)` / `__table_args__` (CheckConstraint, Index). Skip partitioning/JSONB/extension sections.

### openspec-* (explore, propose, apply-change, archive-change, sync-specs, update-change)
- Always run `openspec status --change "<name>" --json` / `openspec list --json` first; the CLI owns state.
- explore = thinking only, no code. propose = proposal/design/specs/tasks via `openspec instructions <artifact>`. apply = implement tasks from `tasks.md`, mark `[x]`, pause on blockers. archive = sync delta specs then move to `openspec/changes/archive/YYYY-MM-DD-<name>/`. update-change = revise artifacts only, never code.
- Never create `openspec/` structure manually.
- PROJECT: apply runs under strict TDD (see python-testing-patterns).

### surgical-patch
- Fix at the narrowest responsible layer; add regression test first; leave surrounding behavior untouched.

### safe-refactor
- Run tests before and after each structural edit; behavior must not change; no mixing feature + refactor.

### investigate-first
- For unknown causes: gather evidence and rank hypotheses before editing code.

### verify-and-stop
- Validation-only: run the gates, report proof, do not expand scope or fix unrelated things.

### lean-build
- Reuse what exists, keep scope strict, define a stop condition; no speculative abstractions (consistent with: no repositories/UoW).

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| Architecture | knowledge-base/08_arquitectura_propuesta.md | Proposed architecture (CLAUDE.md not generated yet) |
| Decisions | knowledge-base/09_decisiones_y_supuestos.md | Decisions and assumptions |
| Business rules | knowledge-base/05_reglas_de_negocio.md | |
| Data model | knowledge-base/04_modelo_de_datos.md | |
| Test cases | knowledge-base/11_casos_de_prueba_y_evaluacion.md | |
| Roadmap | CHANGES.md | Operational index of changes C-01..C-08 |

Read the convention files listed above for project-specific patterns and rules.
