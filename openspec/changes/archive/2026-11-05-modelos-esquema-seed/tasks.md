> **Governance ALTO**: este change define el esquema del que dependen todos los demás. No empezar el `apply` sin la revisión de Matheo del `design.md` (tarea 0.1).
>
> **TDD estricto** (contra PostgreSQL real `veterinaria_test`, nunca SQLite ni mocks de la sesión): cada grupo sigue RED → GREEN → TRIANGULATE → REFACTOR y se ejecuta `pytest` en cada paso. Si un test pasa de entrada porque el código de un grupo anterior ya cubre la propiedad, comprobar que falla rompiendo temporalmente esa propiedad (mutación) y registrarlo en la evidencia TDD. Los módulos de test nuevos declaran `pytestmark = pytest.mark.integracion`.
>
> **Entregables en `test/`**: este change no tiene endpoints, así que no lleva `.http`; su entregable de la cátedra es el `.sql` del caso C-08 (grupo 13).

## 0. Gobernanza y entorno

- [x] 0.1 Confirmar con Matheo la aprobación del `design.md`, en especial las decisiones marcadas ⚠ (D-2 `fecha` con `DateTime(timezone=True)`, D-3 nombres de restricciones, D-7 `passive_deletes="all"`, D-8 registro de modelos + línea en `app/main.py`); registrar la aprobación (fecha) en el encabezado de cada decisión
- [x] 0.2 Verificar que C-01 `base-proyecto-conexion` está aplicado (`openspec list --json`: tareas completas o archivado) y que existen `app/core/config.py`, `app/core/database.py`, `tests/conftest.py`, `tests/soporte.py` y `README.md` con la sección "Índice de `turno_practica.turno_id`"
- [x] 0.3 `docker compose config` parsea sin error (al momento del propose fallaba en la línea 5 de `docker-compose.yml`, reportado a C-01); `docker compose up -d --wait`; la base `veterinaria_test` existe
- [x] 0.4 Venv activo: `pip check` sin errores y versiones `sqlmodel==0.0.48`, `sqlalchemy==2.0.57`, `asyncpg==0.32.0` (`pip show`)
- [x] 0.5 Safety net: `pytest` completo en verde; anotar la línea base "N tests passing" (se modificarán `app/main.py`, `tests/conftest.py`, `tests/soporte.py`, `tests/test_repositorio.py` y `README.md`)

## 1. Tablas y recreación del esquema

- [x] 1.1 RED: en `tests/conftest.py`, fixtures `motor_test` (motor con `Configuracion(database_url=url_base_test, sql_echo=False)`, `dispose` al final) y `esquema_vacio` (llama `recrear_esquema` de `reiniciar`); `tests/test_esquema.py::test_crear_esquema_deja_exactamente_las_seis_tablas` (conjunto exacto en `information_schema.tables`, sin `fichaduenio` ni `turnopractica`) → falla por `ImportError`
- [x] 1.2 GREEN: crear `app/modules/{duenios,mascotas,practicas,turnos}/__init__.py` (vacíos) y `models.py` con los seis modelos `table=True`, `__tablename__` explícito y sólo su clave primaria (D-1; `TurnoPractica` con `turno_id` y `practica_id`, en ese orden); `app/core/modelos.py` (D-8); `reiniciar.py` con `recrear_esquema(engine)` (D-11) → verde
- [x] 1.3 TRIANGULATE: `test_recrear_esquema_sobre_tablas_con_datos_las_deja_vacias_con_ids_desde_1` (insertar una fila, recrear, la tabla queda vacía y el próximo id es 1) y `test_recrear_esquema_dos_veces_seguidas_no_falla`
- [x] 1.4 REFACTOR: fixtures `sesion` (`crear_fabrica_sesiones(motor_test)`) y `sentencias_sql` (listener `before_cursor_execute` sobre `motor_test.sync_engine`, retirado en el teardown); helper `error_postgres(exc)` en `tests/soporte.py` (D-16); tests en verde

