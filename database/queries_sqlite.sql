-- 1) Resumo para dashboard (contagens gerais)
SELECT
  (SELECT COUNT(*) FROM pontos_ilp) AS total_pontos,
  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'ativo') AS pontos_ativos,
  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'manutencao') AS pontos_manutencao,
  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'inativo') AS pontos_inativos,
  (SELECT COUNT(*) FROM ordens_servico WHERE status IN ('aberta', 'em_andamento')) AS os_abertas;

-- 2) Ponto + OS em aberto
SELECT
  os.numero_os,
  os.tipo,
  os.status,
  os.data_abertura,
  p.etiqueta,
  p.endereco,
  p.bairro
FROM ordens_servico os
JOIN pontos_ilp p ON p.id = os.ponto_ilp_id
WHERE os.status IN ('aberta', 'em_andamento')
ORDER BY os.data_abertura DESC;

-- 3) Distribuicao de pontos por bairro
SELECT bairro, COUNT(*) AS total
FROM pontos_ilp
GROUP BY bairro
ORDER BY total DESC, bairro ASC;

-- 4) Tempo medio de resolucao (horas) para OS resolvidas
SELECT
  ROUND(AVG((julianday(data_resolucao) - julianday(data_abertura)) * 24.0), 2) AS media_horas_resolucao
FROM ordens_servico
WHERE status = 'resolvida'
  AND data_resolucao IS NOT NULL;

-- 5) Pontos sem foto de cadastro
SELECT p.id, p.etiqueta, p.endereco, p.bairro
FROM pontos_ilp p
LEFT JOIN fotos_ponto f
  ON f.ponto_ilp_id = p.id AND f.tipo = 'cadastro'
WHERE f.id IS NULL
ORDER BY p.id;
