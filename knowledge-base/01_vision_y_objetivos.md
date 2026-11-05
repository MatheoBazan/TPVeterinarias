# Visión y Objetivos

Fuente: `docs/MiniTP_Cap1a4_Consigna.pdf` (Programación III, Tecnicatura Universitaria en Programación, UTN; "Unidad 1 a 4 — Del objeto a la persistencia"). La KB es fiel a la letra de la consigna; lo inferido se marca como **Suposición** en `09` y lo no resuelto vive en `10`.

## Propósito del sistema

API asincrónica (FastAPI + PostgreSQL) para que una veterinaria de barrio registre a sus clientes (dueños), sus mascotas y los turnos de atención.

Contexto de negocio (consigna):
- Cada dueño puede cargar una **ficha** con teléfono y dirección.
- Cada mascota figura a nombre de un dueño.
- Cada turno es de una mascota y se reserva con las **prácticas** que se van a hacer (consulta, vacuna, desparasitación).
- La veterinaria mantiene un **catálogo de prácticas** con su precio. Al reservar un turno el precio de cada práctica se **congela** en el turno: si el catálogo cambia después, los turnos ya reservados no cambian.

Contexto académico: es un trabajo práctico breve que integra los capítulos 1 a 4 (fundamentos de FastAPI, contratos y CRUD, ejecución asincrónica sin bloqueos, persistencia relacional con SQLModel y PostgreSQL). El producto es a la vez el entregable evaluado.

## Objetivos de aprendizaje (lo que el proyecto debe demostrar)

1. Construir una API asincrónica con parámetros tipados, dependencias con `Depends()` y el motor de la base creado en el ciclo de vida de la aplicación.
2. Separar modelos de tabla de los contratos de entrada/salida y responder con los códigos HTTP correctos.
3. Traducir al esquema relacional un uno a uno, una agregación, una asociación, una composición y un muchos a muchos con datos propios, justificando de qué lado va cada clave foránea.
4. Leer las relaciones con carga anticipada, sin N+1 ni dependencia de la carga perezosa.
5. Delegar en la base las garantías que la base puede dar: claves foráneas, unicidad y comprobaciones.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|-------|--------------------|-----------------------|
| Personal de la veterinaria (recepción) | Registrar dueños, mascotas y turnos con sus prácticas | Consultar el catálogo, ver el detalle de un turno, consultar stock de vacunas del laboratorio |
| Corrector (stakeholder académico) | Verificar el cumplimiento corriendo `python reiniciar.py` y los archivos `.http` de `test/` | Revisar README, restricciones en la base, evidencia C-07 |
| Equipo (Matheo Bazan, Lautaro Mejias, Uriel Vega) | Entregar el TP aprobado aplicando OPSX/SDD con TDD estricto | Mantener repo privado limpio, sin credenciales |

Ver `03_actores_y_roles.md`.

## Alcance

- 6 módulos mínimos: `health`, `duenios`, `mascotas`, `practicas`, `turnos`, `laboratorio` (`FichaDuenio` vive en `duenios`, `TurnoPractica` en `turnos`).
- CRUD parcial según la tabla de endpoints de referencia (ver `02`, `06`).
- 6 tablas: `duenio`, `ficha_duenio`, `mascota`, `practica`, `turno`, `turno_practica`.
- Reglas RN-01 a RN-09 garantizadas por la base (ver `05`).
- Script `reiniciar.py` que borra tablas, las crea con `SQLModel.metadata.create_all` y carga datos iniciales.
- Casos de prueba C-01 a C-09 en archivos `.http` (+ un `.sql`) dentro de `test/` (ver `11`).
- Entregables: repo con código, `requirements.txt`, `env.example`, `reiniciar.py`, `test/`, README y evidencia C-07.

## Fuera de alcance (explícito en la consigna: "Qué queda afuera")

- Autenticación y autorización.
- Repositorios y Unit of Work.
- Colas de tareas.
- Migraciones con Alembic (el esquema se crea con `SQLModel.metadata.create_all`).

Además, por inferencia de los endpoints listados: no hay endpoints de borrado/edición de mascotas ni de prácticas (ver `10`).

## Métricas de éxito (criterios de evaluación)

Pesos 10/20/30/15/15/10 sobre 100; detalle en `11_casos_de_prueba_y_evaluacion.md`. Condición previa: un proyecto que no levanta, que no crea su esquema con `python reiniciar.py` sobre una base vacía o que tiene credenciales reales en el repo no se corrige hasta que se subsane.