## 2. Columnas, tipos y NOT NULL

- [x] 2.1 RED: `test_columnas_de_cada_tabla_son_las_de_la_consigna` parametrizado por las seis tablas (conjunto exacto de `column_name` y `is_nullable = 'NO'`) → falla
- [x] 2.2 GREEN: agregar todas las columnas con los tipos de D-2 (`str`, `Decimal` con `sa_type=Numeric(10, 2)` / `Numeric(12, 2)`, `fecha` con `sa_type=DateTime(timezone=True)`, claves foráneas como `int` sin `foreign_key` todavía) → verde
- [x] 2.3 TRIANGULATE: `test_tipos_de_columna` parametrizado (`numeric` 10/2 en `precio` y `precio_unitario`, 12/2 en `total`, `timestamp with time zone` en `fecha`, `integer` con default `nextval(...)` en los `id`, `character varying` en los textos); en `tests/test_restricciones.py`: precio `15000` vuelve como `Decimal("15000.00")` y `0.10` exacto; `fecha` `2026-11-12T10:30:00-03:00` vuelve con zona y igual a `13:30Z`; `INSERT` con `text()` de una mascota sin `duenio_id` y de un dueño sin `email` → `23502`
- [x] 2.4 REFACTOR: helpers de introspección (consultas a `information_schema` / `pg_catalog`) dentro de `tests/test_esquema.py`; tests en verde

## 3. Claves primarias (RN-07)

- [x] 3.1 RED: `test_clave_primaria_de_turno_practica_es_compuesta_y_empieza_por_turno_id` (`pg_get_constraintdef` = `PRIMARY KEY (turno_id, practica_id)`) y `test_claves_primarias_se_llaman_tabla_pkey`; si pasan de entrada (grupo 1), mutación: invertir temporalmente el orden de las columnas en `TurnoPractica` y ver el rojo
- [x] 3.2 GREEN/TRIANGULATE: `test_misma_practica_dos_veces_en_un_turno_se_rechaza` (`23505`, `turno_practica_pkey`, sigue una sola fila) y `test_misma_practica_en_dos_turnos_se_acepta` (filas creadas con `text()` hasta que existan las claves foráneas del grupo 6)
- [x] 3.3 REFACTOR: tests en verde

## 4. Unicidad (RN-01, RN-02, RN-03)

- [x] 4.1 RED: `test_email_de_duenio_repetido_se_rechaza` (`23505`, `uq_duenio_email`, un solo dueño con ese email) → falla
- [x] 4.2 GREEN: `__table_args__ = (UniqueConstraint("email", name="uq_duenio_email"),)` en `Duenio` (D-3) → verde
- [x] 4.3 TRIANGULATE: email distinto se acepta; nombre de práctica repetido → `uq_practica_nombre`; segunda ficha del mismo dueño → `uq_ficha_duenio_duenio_id`; primera ficha de otro dueño se acepta → agregar los dos `UniqueConstraint` restantes
- [x] 4.4 REFACTOR: parametrizar los rechazos por (modelo, datos, restricción esperada); tests en verde

## 5. CHECK sobre el dinero (RN-04, RN-06, caso C-08)

- [x] 5.1 RED: `test_precio_de_practica_cero_se_rechaza` (`23514`, `ck_practica_precio_positivo`) → falla
- [x] 5.2 GREEN: `CheckConstraint("precio > 0", name="ck_practica_precio_positivo")` en `Practica` → verde
- [x] 5.3 TRIANGULATE: precio `-1` rechazado y `0.01` aceptado; `UPDATE practica SET precio = 0 WHERE id = 1` con `text()` rechazado y precio intacto; `precio_unitario = 0` → `ck_turno_practica_precio_unitario_positivo`; `total = -0.01` → `ck_turno_total_no_negativo` y `total = 0` aceptado → agregar los dos `CheckConstraint` restantes
- [x] 5.4 REFACTOR: parametrizar valores límite; tests en verde

