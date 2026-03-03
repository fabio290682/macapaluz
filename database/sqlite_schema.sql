-- MacapaLuz - Schema principal (SQLite)
-- Equivalente funcional do modelo definido para PostgreSQL.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  senha_hash TEXT NOT NULL,
  perfil TEXT NOT NULL CHECK (perfil IN ('operador', 'tecnico', 'gestor', 'admin')),
  ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
  ultimo_acesso TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pontos_ilp (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  etiqueta TEXT NOT NULL UNIQUE,
  endereco TEXT NOT NULL,
  bairro TEXT,
  cidade TEXT NOT NULL DEFAULT 'Macapa',
  lat REAL,
  lng REAL,
  tipo_poste TEXT,
  altura INTEGER CHECK (altura IS NULL OR altura >= 0),
  tipo_luminaria TEXT,
  braco TEXT,
  tipo_lampada TEXT,
  potencia INTEGER CHECK (potencia IS NULL OR potencia >= 0),
  status TEXT NOT NULL DEFAULT 'cadastrado'
    CHECK (status IN ('cadastrado', 'ativo', 'manutencao', 'inativo')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

CREATE INDEX IF NOT EXISTS idx_usuarios_perfil ON usuarios(perfil);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);

CREATE INDEX IF NOT EXISTS idx_pontos_ilp_status ON pontos_ilp(status);
CREATE INDEX IF NOT EXISTS idx_pontos_ilp_bairro ON pontos_ilp(bairro);
CREATE INDEX IF NOT EXISTS idx_pontos_ilp_cidade ON pontos_ilp(cidade);
CREATE INDEX IF NOT EXISTS idx_pontos_ilp_lat_lng ON pontos_ilp(lat, lng);

CREATE INDEX IF NOT EXISTS idx_ordens_servico_ponto_id ON ordens_servico(ponto_ilp_id);
CREATE INDEX IF NOT EXISTS idx_ordens_servico_tecnico_id ON ordens_servico(tecnico_id);
CREATE INDEX IF NOT EXISTS idx_ordens_servico_status ON ordens_servico(status);
CREATE INDEX IF NOT EXISTS idx_ordens_servico_data_abertura ON ordens_servico(data_abertura);

CREATE INDEX IF NOT EXISTS idx_fotos_ponto_ponto_id ON fotos_ponto(ponto_ilp_id);
CREATE INDEX IF NOT EXISTS idx_fotos_ponto_tipo ON fotos_ponto(tipo);

CREATE TRIGGER IF NOT EXISTS trg_usuarios_updated_at
AFTER UPDATE ON usuarios
FOR EACH ROW
BEGIN
  UPDATE usuarios SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_pontos_ilp_updated_at
AFTER UPDATE ON pontos_ilp
FOR EACH ROW
BEGIN
  UPDATE pontos_ilp SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_ordens_servico_updated_at
AFTER UPDATE ON ordens_servico
FOR EACH ROW
BEGIN
  UPDATE ordens_servico SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
