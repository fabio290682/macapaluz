import json
import mimetypes
import os
import sqlite3
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from importer import import_points_to_db, parse_uploaded_file


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "macapaluz_robusto.db"
DB_PATH = Path(os.getenv("MACAPALUZ_DB_PATH", str(DEFAULT_DB_PATH)))
if not DB_PATH.exists():
    DB_PATH = REPO_ROOT / "macapaluz.db"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))
FRONTEND_FILE = os.getenv("MACAPALUZ_FRONTEND_FILE", "macapaluz-v3.html")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
PUBLIC_API_BASE = os.getenv("MACAPALUZ_API_BASE", "")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def guess_content_type(path):
    ctype, _ = mimetypes.guess_type(str(path))
    return ctype or "application/octet-stream"


class ApiHandler(BaseHTTPRequestHandler):
    PONTO_STATUS = {"cadastrado", "ativo", "manutencao", "inativo"}
    OS_STATUS = {"aberta", "em_andamento", "resolvida", "cancelada"}

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path):
        target = file_path.resolve()
        root = REPO_ROOT.resolve()
        if root not in [target, *target.parents]:
            self._send_json({"error": "forbidden"}, status=403)
            return True
        if not target.exists() or not target.is_file():
            self._send_json({"error": "not_found"}, status=404)
            return True
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", guess_content_type(target))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        return True

    def _serve_static(self, path):
        if path in {"/", "/app"}:
            return self._send_file(REPO_ROOT / FRONTEND_FILE)
        if path == "/config.js":
            # Exposicao controlada apenas da chave publica de mapas para o frontend.
            body = (
                f"window.GOOGLE_MAPS_API_KEY={json.dumps(GOOGLE_MAPS_API_KEY)};\n"
                f"window.MACAPALUZ_API_BASE={json.dumps(PUBLIC_API_BASE)};"
            )
            self._send_text(body, content_type="application/javascript; charset=utf-8")
            return True

        rel = path.lstrip("/")
        if not rel:
            return False
        ext = Path(rel).suffix.lower()
        allowed = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".ico", ".webp"}
        if ext not in allowed:
            return False
        target = REPO_ROOT / rel
        if target.exists():
            return self._send_file(target)
        return False

    def _parse_query(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        return path, parse_qs(parsed.query)

    def _extract_id(self, path, base_path):
        if not path.startswith(f"{base_path}/"):
            return None
        tail = path[len(base_path) + 1 :]
        if not tail or "/" in tail:
            return None
        return to_int(tail, None)

    def _parse_body(self):
        length = to_int(self.headers.get("Content-Length"), 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"json_invalido: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError("json_invalido: objeto esperado")
        return payload

    def _normalize_ponto_payload(self, payload, partial=False):
        allowed = {
            "etiqueta": str,
            "endereco": str,
            "bairro": str,
            "cidade": str,
            "lat": float,
            "lng": float,
            "tipo_poste": str,
            "altura": int,
            "tipo_luminaria": str,
            "braco": str,
            "tipo_lampada": str,
            "potencia": int,
            "status": str,
        }
        required = {"etiqueta", "endereco"} if not partial else set()
        data = {}

        for key in required:
            if key not in payload:
                raise ValueError(f"campo_obrigatorio: {key}")

        for key, value in payload.items():
            if key not in allowed:
                continue
            if value is None:
                data[key] = None
                continue
            if key in {"lat", "lng"}:
                parsed = to_float(value)
                if parsed is None:
                    raise ValueError(f"valor_invalido: {key}")
                data[key] = parsed
            elif key in {"altura", "potencia"}:
                parsed = to_int(value, None)
                if parsed is None:
                    raise ValueError(f"valor_invalido: {key}")
                data[key] = parsed
            else:
                data[key] = str(value).strip()

        for key in {"etiqueta", "endereco"}:
            if key in data and not data[key]:
                raise ValueError(f"campo_vazio: {key}")

        lat = data.get("lat")
        lng = data.get("lng")
        if lat is not None and not (-90 <= lat <= 90):
            raise ValueError("valor_invalido: lat")
        if lng is not None and not (-180 <= lng <= 180):
            raise ValueError("valor_invalido: lng")

        status = data.get("status")
        if status and status not in self.PONTO_STATUS:
            raise ValueError("status_invalido")
        return data

    def _normalize_os_payload(self, payload, partial=False):
        allowed = {
            "numero_os": str,
            "ponto_ilp_id": int,
            "tipo": str,
            "descricao": str,
            "solicitante": str,
            "tecnico_id": int,
            "status": str,
            "data_resolucao": str,
        }
        required = {"numero_os", "ponto_ilp_id", "tipo"} if not partial else set()
        data = {}

        for key in required:
            if key not in payload:
                raise ValueError(f"campo_obrigatorio: {key}")

        for key, value in payload.items():
            if key not in allowed:
                continue
            if value is None:
                data[key] = None
                continue
            if key in {"ponto_ilp_id", "tecnico_id"}:
                parsed = to_int(value, None)
                if parsed is None:
                    raise ValueError(f"valor_invalido: {key}")
                data[key] = parsed
            else:
                data[key] = str(value).strip()

        for key in {"numero_os", "tipo"}:
            if key in data and not data[key]:
                raise ValueError(f"campo_vazio: {key}")

        status = data.get("status")
        if status and status not in self.OS_STATUS:
            raise ValueError("status_invalido")
        return data

    def _fetch_ponto_by_id(self, conn, ponto_id):
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, etiqueta, endereco, bairro, cidade, lat, lng, tipo_lampada, potencia, status
            FROM pontos_ilp
            WHERE id = ?
            """,
            (ponto_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def _fetch_os_by_id(self, conn, os_id):
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              os.id,
              os.numero_os,
              os.ponto_ilp_id,
              os.tipo,
              os.descricao,
              os.solicitante,
              os.tecnico_id,
              os.status,
              os.data_abertura,
              os.data_resolucao,
              p.etiqueta AS ponto_etiqueta,
              p.bairro AS ponto_bairro
            FROM ordens_servico os
            JOIN pontos_ilp p ON p.id = os.ponto_ilp_id
            WHERE os.id = ?
            """,
            (os_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def do_OPTIONS(self):
        self._send_json({"ok": True}, status=200)

    def do_GET(self):
        path, query = self._parse_query()
        try:
            if self._serve_static(path):
                return
            ponto_id = self._extract_id(path, "/pontos-ilp")
            os_id = self._extract_id(path, "/ordens-servico")
            if path == "/health":
                return self._send_json(
                    {
                        "ok": True,
                        "service": "macapaluz-api",
                        "db_path": str(DB_PATH),
                        "frontend_file": FRONTEND_FILE,
                    }
                )
            if path == "/dashboard/summary":
                return self._dashboard_summary()
            if path == "/pontos-ilp":
                return self._pontos_ilp(query)
            if ponto_id is not None:
                return self._ponto_ilp_by_id(ponto_id)
            if path == "/pontos-ilp/map":
                return self._pontos_ilp_map(query)
            if path == "/ordens-servico":
                return self._ordens_servico(query)
            if os_id is not None:
                return self._ordem_servico_by_id(os_id)
            if path == "/qualidade/summary":
                return self._qualidade_summary()
            return self._send_json({"error": "not_found"}, status=404)
        except ValueError as exc:
            return self._send_json({"error": "bad_request", "message": str(exc)}, status=400)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def do_POST(self):
        path, _ = self._parse_query()
        try:
            payload = self._parse_body()
            if path == "/pontos-ilp":
                return self._create_ponto_ilp(payload)
            if path == "/ordens-servico":
                return self._create_ordem_servico(payload)
            if path == "/import/file":
                return self._import_file(payload)
            return self._send_json({"error": "not_found"}, status=404)
        except ValueError as exc:
            return self._send_json({"error": "bad_request", "message": str(exc)}, status=400)
        except sqlite3.IntegrityError as exc:
            return self._send_json({"error": "integrity_error", "message": str(exc)}, status=409)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def do_PUT(self):
        path, _ = self._parse_query()
        try:
            payload = self._parse_body()
            ponto_id = self._extract_id(path, "/pontos-ilp")
            os_id = self._extract_id(path, "/ordens-servico")
            if ponto_id is not None:
                return self._update_ponto_ilp(ponto_id, payload)
            if os_id is not None:
                return self._update_ordem_servico(os_id, payload)
            return self._send_json({"error": "not_found"}, status=404)
        except ValueError as exc:
            return self._send_json({"error": "bad_request", "message": str(exc)}, status=400)
        except sqlite3.IntegrityError as exc:
            return self._send_json({"error": "integrity_error", "message": str(exc)}, status=409)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def do_DELETE(self):
        path, _ = self._parse_query()
        try:
            ponto_id = self._extract_id(path, "/pontos-ilp")
            os_id = self._extract_id(path, "/ordens-servico")
            if ponto_id is not None:
                return self._delete_ponto_ilp(ponto_id)
            if os_id is not None:
                return self._delete_ordem_servico(os_id)
            return self._send_json({"error": "not_found"}, status=404)
        except sqlite3.IntegrityError as exc:
            return self._send_json({"error": "integrity_error", "message": str(exc)}, status=409)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def _dashboard_summary(self):
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM pontos_ilp) AS total_pontos,
                  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'ativo') AS pontos_ativos,
                  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'manutencao') AS pontos_manutencao,
                  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'inativo') AS pontos_inativos,
                  (SELECT COUNT(*) FROM ordens_servico WHERE status IN ('aberta', 'em_andamento')) AS os_abertas
                """
            )
            row = dict(cur.fetchone())
            return self._send_json(row)

    def _pontos_ilp(self, query):
        limit = min(max(to_int(query.get("limit", ["100"])[0], 100), 1), 500)
        offset = max(to_int(query.get("offset", ["0"])[0], 0), 0)
        bairro = query.get("bairro", [None])[0]
        status = query.get("status", [None])[0]
        search = query.get("search", [None])[0]
        min_lat = to_float(query.get("min_lat", [None])[0])
        min_lng = to_float(query.get("min_lng", [None])[0])
        max_lat = to_float(query.get("max_lat", [None])[0])
        max_lng = to_float(query.get("max_lng", [None])[0])

        where = []
        params = []
        if bairro:
            where.append("bairro = ?")
            params.append(bairro)
        if status:
            where.append("status = ?")
            params.append(status)
        if search:
            where.append("(etiqueta LIKE ? OR endereco LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        if None not in (min_lat, min_lng, max_lat, max_lng):
            where.append("(lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?)")
            params.extend([min_lat, max_lat, min_lng, max_lng])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) AS total FROM pontos_ilp {where_sql}", params)
            total = cur.fetchone()["total"]

            cur.execute(
                f"""
                SELECT id, etiqueta, endereco, bairro, cidade, lat, lng, tipo_lampada, potencia, status
                FROM pontos_ilp
                {where_sql}
                ORDER BY id
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            items = [dict(r) for r in cur.fetchall()]

        return self._send_json({"total": total, "limit": limit, "offset": offset, "items": items})

    def _ordens_servico(self, query):
        limit = min(max(to_int(query.get("limit", ["100"])[0], 100), 1), 500)
        offset = max(to_int(query.get("offset", ["0"])[0], 0), 0)
        status = query.get("status", [None])[0]

        where = []
        params = []
        if status:
            where.append("os.status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) AS total FROM ordens_servico os {where_sql}", params)
            total = cur.fetchone()["total"]

            cur.execute(
                f"""
                SELECT
                  os.id,
                  os.numero_os,
                  os.tipo,
                  os.descricao,
                  os.solicitante,
                  os.status,
                  os.data_abertura,
                  os.data_resolucao,
                  p.etiqueta AS ponto_etiqueta,
                  p.bairro AS ponto_bairro
                FROM ordens_servico os
                JOIN pontos_ilp p ON p.id = os.ponto_ilp_id
                {where_sql}
                ORDER BY os.data_abertura DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            items = [dict(r) for r in cur.fetchall()]

        return self._send_json({"total": total, "limit": limit, "offset": offset, "items": items})

    def _pontos_ilp_map(self, query):
        limit = min(max(to_int(query.get("limit", ["5000"])[0], 5000), 1), 20000)
        min_lat = to_float(query.get("min_lat", [None])[0])
        min_lng = to_float(query.get("min_lng", [None])[0])
        max_lat = to_float(query.get("max_lat", [None])[0])
        max_lng = to_float(query.get("max_lng", [None])[0])
        status = query.get("status", [None])[0]

        where = ["lat IS NOT NULL", "lng IS NOT NULL"]
        params = []
        if status:
            where.append("status = ?")
            params.append(status)
        if None not in (min_lat, min_lng, max_lat, max_lng):
            where.append("(lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?)")
            params.extend([min_lat, max_lat, min_lng, max_lng])
        where_sql = f"WHERE {' AND '.join(where)}"

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) AS total FROM pontos_ilp {where_sql}", params)
            total = cur.fetchone()["total"]
            cur.execute(
                f"""
                SELECT id, etiqueta, lat, lng, status, bairro, tipo_lampada, potencia
                FROM pontos_ilp
                {where_sql}
                ORDER BY id
                LIMIT ?
                """,
                [*params, limit],
            )
            items = [dict(r) for r in cur.fetchall()]
        return self._send_json({"total": total, "limit": limit, "items": items})

    def _ponto_ilp_by_id(self, ponto_id):
        if ponto_id is None:
            return self._send_json({"error": "bad_request", "message": "id_invalido"}, status=400)
        with get_db() as conn:
            item = self._fetch_ponto_by_id(conn, ponto_id)
            if not item:
                return self._send_json({"error": "not_found"}, status=404)
            return self._send_json(item)

    def _create_ponto_ilp(self, payload):
        data = self._normalize_ponto_payload(payload, partial=False)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = list(data.values())

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO pontos_ilp ({columns}) VALUES ({placeholders})",
                values,
            )
            ponto_id = cur.lastrowid
            conn.commit()
            item = self._fetch_ponto_by_id(conn, ponto_id)
        return self._send_json(item, status=201)

    def _update_ponto_ilp(self, ponto_id, payload):
        if ponto_id is None:
            return self._send_json({"error": "bad_request", "message": "id_invalido"}, status=400)
        data = self._normalize_ponto_payload(payload, partial=True)
        if not data:
            raise ValueError("payload_vazio")
        set_sql = ", ".join([f"{k} = ?" for k in data.keys()])
        values = [*data.values(), ponto_id]

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"UPDATE pontos_ilp SET {set_sql} WHERE id = ?", values)
            if cur.rowcount == 0:
                return self._send_json({"error": "not_found"}, status=404)
            conn.commit()
            item = self._fetch_ponto_by_id(conn, ponto_id)
        return self._send_json(item)

    def _delete_ponto_ilp(self, ponto_id):
        if ponto_id is None:
            return self._send_json({"error": "bad_request", "message": "id_invalido"}, status=400)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM pontos_ilp WHERE id = ?", (ponto_id,))
            if cur.rowcount == 0:
                return self._send_json({"error": "not_found"}, status=404)
            conn.commit()
        return self._send_json({"deleted": True, "id": ponto_id})

    def _ordem_servico_by_id(self, os_id):
        if os_id is None:
            return self._send_json({"error": "bad_request", "message": "id_invalido"}, status=400)
        with get_db() as conn:
            item = self._fetch_os_by_id(conn, os_id)
            if not item:
                return self._send_json({"error": "not_found"}, status=404)
            return self._send_json(item)

    def _create_ordem_servico(self, payload):
        data = self._normalize_os_payload(payload, partial=False)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM pontos_ilp WHERE id = ?", (data["ponto_ilp_id"],))
            if not cur.fetchone():
                raise ValueError("ponto_ilp_id_nao_encontrado")

            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur.execute(
                f"INSERT INTO ordens_servico ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            os_id = cur.lastrowid
            conn.commit()
            item = self._fetch_os_by_id(conn, os_id)
        return self._send_json(item, status=201)

    def _update_ordem_servico(self, os_id, payload):
        if os_id is None:
            return self._send_json({"error": "bad_request", "message": "id_invalido"}, status=400)
        data = self._normalize_os_payload(payload, partial=True)
        if not data:
            raise ValueError("payload_vazio")
        with get_db() as conn:
            cur = conn.cursor()
            if "ponto_ilp_id" in data:
                cur.execute("SELECT id FROM pontos_ilp WHERE id = ?", (data["ponto_ilp_id"],))
                if not cur.fetchone():
                    raise ValueError("ponto_ilp_id_nao_encontrado")
            set_sql = ", ".join([f"{k} = ?" for k in data.keys()])
            values = [*data.values(), os_id]
            cur.execute(f"UPDATE ordens_servico SET {set_sql} WHERE id = ?", values)
            if cur.rowcount == 0:
                return self._send_json({"error": "not_found"}, status=404)
            conn.commit()
            item = self._fetch_os_by_id(conn, os_id)
        return self._send_json(item)

    def _delete_ordem_servico(self, os_id):
        if os_id is None:
            return self._send_json({"error": "bad_request", "message": "id_invalido"}, status=400)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM ordens_servico WHERE id = ?", (os_id,))
            if cur.rowcount == 0:
                return self._send_json({"error": "not_found"}, status=404)
            conn.commit()
        return self._send_json({"deleted": True, "id": os_id})

    def _qualidade_summary(self):
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_pontos_qualidade_resumo'")
            has_view = cur.fetchone() is not None
            if has_view:
                cur.execute(
                    """
                    SELECT origem, total, sem_bairro, sem_tipo_lampada, sem_potencia, sem_coordenada
                    FROM vw_pontos_qualidade_resumo
                    ORDER BY total DESC
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                      CASE
                        WHEN etiqueta LIKE 'SELT-%' THEN 'kmz_selt'
                        WHEN etiqueta LIKE 'BASE09-%' THEN 'xlsx_base09'
                        WHEN etiqueta LIKE 'KMZ-%' THEN 'kmz_bairro'
                        WHEN etiqueta LIKE 'ILP-MAC-%' THEN 'seed_local'
                        ELSE 'outros'
                      END AS origem,
                      COUNT(*) AS total,
                      SUM(CASE WHEN bairro IS NULL OR TRIM(bairro) = '' THEN 1 ELSE 0 END) AS sem_bairro,
                      SUM(CASE WHEN tipo_lampada IS NULL OR TRIM(tipo_lampada) = '' THEN 1 ELSE 0 END) AS sem_tipo_lampada,
                      SUM(CASE WHEN potencia IS NULL OR potencia <= 0 THEN 1 ELSE 0 END) AS sem_potencia,
                      SUM(CASE WHEN lat IS NULL OR lng IS NULL THEN 1 ELSE 0 END) AS sem_coordenada
                    FROM pontos_ilp
                    GROUP BY origem
                    ORDER BY total DESC
                    """
                )
            items = [dict(r) for r in cur.fetchall()]
        return self._send_json({"items": items})

    def _import_file(self, payload):
        filename = str(payload.get("filename") or "").strip()
        content_base64 = str(payload.get("content_base64") or "").strip()
        import_type = str(payload.get("import_type") or "pontos").strip().lower()
        if not filename:
            raise ValueError("campo_obrigatorio: filename")
        if not content_base64:
            raise ValueError("campo_obrigatorio: content_base64")
        if import_type != "pontos":
            raise ValueError("tipo_importacao_nao_suportado")

        try:
            content = base64.b64decode(content_base64, validate=True)
        except Exception as exc:
            raise ValueError("arquivo_base64_invalido") from exc

        points = parse_uploaded_file(filename, content)
        if not points:
            return self._send_json({"ok": True, "filename": filename, "stats": {"read": 0, "inserted": 0, "updated": 0}})

        with get_db() as conn:
            stats = import_points_to_db(conn, points, origem_dado=f"upload:{Path(filename).suffix.lower().lstrip('.')}")
            conn.commit()
        return self._send_json({"ok": True, "filename": filename, "stats": stats}, status=201)


def run():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco nao encontrado: {DB_PATH}")
    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"MacapaLuz API em http://{HOST}:{PORT}")
    print(f"Banco: {DB_PATH}")
    print(f"Frontend: {REPO_ROOT / FRONTEND_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    run()