## 6. Claves foráneas y reglas de borrado (RN-08, RN-09, PA-02)

- [x] 6.1 RED: `test_reglas_de_borrado_de_las_claves_foraneas` parametrizado por las cinco (`conname`, `confdeltype` `'c'` / `'r'` de D-4, ninguna `'a'`) → falla
- [x] 6.2 GREEN: `Field(foreign_key="...", ondelete="CASCADE" | "RESTRICT")` en las cinco columnas (D-4) → verde
- [x] 6.3 TRIANGULATE: insertar mascota con dueño 999 → `23503` `mascota_duenio_id_fkey`; `turno_practica` con práctica 999 → `turno_practica_practica_id_fkey`; ficha con dueño 999 → `ficha_duenio_duenio_id_fkey`; turno con mascota 999 → `turno_mascota_id_fkey`; migrar los tests del grupo 3 a escrituras con el ORM si ya lo permiten
- [x] 6.4 REFACTOR: tests en verde

## 7. Índices y su justificación

- [x] 7.1 RED: `test_indices_de_cada_tabla_son_exactamente_los_esperados` parametrizado por tabla (conjuntos exactos de D-3/D-5 en `pg_indexes`) → falla por faltar los `ix_*`
- [x] 7.2 GREEN: `index=True` en `mascota.duenio_id`, `turno.mascota_id` y `turno_practica.practica_id` → verde
- [x] 7.3 TRIANGULATE: `test_turno_practica_turno_id_no_tiene_indice_propio` (el único índice de `turno_practica` que empieza por `turno_id` es `turno_practica_pkey`); mutación: `index=True` temporal en `turno_id` → rojo
- [x] 7.4 RED → GREEN: en `tests/test_repositorio.py`, test de que la sección "Índice de `turno_practica.turno_id`" del `README.md` menciona la clave primaria compuesta; completar la sección con el texto de D-15 → verde

## 8. Navegación en los dos extremos

- [x] 8.1 RED: `test_cada_relacion_tiene_su_extremo_opuesto` parametrizado por los cinco pares de D-6 (`sqlalchemy.inspect(Modelo).relationships`, `back_populates` cruzados, `mapper.class_` correcto) y `test_duenio_ficha_no_es_una_lista` (`uselist is False`; las colecciones `uselist is True`) → falla
- [x] 8.2 GREEN: declarar las diez relaciones con `Relationship(back_populates=...)`, `Optional["..."]` / `list["..."]` + `TYPE_CHECKING` entre módulos, `sa_relationship_kwargs={"uselist": False}` en `Duenio.ficha` (sin `passive_deletes` todavía) → verde
- [x] 8.3 TRIANGULATE: en `tests/test_relaciones.py`: asignar `mascota.duenio = duenio` en memoria agrega la mascota a `duenio.mascotas` sin consultas (`sentencias_sql` vacía); crear un turno, hacer `turno.practicas.append(TurnoPractica(...))` dos veces y guardar sólo el turno en una transacción inserta las dos filas con el `turno_id` nuevo
- [x] 8.4 REFACTOR: tests en verde

## 9. Datos iniciales (PA-03)

- [x] 9.1 RED: `tests/test_reiniciar.py::test_datos_iniciales_cargan_exactamente_las_filas_esperadas` (contenido exacto de `duenio`, `ficha_duenio`, `mascota`, `practica` de la spec) → falla por `ImportError` de `cargar_datos_iniciales`
- [x] 9.2 GREEN: `cargar_datos_iniciales(session)` en `reiniciar.py` con los datos de D-13 y el `flush` escalonado de D-11 → verde
- [x] 9.3 TRIANGULATE: turno 1 con `mascota_id = 2`, `total = 23000.00` igual a la suma de sus `precio_unitario`, y `turno_practica` exacta; carga que falla a mitad de camino (dueño `ana.gomez@example.com` preexistente → `uq_duenio_email`, `practica` y demás tablas vacías); carga repetida sin recrear → `23505` y mismas cantidades; ejemplo del Ej. 4 (turno para la mascota 1 con prácticas 1 y 3, precios copiados → id 2, total 27000.00); secuencias: nuevo dueño, mascota y práctica reciben 3, 4 y 5
- [x] 9.4 REFACTOR: fixture `base_con_seed` en `tests/conftest.py` (reutilizable por C-03..C-06); el total se calcula con `sum(..., start=Decimal("0"))`, nunca escrito a mano; tests en verde

