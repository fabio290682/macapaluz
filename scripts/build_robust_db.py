import sqlite3
from pathlib import Path


def run_sql_script(conn, path):
    sql = Path(path).read_text(encoding="utf-8")
    conn.executescript(sql)


def main():
    repo = Path(__file__).resolve().parents[1]
    source_db = repo / "macapaluz.db"
    target_db = repo / "macapaluz_robusto.db"
    schema_path = repo / "database" / "sqlite_schema_robust.sql"
    quality_views_path = repo / "database" / "quality_views.sql"

    if not source_db.exists():
        raise FileNotFoundError(f"Banco origem nao encontrado: {source_db}")
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema robusto nao encontrado: {schema_path}")
    if not quality_views_path.exists():
        raise FileNotFoundError(f"Arquivo de views nao encontrado: {quality_views_path}")
    if target_db.exists():
        target_db.unlink()

    conn = sqlite3.connect(target_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("PRAGMA foreign_keys = ON;")
    run_sql_script(conn, schema_path)

    cur.execute(f"ATTACH DATABASE '{source_db.as_posix()}' AS legacy;")

    cur.execute(
        """
        INSERT INTO bairros (nome, slug, cidade)
        SELECT DISTINCT
          TRIM(bairro) AS nome,
          LOWER(REPLACE(REPLACE(REPLACE(TRIM(bairro), ' ', '-'), '/', '-'), '--', '-')) AS slug,
          'Macapa'
        FROM legacy.pontos_ilp
        WHERE bairro IS NOT NULL AND TRIM(bairro) <> ''
        ORDER BY 1
        """
    )

    cur.execute(
        """
        INSERT INTO usuarios (id, nome, email, senha_hash, perfil, ativo, ultimo_acesso, created_at, updated_at)
        SELECT
          id,
          nome,
          email,
          senha_hash,
          perfil,
          CASE WHEN ativo IN (0, 1) THEN ativo ELSE 1 END,
          ultimo_acesso,
          COALESCE(created_at, CURRENT_TIMESTAMP),
          COALESCE(updated_at, CURRENT_TIMESTAMP)
        FROM legacy.usuarios
        """
    )

    cur.execute(
        """
        INSERT INTO pontos_ilp (
          id, etiqueta, endereco, bairro, bairro_id, cidade, lat, lng,
          tipo_poste, altura, tipo_luminaria, braco, tipo_lampada, potencia,
          status, origem_dado, confianca_dado, deleted_at, created_at, updated_at
        )
        SELECT
          p.id,
          p.etiqueta,
          p.endereco,
          p.bairro,
          b.id,
          COALESCE(p.cidade, 'Macapa'),
          p.lat,
          p.lng,
          p.tipo_poste,
          p.altura,
          p.tipo_luminaria,
          p.braco,
          p.tipo_lampada,
          p.potencia,
          CASE
            WHEN p.status IN ('cadastrado', 'ativo', 'manutencao', 'inativo') THEN p.status
            ELSE 'cadastrado'
          END AS status,
          'migracao',
          1.0,
          NULL,
          COALESCE(p.created_at, CURRENT_TIMESTAMP),
          COALESCE(p.updated_at, CURRENT_TIMESTAMP)
        FROM legacy.pontos_ilp p
        LEFT JOIN bairros b ON b.nome = p.bairro
        """
    )

    cur.execute(
        """
        INSERT INTO ordens_servico (
          id, numero_os, ponto_ilp_id, tipo, descricao, solicitante, tecnico_id,
          status, prioridade, data_abertura, data_resolucao, created_at, updated_at
        )
        SELECT
          os.id,
          os.numero_os,
          os.ponto_ilp_id,
          os.tipo,
          os.descricao,
          os.solicitante,
          os.tecnico_id,
          CASE
            WHEN os.status IN ('aberta', 'em_andamento', 'resolvida', 'cancelada') THEN os.status
            ELSE 'aberta'
          END AS status,
          'media',
          COALESCE(os.data_abertura, CURRENT_TIMESTAMP),
          os.data_resolucao,
          COALESCE(os.created_at, CURRENT_TIMESTAMP),
          COALESCE(os.updated_at, CURRENT_TIMESTAMP)
        FROM legacy.ordens_servico os
        """
    )

    cur.execute(
        """
        INSERT INTO fotos_ponto (id, ponto_ilp_id, url_s3, tipo, uploaded_by, created_at)
        SELECT
          id,
          ponto_ilp_id,
          url_s3,
          CASE WHEN tipo IN ('cadastro', 'streetview') THEN tipo ELSE 'cadastro' END,
          uploaded_by,
          COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM legacy.fotos_ponto
        """
    )

    cur.execute(
        """
        INSERT INTO import_lotes (
          fonte, arquivo, registros_lidos, registros_inseridos, registros_atualizados,
          status, mensagem, started_at, finished_at
        )
        VALUES (
          'legacy_migration',
          ?,
          (SELECT COUNT(*) FROM legacy.pontos_ilp),
          (SELECT COUNT(*) FROM pontos_ilp),
          0,
          'concluido',
          'Migracao inicial para schema robusto',
          CURRENT_TIMESTAMP,
          CURRENT_TIMESTAMP
        )
        """,
        (str(source_db),),
    )

    conn.commit()
    run_sql_script(conn, quality_views_path)
    conn.commit()
    cur.execute("DETACH DATABASE legacy;")

    stats = {}
    for table in ["bairros", "usuarios", "pontos_ilp", "ordens_servico", "fotos_ponto", "ordens_servico_eventos", "pontos_ilp_historico"]:
        cur.execute(f"SELECT COUNT(*) AS total FROM {table}")
        stats[table] = cur.fetchone()["total"]

    conn.close()

    print("BANCO ROBUSTO CRIADO COM SUCESSO")
    print(f"arquivo: {target_db}")
    for table, total in stats.items():
        print(f"- {table}: {total}")


if __name__ == "__main__":
    main()
