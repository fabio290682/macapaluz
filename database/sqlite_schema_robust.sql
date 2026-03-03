-- MacapaLuz - Schema robusto (SQLite)
-- Foco: integridade, rastreabilidade, performance e crescimento.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS bairros (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  cidade TEXT NOT NULL DEFAULT 'Macapa',
  ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  senha_hash TEXT NOT NULL,
  perfil TEXT NOT NULL CHECK (perfil IN ('operador', 'tecnico', 'gestor', 'admin')),
  ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
  ultimo_acesso TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (length(trim(nome)) >= 3),
  CHECK (instr(email, '@') > 1)
);

CREATE TABLE IF NOT EXISTS pontos_ilp (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  etiqueta TEXT NOT NULL UNIQUE,
  endereco TEXT NOT NULL,
  bairro TEXT,
  bairro_id INTEGER,
  cidade TEXT NOT NULL DEFAULT 'Macapa',
  lat REAL,
  lng REAL,
  tipo_poste TEXT,
  altura INTEGER CHECK (altura IS NULL OR altura BETWEEN 0 AND 100),
  tipo_luminaria TEXT,
  braco TEXT,
  tipo_lampada TEXT,
  potencia INTEGER CHECK (potencia IS NULL OR potencia BETWEEN 1 AND 5000),
  status TEXT NOT NULL DEFAULT 'cadastrado'
    CHECK (status IN ('cadastrado', 'ativo', 'manutencao', 'inativo')),
  origem_dado TEXT NOT NULL DEFAULT 'manual',
  confianca_dado REAL CHECK (confianca_dado IS NULL OR (confianca_dado >= 0 AND confianca_dado <= 1)),
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (bairro_id) REFERENCES bairros(id) ON DELETE SET NULL,
  CHECK ((lat IS NULL AND lng IS NULL) OR (lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180))
);

