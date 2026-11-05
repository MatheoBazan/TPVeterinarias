# Veterinaria (FastAPI + PostgreSQL) — Base de Conocimiento

Base de conocimiento generada a partir de `docs/MiniTP_Cap1a4_Consigna.pdf` (Programación III, UTN TUP).

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos, alcance y fuera de alcance |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack, arquitectura, integración con laboratorio, 17 endpoints |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Actores; sin auth, todo público |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 6 tablas, relaciones, restricciones, índices, seed |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | RN-01..RN-09 y garantes |
| [06_funcionalidades.md](06_funcionalidades.md) | Épicas y US por ejercicio |
| [07_flujos_principales.md](07_flujos_principales.md) | Arranque, alta de turno, borrados, lecturas, lab |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, estructura de carpetas, env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | DD-xx y SU-xx |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | Inconsistencias y preguntas priorizadas |
| [11_casos_de_prueba_y_evaluacion.md](11_casos_de_prueba_y_evaluacion.md) | C-01..C-09, pesos, entrega |

## Quick Start para Desarrolladores

1. Dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Datos → [04](04_modelo_de_datos.md)
3. Reglas → [05](05_reglas_de_negocio.md)
4. Arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Probar y entregar → [11](11_casos_de_prueba_y_evaluacion.md)
7. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

API asincrónica de veterinaria (dueños, fichas, mascotas, prácticas, turnos) con FastAPI, SQLModel/SQLAlchemy 2.0 async y PostgreSQL 16. La integridad la garantiza la base (FK, UNIQUE, CHECK, ON DELETE) y los services traducen `IntegrityError` a 409; el turno congela precios y se crea todo o nada. Sin auth, repositorios, colas ni Alembic. Dos carpetas de pruebas distintas: `test/` (`.http` de la cátedra) y `tests/` (pytest del equipo).
