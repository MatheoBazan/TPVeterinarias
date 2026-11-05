-- Caso C-08 de la consigna: la base rechaza por el CHECK un precio que no es mayor que cero (RN-04).
-- Precondición: python reiniciar.py (la práctica 1 es "Consulta", precio 15000.00).
-- Cómo ejecutarlo, con el contenedor levantado (docker compose up -d), igual en bash y en PowerShell:
--   docker compose cp test/c08_check_precio.sql db:/tmp/c08_check_precio.sql
--   docker compose exec db psql -U <usuario> -d veterinaria -f /tmp/c08_check_precio.sql
-- (<usuario> es POSTGRES_USER del .env). También se puede pegar en psql o en cualquier cliente SQL.
-- Esperado:
--   ERROR:  new row for relation "practica" violates check constraint "ck_practica_precio_positivo"
--   DETAIL:  Failing row contains (1, Consulta, 0.00).
--   (SQLSTATE 23514; el UPDATE no modifica ninguna fila)
UPDATE practica SET precio = 0 WHERE id = 1;

-- Esperado: la práctica 1 conserva su precio (15000.00).
SELECT id, nombre, precio FROM practica WHERE id = 1;
