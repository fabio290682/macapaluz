PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_pontos_qualidade;
CREATE VIEW vw_pontos_qualidade AS
SELECT
  p.id,
  p.etiqueta,
  p.bairro,
  p.cidade,
  p.status,
  p.lat,
  p.lng,
  p.tipo_lampada,
  p.potencia,
  CASE
    WHEN p.etiqueta LIKE 'SELT-%' THEN 'kmz_selt'
    WHEN p.etiqueta LIKE 'BASE09-%' THEN 'xlsx_base09'
    WHEN p.etiqueta LIKE 'KMZ-%' THEN 'kmz_bairro'
    WHEN p.etiqueta LIKE 'ILP-MAC-%' THEN 'seed_local'
    ELSE 'outros'
  END AS origem,
  CASE
    WHEN p.bairro IS NULL OR TRIM(p.bairro) = '' THEN 1 ELSE 0
  END AS flag_sem_bairro,
  CASE
    WHEN p.tipo_lampada IS NULL OR TRIM(p.tipo_lampada) = '' THEN 1 ELSE 0
  END AS flag_sem_tipo_lampada,
  CASE
    WHEN p.potencia IS NULL OR p.potencia <= 0 THEN 1 ELSE 0
  END AS flag_sem_potencia,
  CASE
    WHEN p.lat IS NULL OR p.lng IS NULL THEN 1 ELSE 0
  END AS flag_sem_coordenada
FROM pontos_ilp p;

DROP VIEW IF EXISTS vw_pontos_qualidade_resumo;
CREATE VIEW vw_pontos_qualidade_resumo AS
SELECT
  origem,
  COUNT(*) AS total,
  SUM(flag_sem_bairro) AS sem_bairro,
  SUM(flag_sem_tipo_lampada) AS sem_tipo_lampada,
  SUM(flag_sem_potencia) AS sem_potencia,
  SUM(flag_sem_coordenada) AS sem_coordenada
FROM vw_pontos_qualidade
GROUP BY origem
ORDER BY total DESC;
