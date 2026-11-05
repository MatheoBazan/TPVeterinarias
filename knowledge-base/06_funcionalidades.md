# Funcionalidades

Organizadas por épica (alineadas a los Ejercicios 1 a 6 y sus pesos). Actor: "Personal de la veterinaria" salvo indicación. Los criterios son los de la consigna; nada se inventa.

## Épica 1: Proyecto, conexión y ciclo de vida (Ej. 1 — 10 pts)

### US-001 — Motor y sesión por petición
**Como** equipo **quiero** crear el motor asincrónico y la fábrica de sesiones en el `lifespan` **para** tener un recurso por proceso y una sesión por petición.

**Criterios de aceptación**:
- [ ] Motor y fábrica en `app.state`; el motor se cierra al apagar.
- [ ] `get_session` vía `Depends(get_session)`, una sesión por petición, `expire_on_commit=False`.
- [ ] `DATABASE_URL` leída de `.env` (no versionado); `env.example` sin secretos.

### US-002 — Salud del servicio
**Como** operador **quiero** `GET /health/live` y `GET /health/ready` **para** saber si el proceso y la base responden.

**Criterios de aceptación**:
- [ ] `/health/live` no toca la base → 200 `{"estado": "vivo"}`.
- [ ] `/health/ready` ejecuta `SELECT 1`; 200 si responde, 503 si la base no contesta.

## Épica 2: Contratos y CRUD (Ej. 2 — 20 pts)

### US-003 — Alta de dueño
**Criterios**: [ ] `POST /duenios/` → 201 `DuenioRead`; [ ] email repetido → 409 (RN-01); [ ] cuerpo inválido → 422; [ ] `DuenioCreate` sin `id`.
**Reglas**: RN-01.

### US-004 — Detalle, edición parcial y borrado de dueño
**Criterios**: [ ] `GET /duenios/{id}` → dueño con su ficha (200/404/422); [ ] `PATCH` aplica solo campos enviados (`exclude_unset`), 200/404/409/422; [ ] `DELETE` → 204/404/409 (409 si tiene mascotas).
**Reglas**: RN-01, RN-08.

### US-005 — Ficha del dueño
**Criterios**: [ ] `POST /duenios/{id}/ficha` → 201 `FichaRead`; [ ] dueño inexistente → 404; [ ] segunda ficha → 409 (RN-03).
**Reglas**: RN-03.

### US-006 — Mascotas del dueño
**Criterios**: [ ] `GET /duenios/{id}/mascotas` → 200 con las mascotas / 404 si el dueño no existe.

### US-007 — Alta y lectura de mascotas
**Criterios**: [ ] `POST /mascotas/` recibe `duenio_id` existente → 201 `MascotaRead`; dueño inexistente → 409 (C-04); [ ] `GET /mascotas/{id}` → mascota con su dueño (200/404).

### US-008 — Listado paginado de mascotas
**Criterios**: [ ] `GET /mascotas/?page&size` → `{ items, total, page, size, pages }`; [ ] `size` por defecto 20, rango 1–100; [ ] página mayor a `pages` → 422; [ ] la primera página siempre responde, aun sin resultados.

### US-009 — Catálogo de prácticas
**Criterios**: [ ] `POST /practicas/` → 201 `PracticaRead`; nombre repetido → 409 (RN-02); precio ≤ 0 → 422 (RN-04); [ ] `GET /practicas/` → 200 catálogo.
**Reglas**: RN-02, RN-04.

## Épica 3: Modelos, restricciones y relaciones (Ej. 3 — 30 pts)

### US-010 — Esquema completo y `reiniciar.py`
**Criterios**: [ ] 6 tablas con FK y su regla de borrado, UNIQUE, CHECK e índices (ver `04`); [ ] navegación en ambos extremos; [ ] `Turno.practicas` con `passive_deletes`; [ ] `reiniciar.py` deja la base conocida (2 dueños/1 ficha, 3 mascotas, 4 prácticas, 1 turno con 2 prácticas) y reproduce el ejemplo del Ej. 4; [ ] funciona sobre base vacía.

## Épica 4: Altas con relaciones (Ej. 4 — 15 pts)

### US-011 — Reservar un turno con sus prácticas
**Criterios**: [ ] `POST /turnos/` con `mascota_id`, `fecha`, `motivo`, `practicas: [{practica_id}]`; [ ] precio y total no viajan; el servidor copia precios y calcula total; [ ] una sola transacción: práctica inexistente → 409 y nada guardado; [ ] lista vacía → 422 (RN-05); [ ] práctica repetida → 409 (RN-07); [ ] 201 con el formato del ejemplo (ver `07`).

### US-012 — Borrar un turno
**Criterios**: [ ] `DELETE /turnos/{id}` → 204 y sus prácticas desaparecen por CASCADE; 404 si no existe.
**Reglas**: RN-09.

## Épica 5: Lecturas sin N+1 (Ej. 5 — 15 pts)

### US-013 — Detalle de turno y de dueño con carga anticipada
**Criterios**: [ ] `GET /turnos/{id}` con mascota y prácticas en número fijo de consultas; [ ] `GET /duenios/{id}` con ficha en número fijo; [ ] `joinedload` para a-uno, `selectinload` para colecciones, en la misma consulta; [ ] sin lazy loading (falla con `MissingGreenlet`); [ ] evidencia C-07 (echo=True).

## Épica 6: Asincronía sin bloqueos (Ej. 6 — 10 pts)

### US-014 — Stock del laboratorio
**Criterios**: [ ] `GET /laboratorio/stock/{vacuna}` → `{"vacuna": ..., "stock": ...}`; [ ] llama a `consultar_stock` sin modificarla y fuera del bucle de eventos; [ ] con varias consultas en marcha, `GET /health/live` responde de inmediato (C-09).

## Épica 7: Entrega

### US-015 — Paquete de entrega
**Criterios**: [ ] repo con código, `requirements.txt`, `env.example`, `reiniciar.py`, `test/`; [ ] `.env` no subido; [ ] README con pasos desde cero y la explicación del índice de `turno_practica.turno_id`; [ ] evidencia C-07 incluida.
