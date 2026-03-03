-- MacapaLuz - Schema principal (PostgreSQL + PostGIS)
-- Baseado em arquitetura-macapaluz.html

CREATE EXTENSION IF NOT EXISTS postgis;

-- Enums
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'perfil_usuario') THEN
    CREATE TYPE perfil_usuario AS ENUM ('operador', 'tecnico', 'gestor', 'admin');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'status_ponto') THEN
    CREATE TYPE status_ponto AS ENUM ('cadastrado', 'ativo', 'manutencao', 'inativo');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'status_os') THEN
    CREATE TYPE status_os AS ENUM ('aberta', 'em_andamento', 'resolvida', 'cancelada');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipo_foto_ponto') THEN
    CREATE TYPE tipo_foto_ponto AS ENUM ('cadastro', 'streetview');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS usuarios (
  id BIGSERIAL PRIMARY KEY,
  nome TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  senha_hash TEXT NOT NULL,
  perfil perfil_usuario NOT NULL,
  ativo BOOLEAN NOT NULL DEFAULT TRUE,
  ultimo_acesso TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pontos_ilp (
  id BIGSERIAL PRIMARY KEY,
  etiqueta TEXT NOT NULL UNIQUE,
  endereco TEXT NOT NULL,
  bairro TEXT,
  cidade TEXT NOT NULL DEFAULT 'Macapa',
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  geom geometry(Point, 4326),
  tipo_poste TEXT,
  altura INTEGER,
  tipo_luminaria TEXT,
  braco TEXT,
  tipo_lampada TEXT,
  potencia INTEGER,
  status status_ponto NOT NULL DEFAULT 'cadastrado',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_altura_nonneg CHECK (altura IS NULL OR altura >= 0),
  CONSTRAINT chk_potencia_nonneg CHECK (potencia IS NULL OR potencia >= 0)
);

CREATE TABLE IF NOT EXISTS ordens_servico (
  id BIGSERIAL PRIMARY KEY,
  numero_os TEXT NOT NULL UNIQUE,
  ponto_ilp_id BIGINT NOT NULL REFERENCES pontos_ilp(id) ON DELETE RESTRICT,
  tipo TEXT NOT NULL,
  descricao TEXT,
  solicitante TEXT,
  tecnico_id BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
  status status_os NOT NULL DEFAULT 'aberta',
  data_abertura TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  data_resolucao TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fotos_ponto (
  id BIGSERIAL PRIMARY KEY,
  ponto_ilp_id BIGINT NOT NULL REFERENCES pontos_ilp(id) ON DELETE CASCADE,
  url_s3 TEXT NOT NULL,
  tipo tipo_foto_ponto NOT NULL,
  uploaded_by BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_perfil ON usuarios(perfil);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);

CREATE INDEX IF NOT EXISTS idx_pontos_ilp_status ON pontos_ilp(status);
CREATE INDEX IF NOT EXISTS idx_pontos_ilp_bairro ON pontos_ilp(bairro);
CREATE INDEX IF NOT EXISTS idx_pontos_ilp_cidade ON pontos_ilp(cidade);
CREATE INDEX IF NOT EXISTS idx_pontos_ilp_geom ON pontos_ilp USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_ordens_servico_ponto_id ON ordens_servico(ponto_ilp_id);
CREATE INDEX IF NOT EXISTS idx_ordens_servico_tecnico_id ON ordens_servico(tecnico_id);
CREATE INDEX IF NOT EXISTS idx_ordens_servico_status ON ordens_servico(status);
CREATE INDEX IF NOT EXISTS idx_ordens_servico_data_abertura ON ordens_servico(data_abertura);

CREATE INDEX IF NOT EXISTS idx_fotos_ponto_ponto_id ON fotos_ponto(ponto_ilp_id);
CREATE INDEX IF NOT EXISTS idx_fotos_ponto_tipo ON fotos_ponto(tipo);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_usuarios_updated_at ON usuarios;
CREATE TRIGGER trg_usuarios_updated_at
BEFORE UPDATE ON usuarios
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_pontos_ilp_updated_at ON pontos_ilp;
CREATE TRIGGER trg_pontos_ilp_updated_at
BEFORE UPDATE ON pontos_ilp
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_ordens_servico_updated_at ON ordens_servico;
CREATE TRIGGER trg_ordens_servico_updated_at
BEFORE UPDATE ON ordens_servico
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Mantem geom sincronizado com lat/lng quando ambos estiverem preenchidos.
CREATE OR REPLACE FUNCTION sync_geom_from_lat_lng()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL THEN
    NEW.geom = ST_SetSRID(ST_MakePoint(NEW.lng, NEW.lat), 4326);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pontos_ilp_sync_geom ON pontos_ilp;
CREATE TRIGGER trg_pontos_ilp_sync_geom
BEFORE INSERT OR UPDATE ON pontos_ilp
FOR EACH ROW
EXECUTE FUNCTION sync_geom_from_lat_lng();
