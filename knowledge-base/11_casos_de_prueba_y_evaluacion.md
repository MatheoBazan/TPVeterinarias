# Casos de Prueba, Evaluación y Entrega

Extra del dominio (consigna): casos de prueba mínimos, criterios de evaluación y formato de entrega.

## Casos de prueba mínimos (C-01..C-09)

Los archivos `.http` de **`test/`** (no `tests/`) demuestran como mínimo estos casos; cada uno indica en un comentario la respuesta esperada y se corre **después de `python reiniciar.py`**. El C-08 va en un archivo `.sql`.

| Caso | Qué se demuestra | Resultado esperado |
|------|------------------|--------------------|
| C-01 | Un parámetro de ruta que no es entero, p. ej. `/duenios/abc` | 422, sin ejecutar el handler |
| C-02 | Email de dueño o nombre de práctica repetido | 409 con mensaje propio |
| C-03 | Segunda ficha para el mismo dueño | 409 |
| C-04 | Mascota con un dueño inexistente, y turno con una práctica inexistente | 409; del turno no queda guardado nada |
| C-05 | Borrar un dueño con mascotas, y borrar un turno | 409 en el primero; 204 en el segundo, y sus prácticas ya no están |
| C-06 | Turno válido con dos prácticas | 201, con los precios copiados y el total calculado |
| C-07 | Detalle de un turno con una práctica y con tres | La misma cantidad de consultas en la consola (`echo=True`) |
| C-08 | Un `UPDATE practica SET precio = 0` ejecutado directo en la base, en un archivo `.sql` | La base lo rechaza por el CHECK |
| C-09 | Tres consultas simultáneas al laboratorio y un `GET /health/live` | El de salud responde de inmediato |

## Criterios de evaluación

| Criterio | Peso | Qué se mira |
|----------|------|-------------|
| Proyecto, conexión y ciclo de vida | 10 % | Estructura, lifespan, `Depends`, `.env` y `env.example` |
| Contratos y CRUD | 20 % | DTO separados, códigos HTTP, PATCH parcial, envoltorio de paginación |
| Modelos, restricciones y relaciones | 30 % | Lado de cada clave foránea, uno a uno con UNIQUE, tabla intermedia con su dato, RESTRICT y CASCADE, CHECK, índices y su justificación, navegación en los dos extremos |
| Altas con relaciones | 15 % | Ids en la agregación y la asociación; prácticas dentro del turno en la composición; todo o nada |
| Lecturas sin N+1 | 15 % | Carga anticipada adecuada a cada relación; número fijo de consultas |
| Asincronía sin bloqueos | 10 % | Handlers asincrónicos; la biblioteca sincrónica fuera del bucle de eventos |

**Condición de corrección**: un proyecto que no levanta, que no crea su esquema con `python reiniciar.py` sobre una base vacía o que tiene credenciales reales en el repositorio no se corrige hasta que se subsane.

## Formato de entrega

- Repositorio con el código fuente completo, `requirements.txt`, `env.example`, `reiniciar.py` y la carpeta `test/`. El `.env` no se sube.
- `README.md` con los pasos para levantar el proyecto desde cero (entorno virtual, dependencias, `.env`, `python reiniciar.py` y arranque del servidor) y con la explicación del índice de `turno_practica.turno_id` (1–2 líneas: es la columna izquierda de la PK compuesta, que ya es un índice B-tree).
- Evidencia del caso C-07: un fragmento de la consola con las consultas del detalle de un turno con una práctica y con tres.

## Mapa caso → regla/ejercicio

| Caso | Reglas | Ejercicio |
|------|--------|-----------|
| C-01 | — | 2 |
| C-02 | RN-01, RN-02 | 2 |
| C-03 | RN-03 | 2/3 |
| C-04 | FK, todo o nada | 4 |
| C-05 | RN-08, RN-09 | 3 |
| C-06 | RN-05, RN-06 | 4 |
| C-07 | — | 5 |
| C-08 | RN-04 (CHECK) | 3 |
| C-09 | — | 6 |