CREATE TABLE IF NOT EXISTS ordens_servico (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero_os TEXT NOT NULL UNIQUE,
  ponto_ilp_id INTEGER NOT NULL,
  tipo TEXT NOT NULL,
  descricao TEXT,
  solicitante TEXT,
  tecnico_id INTEGER,
  status TEXT NOT NULL DEFAULT 'aberta'
    CHECK (status IN ('aberta', 'em_andamento', 'resolvida', 'cancelada')),
  prioridade TEXT NOT NULL DEFAULT 'media'
    CHECK (prioridade IN ('baixa', 'media', 'alta', 'critica')),
  data_abertura TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  data_resolucao TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (ponto_ilp_id) REFERENCES pontos_ilp(id) ON DELETE RESTRICT,
  FOREIGN KEY (tecnico_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS fotos_ponto (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ponto_ilp_id INTEGER NOT NULL,
  url_s3 TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('cadastro', 'streetview')),
  uploaded_by INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (ponto_ilp_id) REFERENCES pontos_ilp(id) ON DELETE CASCADE,
  FOREIGN KEY (uploaded_by) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS anexos_os (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ordem_servico_id INTEGER NOT NULL,
  tipo_arquivo TEXT NOT NULL,
  nome_arquivo TEXT NOT NULL,
  url_arquivo TEXT NOT NULL,
  tamanho_bytes INTEGER CHECK (tamanho_bytes IS NULL OR tamanho_bytes >= 0),
  uploaded_by INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (ordem_servico_id) REFERENCES ordens_servico(id) ON DELETE CASCADE,
  FOREIGN KEY (uploaded_by) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ordens_servico_eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ordem_servico_id INTEGER NOT NULL,
  evento TEXT NOT NULL,
  status_anterior TEXT,
  status_novo TEXT,
  observacao TEXT,
  actor_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (ordem_servico_id) REFERENCES ordens_servico(id) ON DELETE CASCADE,
  FOREIGN KEY (actor_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pontos_ilp_historico (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ponto_ilp_id INTEGER NOT NULL,
  acao TEXT NOT NULL CHECK (acao IN ('insert', 'update', 'delete')),
  actor_id INTEGER,
  old_data TEXT,
  new_data TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (actor_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS import_lotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fonte TEXT NOT NULL,
  arquivo TEXT,
  registros_lidos INTEGER NOT NULL DEFAULT 0,
  registros_inseridos INTEGER NOT NULL DEFAULT 0,
  registros_atualizados INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'concluido' CHECK (status IN ('processando', 'concluido', 'falha')),
  mensagem TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS auditoria_api (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint TEXT NOT NULL,
  metodo TEXT NOT NULL,
  status_code INTEGER NOT NULL,
  actor_id INTEGER,
  ip_origem TEXT,
  duracao_ms INTEGER,
  payload_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (actor_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bairros_nome ON bairros(nome);
CREATE INDEX IF NOT EXISTS idx_usuarios_perfil_ativo ON usuarios(perfil, ativo);

CREATE INDEX IF NOT EXISTS idx_pontos_status_bairro ON pontos_ilp(status, bairro);
CREATE INDEX IF NOT EXISTS idx_pontos_bairro_id ON pontos_ilp(bairro_id);
CREATE INDEX IF NOT EXISTS idx_pontos_geo ON pontos_ilp(lat, lng);
CREATE INDEX IF NOT EXISTS idx_pontos_origem_status ON pontos_ilp(origem_dado, status);
CREATE INDEX IF NOT EXISTS idx_pontos_deleted_at ON pontos_ilp(deleted_at);
CREATE INDEX IF NOT EXISTS idx_pontos_etiqueta_ci ON pontos_ilp(lower(etiqueta));

CREATE INDEX IF NOT EXISTS idx_os_status_abertura ON ordens_servico(status, data_abertura DESC);
CREATE INDEX IF NOT EXISTS idx_os_ponto_status ON ordens_servico(ponto_ilp_id, status);
CREATE INDEX IF NOT EXISTS idx_os_tecnico_status ON ordens_servico(tecnico_id, status);
CREATE INDEX IF NOT EXISTS idx_os_prioridade_status ON ordens_servico(prioridade, status);

CREATE INDEX IF NOT EXISTS idx_fotos_ponto_tipo ON fotos_ponto(ponto_ilp_id, tipo);
CREATE INDEX IF NOT EXISTS idx_anexos_os ON anexos_os(ordem_servico_id);
CREATE INDEX IF NOT EXISTS idx_eventos_os_data ON ordens_servico_eventos(ordem_servico_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hist_ponto_data ON pontos_ilp_historico(ponto_ilp_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria_api(created_at DESC);

CREATE TRIGGER IF NOT EXISTS trg_bairros_updated_at
AFTER UPDATE ON bairros
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE bairros SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_usuarios_updated_at
AFTER UPDATE ON usuarios
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE usuarios SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_pontos_updated_at
AFTER UPDATE ON pontos_ilp
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE pontos_ilp SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_os_updated_at
AFTER UPDATE ON ordens_servico
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
  UPDATE ordens_servico SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_pontos_hist_insert
AFTER INSERT ON pontos_ilp
FOR EACH ROW
BEGIN
  INSERT INTO pontos_ilp_historico (ponto_ilp_id, acao, new_data)
  VALUES (
    NEW.id,
    'insert',
    json_object(
      'etiqueta', NEW.etiqueta,
      'endereco', NEW.endereco,
      'bairro', NEW.bairro,
      'cidade', NEW.cidade,
      'status', NEW.status
    )
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_pontos_hist_update
AFTER UPDATE ON pontos_ilp
FOR EACH ROW
WHEN
  COALESCE(OLD.endereco, '') <> COALESCE(NEW.endereco, '')
  OR COALESCE(OLD.bairro, '') <> COALESCE(NEW.bairro, '')
  OR COALESCE(OLD.lat, 0) <> COALESCE(NEW.lat, 0)
  OR COALESCE(OLD.lng, 0) <> COALESCE(NEW.lng, 0)
  OR COALESCE(OLD.status, '') <> COALESCE(NEW.status, '')
BEGIN
  INSERT INTO pontos_ilp_historico (ponto_ilp_id, acao, old_data, new_data)
  VALUES (
    NEW.id,
    'update',
    json_object('endereco', OLD.endereco, 'bairro', OLD.bairro, 'lat', OLD.lat, 'lng', OLD.lng, 'status', OLD.status),
    json_object('endereco', NEW.endereco, 'bairro', NEW.bairro, 'lat', NEW.lat, 'lng', NEW.lng, 'status', NEW.status)
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_pontos_hist_delete
AFTER DELETE ON pontos_ilp
FOR EACH ROW
BEGIN
  INSERT INTO pontos_ilp_historico (ponto_ilp_id, acao, old_data)
  VALUES (
    OLD.id,
    'delete',
    json_object(
      'etiqueta', OLD.etiqueta,
      'endereco', OLD.endereco,
      'bairro', OLD.bairro,
      'cidade', OLD.cidade,
      'status', OLD.status
    )
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_os_event_insert
AFTER INSERT ON ordens_servico
FOR EACH ROW
BEGIN
  INSERT INTO ordens_servico_eventos (ordem_servico_id, evento, status_novo, observacao)
  VALUES (NEW.id, 'criada', NEW.status, 'Ordem criada');
END;

CREATE TRIGGER IF NOT EXISTS trg_os_event_status
AFTER UPDATE ON ordens_servico
FOR EACH ROW
WHEN COALESCE(OLD.status, '') <> COALESCE(NEW.status, '')
BEGIN
  INSERT INTO ordens_servico_eventos (ordem_servico_id, evento, status_anterior, status_novo, observacao)
  VALUES (NEW.id, 'mudanca_status', OLD.status, NEW.status, 'Mudanca automatica de status');
END;

CREATE TRIGGER IF NOT EXISTS trg_os_set_data_resolucao
AFTER UPDATE ON ordens_servico
FOR EACH ROW
WHEN NEW.status = 'resolvida' AND NEW.data_resolucao IS NULL
BEGIN
  UPDATE ordens_servico
  SET data_resolucao = CURRENT_TIMESTAMP
  WHERE id = NEW.id;
END;

CREATE VIEW IF NOT EXISTS vw_dashboard_operacional AS
SELECT
  (SELECT COUNT(*) FROM pontos_ilp WHERE deleted_at IS NULL) AS total_pontos,
  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'ativo' AND deleted_at IS NULL) AS pontos_ativos,
  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'manutencao' AND deleted_at IS NULL) AS pontos_manutencao,
  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'inativo' AND deleted_at IS NULL) AS pontos_inativos,
  (SELECT COUNT(*) FROM ordens_servico WHERE status IN ('aberta', 'em_andamento')) AS os_abertas,
  (SELECT COUNT(*) FROM ordens_servico WHERE status = 'resolvida') AS os_resolvidas;

CREATE VIEW IF NOT EXISTS vw_pontos_por_bairro AS
SELECT
  COALESCE(bairro, 'SEM_BAIRRO') AS bairro,
  COUNT(*) AS total,
  SUM(CASE WHEN status = 'ativo' THEN 1 ELSE 0 END) AS ativos,
  SUM(CASE WHEN status = 'manutencao' THEN 1 ELSE 0 END) AS manutencao,
  SUM(CASE WHEN status = 'inativo' THEN 1 ELSE 0 END) AS inativos
FROM pontos_ilp
WHERE deleted_at IS NULL
GROUP BY COALESCE(bairro, 'SEM_BAIRRO');
