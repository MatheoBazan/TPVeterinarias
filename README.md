# Veterinaria — API con FastAPI y PostgreSQL

Trabajo práctico de Programación III (UTN, Tecnicatura Universitaria en Programación, unidades 1 a 4).
Equipo: Matheo Bazan, Lautaro Mejias, Uriel Vega.

## Requisitos

- Python 3.12, 3.13 o 3.14
- Docker (para PostgreSQL 16)

## Puesta en marcha desde cero

1. Entorno virtual y dependencias:

   ```powershell
   py -3.14 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt   # o requirements.txt si sólo vas a correr la API
   ```

   En bash: `python -m venv .venv && source .venv/bin/activate` (en Git Bash de Windows: `source .venv/Scripts/activate`).

2. Configuración: copiá `env.example` a `.env` y reemplazá `<usuario>` y `<clave>` en las tres líneas que los usan.
   El `.env` no se versiona. Si la clave tiene `@`, `:`, `/` o `#`, codificala en URL o elegí otra.
3. Base de datos: `docker compose up -d` (esperá a que quede sana con `docker compose ps`).
4. Esquema y datos de ejemplo: `python reiniciar.py` — disponible desde C-02 `modelos-esquema-seed`.
5. Servidor: `uvicorn app.main:app --reload` (o `fastapi dev app/main.py`). Documentación en `http://localhost:8000/docs`.
6. Tests: `pytest` (necesita la base levantada; `pytest -m "not integracion"` corre sólo los que no la usan).

## Variables de entorno

| Variable | Para qué | Ejemplo |
|----------|----------|---------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Usuario y clave del contenedor (obligatorias) | `<usuario>` / `<clave>` |
| `POSTGRES_DB` | Base de desarrollo | `veterinaria` |
| `POSTGRES_PORT` | Puerto del host (por defecto 5433) | `5433` |
| `DATABASE_URL` | Base que usa la API | `postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria` |
| `TEST_DATABASE_URL` | Base de la suite pytest; el nombre debe terminar en `_test` | `postgresql+asyncpg://<usuario>:<clave>@localhost:5433/veterinaria_test` |
| `SQL_ECHO` | `1` o `true`: imprime cada sentencia SQL | `0` |

## Puerto 5433

PostgreSQL se publica en el puerto 5433 del host porque el 5432 suele estar ocupado por un PostgreSQL local.
Para cambiarlo, modificá `POSTGRES_PORT` y el puerto de las dos URLs en tu `.env`.

## Base de test con un volumen preexistente

`veterinaria_test` la crea `docker/initdb/01-crear-base-test.sql`, que sólo corre con el volumen vacío.
Si ya tenías el volumen, creala a mano (`docker compose exec db createdb -U <usuario> veterinaria_test`)
o recreá todo (`docker compose down -v && docker compose up -d`, borra los datos).

## `tests/` y `test/`

- `tests/`: suite pytest del equipo (TDD estricto, contra PostgreSQL real).
- `test/`: archivos `.http` (y el `.sql` del caso C-08) que exige la consigna, con la respuesta esperada en un comentario.

## Evidencia con `SQL_ECHO=1`

Con `SQL_ECHO=1` en el `.env` (o en la sesión de la terminal) y `uvicorn app.main:app`, la consola muestra cada sentencia SQL.

## Índice de `turno_practica.turno_id`

Se completa en C-02 (`modelos-esquema-seed`).

## Evidencia del caso C-07

Se completa en C-06.
