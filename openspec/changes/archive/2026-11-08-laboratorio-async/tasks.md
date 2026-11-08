# Tasks — laboratorio-async (C-07)

> **TDD estricto**: cada grupo sigue RED → GREEN → TRIANGULATE → REFACTOR y corre `pytest` en cada paso. Si un test pasa de entrada, romper temporalmente la propiedad (mutación), ver el rojo y anotarlo. Las pruebas usan `client` (lifespan real) pero no tocan la base.
>
> **Entregable en `test/`**: `test/laboratorio.http` (grupo 3).

## 1. Biblioteca de la cátedra y consulta de stock (D-1, D-2, D-3)

- [x] 1.1 RED: `tests/test_laboratorio.py::test_cliente_es_el_de_la_catedra` (el contenido de `app/modules/laboratorio/cliente.py` es exactamente el texto del enunciado) → falla (no existe)
- [x] 1.2 GREEN: crear `app/modules/laboratorio/__init__.py` y `cliente.py` copiado del enunciado → verde
- [x] 1.3 RED: `test_stock_de_una_vacuna` (`GET /laboratorio/stock/rabia` → 200 `{"vacuna": "rabia", "stock": 15}`) → falla con 404
- [x] 1.4 GREEN: `models.py` (docstring), `schemas.py` (`StockRead`), `service.py` (`asyncio.to_thread(cliente.consultar_stock, vacuna)`), `router.py` (`GET /stock/{vacuna}`, `response_model=StockRead`); `include_router` en `crear_app()` → verde
- [x] 1.5 TRIANGULATE: `parvovirus` → `{"vacuna": "parvovirus", "stock": 20}`

## 2. Sin bloqueos (caso C-09 de la consigna, D-4)

- [x] 2.1 RED/GREEN: `tests/test_laboratorio_concurrencia.py::test_caso_c09_health_responde_con_tres_consultas_en_curso` y `test_tres_consultas_simultaneas_no_se_encolan` (D-4) → pasan por 1.4: mutación llamando a `cliente.consultar_stock` sin `to_thread` → rojo, anotarla, restaurar
- [x] 2.2 REFACTOR: tests en verde

## 3. Entregable `test/laboratorio.http` (D-5)

- [x] 3.1 RED: `tests/test_laboratorio_http.py` (existe, menciona `Caso C-09`, cada bloque con `# Esperado:`, corrido en orden cada bloque responde su código) → falla
- [x] 3.2 GREEN: escribir `test/laboratorio.http` con los tres `GET` de stock, el `GET /health/live` y el comando de Git Bash para lanzarlos a la vez → verde
- [x] 3.3 Verificación manual: uvicorn levantado, correr el comando de D-5 y ver que el `live` responde en centésimas

## 4. Cierre

- [x] 4.1 `pytest` completo en verde

## Workflow follow-up

- `/opsx:archive laboratorio-async` con `pytest` en verde.
- Marcar C-07 como `[x]` en `CHANGES.md`.
