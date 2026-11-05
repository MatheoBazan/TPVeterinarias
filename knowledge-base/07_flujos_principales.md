# Flujos Principales

## Flujo 1: Arranque y ciclo de vida

**Disparador**: `uvicorn app.main:app` (o `fastapi dev`). **Actor**: operador.

1. `main.py` arranca el `lifespan`: lee `DATABASE_URL` (`core/config.py`, python-dotenv), crea el motor async y la fábrica de sesiones (`expire_on_commit=False`), los guarda en `app.state`.
2. Se registran los routers de los 6 módulos.
3. Al apagar, el `lifespan` hace `engine.dispose()`.
4. Cada petición recibe su sesión por `Depends(get_session)` (una por petición).

El esquema NO se crea en el arranque: lo crea `python reiniciar.py`.

## Flujo 2: Reinicio de la base (`python reiniciar.py`)

**Actor**: equipo / corrector, sobre una base posiblemente vacía.
1. Borra las tablas (`drop_all`). 2. `SQLModel.metadata.create_all`. 3. Carga el seed (ver `04`). Debe funcionar sobre base vacía.

## Flujo 3: Alta de un turno (todo o nada)

**Disparador**: `POST /turnos/`. **Actor**: recepción.

1. Router valida `TurnoCreate` (`mascota_id`, `fecha`, `motivo`, `practicas` con `min_length=1`); lista vacía → 422.
2. Service abre la transacción: lee el precio de cada práctica del catálogo y calcula el total (`Decimal`).
3. Inserta `turno` y sus filas `turno_practica` con `precio_unitario` copiado.
4. `commit`. Si la base rechaza (práctica inexistente → FK, práctica repetida → PK compuesta, mascota inexistente → FK): `IntegrityError` → `rollback` → 409 con mensaje propio; no queda nada guardado.
5. Responde 201 releyendo con carga anticipada (mascota con `joinedload`, prácticas con `selectinload`).

Ejemplo de cuerpo (de la consigna):
```json
{ "mascota_id": 1, "fecha": "2026-11-12T10:30:00-03:00", "motivo": "Control anual",
  "practicas": [ { "practica_id": 1 }, { "practica_id": 3 } ] }
```
Respuesta esperada (el seed debe permitir reproducirla; id 2 porque el seed ya tiene el turno 1):
```json
{ "id": 2, "fecha": "2026-11-12T13:30:00Z", "motivo": "Control anual", "total": "27000.00",
  "mascota": { "id": 1, "nombre": "Toby", "especie": "perro" },
  "practicas": [
    { "practica_id": 1, "nombre": "Consulta", "precio_unitario": "15000.00" },
    { "practica_id": 3, "nombre": "Vacuna antirrábica", "precio_unitario": "12000.00" } ] }
```
Formato: `fecha` en UTC con `Z`; dinero como string con 2 decimales; `practicas` con `practica_id`, `nombre` (del catálogo), `precio_unitario` (de `turno_practica`).

**Casos de error**:
- Práctica inexistente → 409, nada guardado (C-04).
- Práctica repetida en el turno → 409 vía PK compuesta (RN-07).
- Lista vacía → 422 (RN-05).
- Mascota inexistente → 409 (**Suposición**, FK; ver `10`).

## Flujo 4: Alta de mascota y de ficha

- `POST /mascotas/`: recibe `duenio_id`; escribe; FK violada → rollback → 409 (C-04). 201 con `MascotaRead`.
- `POST /duenios/{id}/ficha`: dueño inexistente → 404; segunda ficha → 409 (RN-03). Cómo distinguir FK (404) de UNIQUE (409) sin pre-chequeo: ver `10`.

## Flujo 5: Borrado

- `DELETE /duenios/{id}`: con mascotas → RESTRICT → `IntegrityError` → 409 (RN-08/C-05); sin mascotas (con o sin ficha) → 204 (la ficha cae por CASCADE, DD-05); inexistente → 404.
- `DELETE /turnos/{id}`: 204; la base borra `turno_practica` (CASCADE; `passive_deletes`) (RN-09/C-05); inexistente → 404.

## Flujo 6: Lecturas con carga anticipada

- `GET /turnos/{id}`: `joinedload(Turno.mascota)` + `selectinload(Turno.practicas)` (y la práctica de cada fila para el nombre) en la misma consulta; número fijo de consultas, independiente de la cantidad de prácticas (C-07).
- `GET /duenios/{id}`: `joinedload(Duenio.ficha)` (a-uno). `GET /mascotas/{id}`: `joinedload(Mascota.duenio)`. `GET /duenios/{id}/mascotas`: `selectinload` de la colección.
- Nunca lazy loading (`MissingGreenlet`).

## Flujo 7: Listado paginado

`GET /mascotas/?page=&size=` → cuenta `total`, calcula `pages`, devuelve `{items, total, page, size, pages}`. `size` 1–100 (default 20); `page` > `pages` → 422 salvo la primera página, que siempre responde (valor de `pages` con `total=0`: abierto en `10`).

## Flujo 8: Laboratorio sin bloquear

`GET /laboratorio/stock/{vacuna}` → el handler `async def` delega `consultar_stock(vacuna)` a un hilo (`asyncio.to_thread` / `run_in_threadpool`) → `{"vacuna": ..., "stock": ...}`. Con tres consultas simultáneas, `GET /health/live` responde de inmediato (C-09).

## Flujo 9: Salud

`/health/live`: sin tocar la base → `{"estado": "vivo"}`. `/health/ready`: `SELECT 1`; si falla → 503.