## 10. Lecturas con carga anticipada

- [x] 10.1 RED/GREEN: con `base_con_seed`, `test_ficha_de_duenio_es_un_objeto` (`joinedload(Duenio.ficha)`: dueño 1 → `FichaDuenio` con `duenio_id == 1`) y `test_duenio_sin_ficha_devuelve_none` (dueño 2)
- [x] 10.2 TRIANGULATE: `selectinload(Duenio.mascotas)` → "Toby" y "Mishi" para el dueño 1 (y cada una navega de vuelta al mismo dueño), "Luna" para el dueño 2; turno 1 con `joinedload(Turno.mascota)` + `selectinload(Turno.practicas).joinedload(TurnoPractica.practica)` → "Mishi", "Consulta" 15000.00 y "Desparasitación" 8000.00, accesibles después de cerrar la sesión
- [x] 10.3 REFACTOR: tests en verde

## 11. El borrado lo decide la base (`passive_deletes`)

- [x] 11.1 RED: `tests/test_borrados.py::test_borrar_turno_sin_practicas_cargadas_no_toca_turno_practica` (con `sentencias_sql`: está el `DELETE FROM turno` y no hay `SELECT`/`UPDATE`/`DELETE` sobre `turno_practica`; las filas del turno 1 desaparecen; prácticas 1 y 2 siguen) → falla (el ORM carga las hijas e intenta vaciar la PK)
- [x] 11.2 GREEN: `passive_deletes="all"` en `Turno.practicas`, sin `cascade_delete` (D-7) → verde
- [x] 11.3 TRIANGULATE: turno 1 con prácticas cargadas por `selectinload` → ningún `UPDATE`/`DELETE` sobre `turno_practica` y filas borradas
- [x] 11.4 RED → GREEN: dueño nuevo con ficha y sin mascotas, con la ficha sin cargar y cargada → el borrado se acepta, la ficha desaparece y no hay `UPDATE`/`DELETE` sobre `ficha_duenio` (rojo: el ORM pone `duenio_id = NULL` → `23502`) → `passive_deletes="all"` en `Duenio.ficha`
- [x] 11.5 RED → GREEN: dueño 1 con mascotas, sin cargarlas y cargadas → `23503` `mascota_duenio_id_fkey`, sin `UPDATE` sobre `mascota` ni `ficha_duenio`, y todo intacto (verificado con otra sesión tras el rollback) (rojo: `UPDATE mascota SET duenio_id = NULL` → `23502`) → `passive_deletes="all"` en `Duenio.mascotas`
- [x] 11.6 RED → GREEN: borrar "Mishi" (tiene el turno 1) → `turno_mascota_id_fkey`; borrar "Consulta" (usada en el turno 1) → `turno_practica_practica_id_fkey` → `passive_deletes="all"` en `Mascota.turnos` y `Practica.turnos`; triangular con "Toby" y "Vacuna quíntuple", que se borran
- [x] 11.7 REFACTOR: `test_lados_uno_tienen_passive_deletes_all_sin_cascada_delete` en `tests/test_esquema.py` (introspección de las cinco relaciones); tests en verde

## 12. `reiniciar.py` como script y registro de modelos en la aplicación

