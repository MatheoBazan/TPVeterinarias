# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|-------|-------------|-----------------|
| Personal de la veterinaria (recepción) | Quien registra dueños, fichas, mascotas, prácticas y turnos | Consume la API REST (los 17 endpoints) |
| Corrector (stakeholder) | Docente de Programación III que evalúa el TP | Corre `python reiniciar.py` sobre una base vacía y luego los `.http` de `test/`; lee README y evidencia C-07 |
| Equipo de desarrollo | Matheo Bazan, Lautaro Mejias, Uriel Vega | Implementan, prueban (pytest) y entregan |
| Laboratorio (sistema externo simulado) | Provee stock de vacunas | `app/modules/laboratorio/cliente.py` (sincrónico, de la cátedra) |

No hay usuarios finales humanos con cuentas: no existe el concepto de sesión de usuario.

## RBAC — Matriz de permisos

**No aplica.** La autenticación y la autorización están fuera de alcance según la consigna ("No se evalúan: autenticación ni autorización"). No se inventa RBAC: no hay roles, tokens, ni distinción de permisos. Todo actor que alcance la API puede ejecutar cualquier endpoint.

| Rol | Recurso | Permisos |
|-----|---------|----------|
| (único, anónimo) | Todos los recursos de la tabla de endpoints | Los definidos por cada endpoint (ver `02`) |

## Rutas públicas

Todos los endpoints son públicos (porque auth está fuera de alcance):

`/health/live`, `/health/ready`, `/duenios/` (+ `/{id}`, `/{id}/ficha`, `/{id}/mascotas`), `/mascotas/` (+ `/{id}`), `/practicas/`, `/turnos/` (+ `/{id}`), `/laboratorio/stock/{vacuna}`.

**Suposición:** esto es aceptable solo porque es un TP académico; no desplegar en Internet sin autenticación (ver SU-06 en `09`).
