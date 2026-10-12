-- Especies de referencia: las mismas cinco, con los mismos rangos, que tenia backend/datos/especies.csv.
-- Solo se ejecuta si la tabla especie esta vacia: al reiniciar no pisa las especies que agrego el admin.
-- La explicacion completa de cada rango esta en el README, seccion "Tabla de referencia y fuentes":
--   luz: categoria de la tabla de Arkansas [1], hasta el pico de sol directo, unos 10 000 fc [2],
--        convertida a lux (1 fc = 10,764 lux) y redondeada a la decena;
--   temperatura: ficha de cada especie, convertida de grados F a C;
--   humedad del sustrato: ninguna fuente la da en porcentaje; se tomo del Anexo B del enunciado
--        y se comprobo que el orden entre especies coincide con las fuentes.

INSERT INTO especie (nombre, nombre_cientifico) VALUES
    ('sansevieria', 'Dracaena trifasciata'),
    ('potos',       'Epipremnum aureum'),
    ('suculenta',   'Crassula ovata'),
    ('helecho',     'Nephrolepis exaltata'),
    ('lavanda',     'Lavandula angustifolia');

INSERT INTO rango_optimo (especie, parametro, minimo, maximo) VALUES
    -- sansevieria: luz baja [1]; de 70 a 90 F [3]; se riega cuando el sustrato se seco por completo [3]
    ('sansevieria', 'humedad',     20,    45),
    ('sansevieria', 'luz',         270,   2150),
    ('sansevieria', 'temperatura', 21,    32),
    -- potos: luz baja [1]; de 60 a 70 F de noche y de 70 a 85 F de dia [4]
    ('potos',       'humedad',     40,    70),
    ('potos',       'luz',         270,   2150),
    ('potos',       'temperatura', 16,    29),
    -- suculenta (planta de jade): luz muy alta [1]; de 50 a 55 F en invierno y de 65 a 75 F de dia [6]
    ('suculenta',   'humedad',     10,    30),
    ('suculenta',   'luz',         10760, 107640),
    ('suculenta',   'temperatura', 10,    24),
    -- helecho de Boston: luz media [1]; de 50 a 55 F de noche y de 68 a 72 F de dia [5]
    ('helecho',     'humedad',     60,    85),
    ('helecho',     'luz',         1080,  5380),
    ('helecho',     'temperatura', 10,    22),
    -- lavanda: pleno sol [7], categoria muy alta; de 13 a 18 C de noche y de 18 a 27 C de dia [8]
    ('lavanda',     'humedad',     25,    50),
    ('lavanda',     'luz',         10760, 107640),
    ('lavanda',     'temperatura', 13,    27);

-- [1] University of Arkansas Cooperative Extension Service. Light and Moisture Requirements For Selected Indoor Plants.
-- [2] University of Maryland Extension. Lighting for Indoor Plants.
-- [3] Iowa State University Extension and Outreach (2025). Yard and Garden: Caring for Sansevieria.
-- [4] Clemson Cooperative Extension, HGIC (2026). How to Grow Pothos Indoors (Epipremnum spp.).
-- [5] Clemson Cooperative Extension, HGIC (2015). Indoor Ferns.
-- [6] Clemson Cooperative Extension, HGIC (2015). Jade Plant (HGIC 1507).
-- [7] Utah State University Extension (2020). How to Grow English Lavender in Your Garden.
-- [8] Greenhouse Grower (2012). Tips For Producing Lavandula.