- [x] 12.1 RED: `test_reiniciar_py_sobre_base_sin_tablas` (subproceso `python reiniciar.py` con `DATABASE_URL = TEST_DATABASE_URL` y `SQL_ECHO=0` vía `asyncio.to_thread(subprocess.run, ...)`, tras `drop_all`; código 0 y datos iniciales presentes) → falla (no hay punto de entrada)
- [x] 12.2 GREEN: `main()` y bloque `if __name__ == "__main__":` de D-11 (`dispose` en `finally`, resumen de una línea, `ConfiguracionInvalida` → `SystemExit`) → verde
- [x] 12.3 TRIANGULATE: dos ejecuciones seguidas con filas agregadas en el medio → mismo estado e ids; `DATABASE_URL=""` y `DATABASE_URL=postgresql://...` → código ≠ 0, mensaje con `DATABASE_URL` y sin la clave de `TEST_DATABASE_URL`
- [x] 12.4 RED → GREEN: subproceso que hace `import app.main` y verifica que `SQLModel.metadata.tables` tiene las seis tablas y `configure_mappers()` no falla → rojo → agregar `from app.core import modelos  # noqa: F401` con su comentario en `app/main.py` (D-8) → verde; triangular con un subproceso que importa sólo `app.modules.duenios.models` y comprueba que `configure_mappers()` lanza `InvalidRequestError`
- [x] 12.5 REFACTOR: suite completa en verde (incluidos los tests de C-01)

## 13. Caso C-08 de la consigna (`test/c08_check_precio.sql`)

- [x] 13.1 RED: `test_sql_del_caso_c08_es_rechazado_por_el_check` (con `base_con_seed`: lee `test/c08_check_precio.sql`, descarta líneas `--`, separa por `;`, ejecuta el `UPDATE` → `23514` `ck_practica_precio_positivo`; ejecuta el `SELECT` → 15000.00) → falla porque el archivo no existe
- [x] 13.2 GREEN: escribir `test/c08_check_precio.sql` con el contenido de D-14 → verde
- [x] 13.3 TRIANGULATE: `test_sql_del_caso_c08_documenta_precondicion_ejecucion_y_error` (los comentarios mencionan `python reiniciar.py`, `docker compose cp`, `docker compose exec db psql` y `ck_practica_precio_positivo`; no contiene el valor de `POSTGRES_PASSWORD` si está definido en el entorno)
- [x] 13.4 Manual: `python reiniciar.py` sobre la base de desarrollo y ejecutar los dos comandos del comentario; confirmar en la consola el `ERROR ... violates check constraint "ck_practica_precio_positivo"` y el `SELECT` con 15000.00

## 14. README

- [x] 14.1 Paso `python reiniciar.py`: quitar la marca "disponible desde C-02", aclarar que borra y recrea las tablas de `DATABASE_URL` y carga los datos iniciales; mencionar el caso C-08 y remitir a los comentarios de `test/c08_check_precio.sql` (D-15)

## 15. Verificación final

- [x] 15.1 `pytest` completo en verde: línea base de 0.5 + los tests nuevos, sin tests omitidos por falta de base
- [x] 15.2 Base de desarrollo vacía (`docker compose exec db dropdb -U <usuario> veterinaria` + `docker compose exec db createdb -U <usuario> veterinaria`), `python reiniciar.py` dos veces seguidas: ambas terminan con código 0 y el mismo resumen
- [x] 15.3 Ejecutar el `.sql` del caso C-08 según su comentario y ver el error del CHECK (13.4 sobre la base recién creada)
- [x] 15.4 Revisión contra las reglas duras: sin `float` para dinero, sin `cascade_delete`, sin `from __future__ import annotations` en los `models.py`, sin `TODO` ni archivos vacíos de relleno, sin `schemas.py`/`service.py`/`router.py` en los módulos nuevos, sin secretos en archivos versionados
- [x] 15.5 `openspec validate modelos-esquema-seed --strict` sin errores; completar la tabla "TDD Cycle Evidence" en el resumen del `apply`
- [x] 15.6 Guardar en engram (`opsx/modelos-esquema-seed/apply`) el resultado y la recomendación de actualizar DD-13 de `knowledge-base/09` a `passive_deletes="all"` al archivar
