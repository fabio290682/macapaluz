PRAGMA foreign_keys = ON;

-- Usuarios base
INSERT OR IGNORE INTO usuarios (nome, email, senha_hash, perfil, ativo)
VALUES
  ('Admin MacapaLuz', 'admin@macapaluz.local', 'dev_hash_admin', 'admin', 1),
  ('Gestor Operacoes', 'gestor@macapaluz.local', 'dev_hash_gestor', 'gestor', 1),
  ('Tecnico Campo 01', 'tecnico1@macapaluz.local', 'dev_hash_tecnico1', 'tecnico', 1),
  ('Operador Central', 'operador@macapaluz.local', 'dev_hash_operador', 'operador', 1);

-- Pontos ILP iniciais
INSERT OR IGNORE INTO pontos_ilp
  (etiqueta, endereco, bairro, cidade, lat, lng, tipo_poste, altura, tipo_luminaria, braco, tipo_lampada, potencia, status)
VALUES
  ('ILP-MAC-00142', 'Av Mendonca Furtado, 1200', 'Centro', 'Macapa', 0.0349, -51.0694, 'Concreto', 9, 'Fechada', 'Simples', 'LED', 100, 'ativo'),
  ('ILP-MAC-00143', 'Av Azarias Neto, 500', 'Buritizal', 'Macapa', 0.0285, -51.0720, 'Metalico', 11, 'Aberta', 'Duplo', 'Vapor de Sodio', 150, 'manutencao'),
  ('ILP-MAC-00144', 'R Leopoldo Machado, 88', 'Centro', 'Macapa', 0.0310, -51.0650, 'Concreto', 7, 'Decorativa', 'Ornamental', 'LED', 70, 'ativo'),
  ('ILP-MAC-00145', 'Av FAB, 350', 'Centro', 'Macapa', 0.0370, -51.0580, 'Metalico', 12, 'Projetor', 'Simples', 'Vapor Metalico', 250, 'inativo'),
  ('ILP-MAC-00146', 'R Sao Jose, 22', 'Perpetuo Socorro', 'Macapa', 0.0290, -51.0600, 'Concreto', 9, 'Fechada', 'Simples', 'LED', 100, 'ativo'),
  ('ILP-MAC-00147', 'Av Coaracy Nunes, 780', 'Jardim Equatorial', 'Macapa', 0.0210, -51.0800, 'Fibra de Vidro', 7, 'Fechada', 'Simples', 'LED', 70, 'cadastrado');

-- Ordens de servico iniciais
INSERT OR IGNORE INTO ordens_servico
  (numero_os, ponto_ilp_id, tipo, descricao, solicitante, tecnico_id, status, data_abertura, data_resolucao)
VALUES
  (
    'OS-2026-0001',
    (SELECT id FROM pontos_ilp WHERE etiqueta = 'ILP-MAC-00143'),
    'Corretiva',
    'Lampada apagada ha 2 dias',
    'Central 156',
    (SELECT id FROM usuarios WHERE email = 'tecnico1@macapaluz.local'),
    'em_andamento',
    '2026-02-28 09:10:00',
    NULL
  ),
  (
    'OS-2026-0002',
    (SELECT id FROM pontos_ilp WHERE etiqueta = 'ILP-MAC-00145'),
    'Inspecao',
    'Revisao geral de circuito',
    'Fiscalizacao',
    (SELECT id FROM usuarios WHERE email = 'tecnico1@macapaluz.local'),
    'aberta',
    '2026-03-01 14:30:00',
    NULL
  ),
  (
    'OS-2026-0003',
    (SELECT id FROM pontos_ilp WHERE etiqueta = 'ILP-MAC-00144'),
    'Preventiva',
    'Limpeza de luminaria e reaperto',
    'Plano mensal',
    (SELECT id FROM usuarios WHERE email = 'tecnico1@macapaluz.local'),
    'resolvida',
    '2026-02-20 08:00:00',
    '2026-02-20 11:25:00'
  );

-- Fotos por ponto
INSERT OR IGNORE INTO fotos_ponto (ponto_ilp_id, url_s3, tipo, uploaded_by)
VALUES
  (
    (SELECT id FROM pontos_ilp WHERE etiqueta = 'ILP-MAC-00142'),
    's3://macapaluz/pontos/ILP-MAC-00142/cadastro-1.jpg',
    'cadastro',
    (SELECT id FROM usuarios WHERE email = 'operador@macapaluz.local')
  ),
  (
    (SELECT id FROM pontos_ilp WHERE etiqueta = 'ILP-MAC-00142'),
    's3://macapaluz/pontos/ILP-MAC-00142/streetview-1.jpg',
    'streetview',
    (SELECT id FROM usuarios WHERE email = 'operador@macapaluz.local')
  ),
  (
    (SELECT id FROM pontos_ilp WHERE etiqueta = 'ILP-MAC-00143'),
    's3://macapaluz/pontos/ILP-MAC-00143/cadastro-1.jpg',
    'cadastro',
    (SELECT id FROM usuarios WHERE email = 'operador@macapaluz.local')
  );
