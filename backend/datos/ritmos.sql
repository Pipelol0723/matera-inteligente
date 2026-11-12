-- Ritmo de crecimiento de las cinco especies de referencia, en dias de juego bien cuidada.
-- Son valores de juego, no botanicos. Se cargan una sola vez, al llegar a la version 4 (en una
-- base nueva, despues de carga.sql), y solo para las especies que existan.

INSERT OR IGNORE INTO ritmo_crecimiento (especie, dias_brote, dias_planta, dias_florecida)
SELECT especie.nombre, ritmo.brote, ritmo.planta, ritmo.florecida
FROM (
              SELECT 'potos' AS nombre, 1 AS brote, 3 AS planta, 6 AS florecida
    UNION ALL SELECT 'helecho',     1, 3, 7
    UNION ALL SELECT 'lavanda',     1, 4, 8
    UNION ALL SELECT 'sansevieria', 2, 5, 10
    UNION ALL SELECT 'suculenta',   2, 6, 12
) AS ritmo
JOIN especie ON especie.nombre = ritmo.nombre;
