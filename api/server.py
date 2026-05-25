import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

API_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from .importer import import_points_to_db, parse_uploaded_file
except ImportError:
    from importer import import_points_to_db, parse_uploaded_file

from scripts.ensure_runtime_db import ensure_db


DEFAULT_DB_PATH = REPO_ROOT / "macapaluz_robusto.db"
DB_ENV = os.getenv("MACAPALUZ_DB_PATH")
DB_PATH = Path(DB_ENV) if DB_ENV else (DEFAULT_DB_PATH if DEFAULT_DB_PATH.exists() else REPO_ROOT / "macapaluz.db")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))
FRONTEND_FILE = os.getenv("MACAPALUZ_FRONTEND_FILE", "macapaluz-v3.html")
SOFTLUZ_FRONTEND_FILE = os.getenv("MACAPALUZ_SOFTLUZ_FILE", "softluz (3).html")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
PUBLIC_API_BASE = os.getenv("MACAPALUZ_API_BASE", "")
SOFTLUZ_RUNTIME_PATH = REPO_ROOT / "data" / "softluz_runtime.json"
APP_ENV = os.getenv("MACAPALUZ_ENV", "development").strip().lower() or "development"
AUTH_SECRET = os.getenv("MACAPALUZ_AUTH_SECRET", "macapaluz-dev-secret")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("MACAPALUZ_CORS_ORIGINS", "").split(",") if origin.strip()]
DEFAULT_PASSWORDS = {
    "admin@macapaluz.local": "Admin@123",
    "gestor@macapaluz.local": "Gestor@123",
    "tecnico1@macapaluz.local": "Tecnico@123",
    "operador@macapaluz.local": "Operador@123",
}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def guess_content_type(path):
    ctype, _ = mimetypes.guess_type(str(path))
    return ctype or "application/octet-stream"


def utcnow_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(password, stored_hash, email=""):
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored_hash.split("$", 3)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
            return hmac.compare_digest(digest.hex(), expected)
        except Exception:
            return False
    if stored_hash.startswith("dev_hash_"):
        expected_password = DEFAULT_PASSWORDS.get(email or "", "123456")
        return password == expected_password
    return False


def sign_token(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_token(token):
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    padded = body + "=" * (-len(body) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception:
        return None


def parse_json_body(handler):
    length = to_int(handler.headers.get("Content-Length"), 0) or 0
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_invalido: objeto esperado")
    return payload


def is_production():
    return APP_ENV in {"prod", "production"}


def auth_secret_is_secure():
    return bool(AUTH_SECRET and AUTH_SECRET != "macapaluz-dev-secret" and len(AUTH_SECRET) >= 32)


def origin_is_allowed(origin):
    if not origin:
        return True
    return origin in CORS_ORIGINS


def runtime_defaults():
    return {
        "medicao": [],
        "estoque": [],
        "garantia": [],
        "aplicados": [],
        "logs": [],
        "appCidadao": [],
        "consumoBairros": [],
        "usuariosExtras": [],
        "config": {
            "municipio": "Macapá - AP",
            "responsavel": "Eng. Carlos Mendes",
            "contrato": "2024/IL-001",
            "tarifa": "0,89",
            "horas": "11",
        },
    }


def load_runtime_data():
    default = runtime_defaults()
    SOFTLUZ_RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SOFTLUZ_RUNTIME_PATH.exists():
        SOFTLUZ_RUNTIME_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    try:
        payload = json.loads(SOFTLUZ_RUNTIME_PATH.read_text(encoding="utf-8"))
    except Exception:
        SOFTLUZ_RUNTIME_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    default.update({k: v for k, v in payload.items() if k in default})
    return default


def save_runtime_data(data):
    SOFTLUZ_RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOFTLUZ_RUNTIME_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "CIPEMAC/1.0"
    PONTO_STATUS = {"cadastrado", "ativo", "manutencao", "inativo"}
    OS_STATUS = {"aberta", "em_andamento", "resolvida", "cancelada"}

    def _send_cors_headers(self):
        origin = (self.headers.get("Origin") or "").strip()
        if origin and origin_is_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _extract_bearer_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def _current_auth_payload(self):
        return decode_token(self._extract_bearer_token())

    def _require_auth(self):
        payload = self._current_auth_payload()
        if not payload or not payload.get("uid"):
            raise PermissionError("auth_required")
        with get_db() as conn:
            user = conn.execute(
                """
                SELECT id, nome, email, perfil, ativo, ultimo_acesso, created_at, updated_at
                FROM usuarios
                WHERE id = ?
                """,
                (payload["uid"],),
            ).fetchone()
        if not user or not user["ativo"]:
            raise PermissionError("auth_required")
        return dict(user)

    def _require_admin(self):
        user = self._require_auth()
        if user.get("perfil") != "admin":
            raise PermissionError("admin_required")
        return user

    def _send_text(self, text, content_type="text/plain; charset=utf-8", status=200):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path):
        target = file_path.resolve()
        root = REPO_ROOT.resolve()
        if root not in [target, *target.parents]:
            return self._send_json({"error": "forbidden"}, status=403)
        if not target.exists():
            return self._send_json({"error": "not_found"}, status=404)
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", guess_content_type(target))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _parse_query(self):
        parsed = urlparse(self.path)
        return parsed.path.rstrip("/") or "/", parse_qs(parsed.query)

    def _extract_id(self, path, base):
        prefix = f"{base}/"
        if not path.startswith(prefix):
            return None
        tail = path[len(prefix):]
        return to_int(tail, None) if tail and "/" not in tail else None

    def _serve_static(self, path):
        if path in {"/", "/app"}:
            return self._send_file(REPO_ROOT / FRONTEND_FILE)
        if path == "/softluz":
            return self._send_file(REPO_ROOT / SOFTLUZ_FRONTEND_FILE)
        if path == "/config.js":
            body = (
                "window.MACAPALUZ_CONFIG_LOADED=true;\n"
                f"window.GOOGLE_MAPS_API_KEY={json.dumps(GOOGLE_MAPS_API_KEY)};\n"
                f"window.MACAPALUZ_API_BASE={json.dumps(PUBLIC_API_BASE)};\n"
                f"window.SOFTLUZ_API_BASE={json.dumps(PUBLIC_API_BASE or '')};\n"
            )
            return self._send_text(body, "application/javascript; charset=utf-8")
        rel = path.lstrip("/")
        allowed = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".ico", ".webp"}
        if rel and Path(rel).suffix.lower() in allowed and (REPO_ROOT / rel).exists():
            return self._send_file(REPO_ROOT / rel)
        return False

    def _normalize_ponto_payload(self, payload, partial=False):
        required = {"etiqueta", "endereco"} if not partial else set()
        data = {}
        for key in required:
            if not payload.get(key):
                raise ValueError(f"campo_obrigatorio: {key}")
        for key in ("etiqueta", "endereco", "bairro", "cidade", "tipo_poste", "tipo_luminaria", "braco", "tipo_lampada", "status"):
            if key in payload:
                value = str(payload.get(key) or "").strip()
                if value:
                    data[key] = value
        for key in ("lat", "lng"):
            if key in payload:
                parsed = to_float(payload.get(key), None)
                if parsed is None and payload.get(key) not in (None, ""):
                    raise ValueError(f"valor_invalido: {key}")
                if parsed is not None:
                    data[key] = parsed
        for key in ("altura", "potencia"):
            if key in payload:
                parsed = to_int(payload.get(key), None)
                if parsed is None and payload.get(key) not in (None, ""):
                    raise ValueError(f"valor_invalido: {key}")
                if parsed is not None:
                    data[key] = parsed
        if data.get("status") and data["status"] not in self.PONTO_STATUS:
            raise ValueError("status_invalido")
        return data

    def _normalize_os_payload(self, payload, partial=False):
        required = {"numero_os", "ponto_ilp_id", "tipo"} if not partial else set()
        data = {}
        for key in required:
            if payload.get(key) in (None, ""):
                raise ValueError(f"campo_obrigatorio: {key}")
        for key in ("numero_os", "tipo", "descricao", "solicitante", "status", "data_resolucao"):
            if key in payload:
                value = str(payload.get(key) or "").strip()
                if value:
                    data[key] = value
        for key in ("ponto_ilp_id", "tecnico_id"):
            if key in payload:
                parsed = to_int(payload.get(key), None)
                if parsed is None and payload.get(key) not in (None, ""):
                    raise ValueError(f"valor_invalido: {key}")
                if parsed is not None:
                    data[key] = parsed
        if data.get("status") and data["status"] not in self.OS_STATUS:
            raise ValueError("status_invalido")
        return data

    def _append_runtime_log(self, modulo, acao, det, user="Sistema", perfil="API"):
        data = load_runtime_data()
        data["logs"].insert(0, {"dt": datetime.now().strftime("%d/%m/%Y %H:%M"), "user": user, "perfil": perfil, "acao": acao, "modulo": modulo, "det": det})
        data["logs"] = data["logs"][:100]
        save_runtime_data(data)

    def _serialize_user(self, row):
        item = dict(row)
        item.pop("senha_hash", None)
        item["ativo"] = bool(item.get("ativo"))
        return item

    def _list_users(self):
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, nome, email, perfil, ativo, ultimo_acesso, created_at, updated_at
                FROM usuarios
                ORDER BY nome COLLATE NOCASE ASC
                """
            ).fetchall()
        return {"items": [self._serialize_user(r) for r in rows]}

    def _create_auth_user(self, payload):
        nome = str(payload.get("nome") or "").strip()
        email = str(payload.get("email") or "").strip().lower()
        senha = str(payload.get("senha") or "").strip()
        perfil = str(payload.get("perfil") or "operador").strip().lower()
        if len(nome) < 3:
            raise ValueError("nome_invalido")
        if "@" not in email:
            raise ValueError("email_invalido")
        if len(senha) < 6:
            raise ValueError("senha_curta")
        if perfil not in {"operador", "tecnico", "gestor", "admin"}:
            raise ValueError("perfil_invalido")
        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash, perfil, ativo)
                VALUES (?, ?, ?, ?, 1)
                """,
                (nome, email, hash_password(senha), perfil),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT id, nome, email, perfil, ativo, ultimo_acesso, created_at, updated_at
                FROM usuarios
                WHERE id = ?
                """,
                (cur.lastrowid,),
            ).fetchone()
        self._append_runtime_log("Administração", "Cadastrou usuário", f"{nome} — {perfil}", user="Sistema", perfil="Admin")
        return self._serialize_user(row)

    def _login_user(self, payload):
        email = str(payload.get("email") or "").strip().lower()
        senha = str(payload.get("senha") or "").strip()
        if "@" not in email:
            raise ValueError("email_invalido")
        if not senha:
            raise ValueError("senha_obrigatoria")
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, nome, email, senha_hash, perfil, ativo, ultimo_acesso, created_at, updated_at
                FROM usuarios
                WHERE lower(email) = lower(?)
                """,
                (email,),
            ).fetchone()
            if not row or not row["ativo"] or not verify_password(senha, row["senha_hash"], row["email"]):
                raise PermissionError("credenciais_invalidas")
            now = utcnow_iso()
            conn.execute("UPDATE usuarios SET ultimo_acesso = ? WHERE id = ?", (now, row["id"]))
            conn.commit()
            user = conn.execute(
                """
                SELECT id, nome, email, perfil, ativo, ultimo_acesso, created_at, updated_at
                FROM usuarios
                WHERE id = ?
                """,
                (row["id"],),
            ).fetchone()
        token = sign_token({"uid": user["id"], "email": user["email"], "perfil": user["perfil"], "iat": utcnow_iso()})
        return {"token": token, "user": self._serialize_user(user)}

    def _fetch_ponto(self, conn, ponto_id):
        row = conn.execute(
            """
            SELECT id, etiqueta, endereco, bairro, cidade, lat, lng, tipo_poste, altura,
                   tipo_luminaria, braco, tipo_lampada, potencia, status
            FROM pontos_ilp
            WHERE id = ?
            """,
            (ponto_id,),
        ).fetchone()
        return dict(row) if row else None

    def _fetch_os(self, conn, os_id):
        row = conn.execute(
            """
            SELECT os.id, os.numero_os, os.ponto_ilp_id, os.tipo, os.descricao, os.solicitante,
                   os.tecnico_id, os.status, os.data_abertura, os.data_resolucao,
                   p.etiqueta AS ponto_etiqueta, p.bairro AS ponto_bairro, p.endereco AS ponto_endereco
            FROM ordens_servico os
            JOIN pontos_ilp p ON p.id = os.ponto_ilp_id
            WHERE os.id = ?
            """,
            (os_id,),
        ).fetchone()
        return dict(row) if row else None

    def _db_summary(self):
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM pontos_ilp) AS total_pontos,
                  (SELECT COUNT(*) FROM pontos_ilp WHERE status IN ('ativo', 'cadastrado')) AS pontos_ativos,
                  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'manutencao') AS pontos_manutencao,
                  (SELECT COUNT(*) FROM pontos_ilp WHERE status = 'inativo') AS pontos_inativos,
                  (SELECT COUNT(*) FROM ordens_servico WHERE status IN ('aberta', 'em_andamento')) AS os_abertas
                """
            ).fetchone()
        return dict(row)

    def _db_points(self, limit=250, offset=0, status=None, bairro=None, search=None, only_map=False):
        where = []
        params = []
        if status:
            where.append("status = ?")
            params.append(status)
        if bairro:
            where.append("bairro = ?")
            params.append(bairro)
        if search:
            where.append("(etiqueta LIKE ? OR endereco LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        if only_map:
            where.extend(["lat IS NOT NULL", "lng IS NOT NULL"])
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with get_db() as conn:
            total = conn.execute(f"SELECT COUNT(*) AS total FROM pontos_ilp {where_sql}", params).fetchone()["total"]
            rows = conn.execute(
                f"""
                SELECT id, etiqueta, endereco, bairro, cidade, lat, lng, tipo_poste, altura,
                       tipo_luminaria, braco, tipo_lampada, potencia, status
                FROM pontos_ilp
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return {"total": total, "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}

    def _db_orders(self, limit=250, offset=0, status=None):
        where = []
        params = []
        if status:
            where.append("os.status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with get_db() as conn:
            total = conn.execute(f"SELECT COUNT(*) AS total FROM ordens_servico os {where_sql}", params).fetchone()["total"]
            rows = conn.execute(
                f"""
                SELECT os.id, os.numero_os, os.tipo, os.descricao, os.solicitante, os.status,
                       os.data_abertura, os.data_resolucao, p.id AS ponto_ilp_id,
                       p.etiqueta AS ponto_etiqueta, p.bairro AS ponto_bairro, p.endereco AS ponto_endereco
                FROM ordens_servico os
                JOIN pontos_ilp p ON p.id = os.ponto_ilp_id
                {where_sql}
                ORDER BY os.data_abertura DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return {"total": total, "limit": limit, "offset": offset, "items": [dict(r) for r in rows]}

    def _quality_summary_items(self):
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT
                  COALESCE(origem_dado, 'manual') AS origem,
                  COUNT(*) AS total,
                  SUM(CASE WHEN bairro IS NULL OR TRIM(bairro) = '' THEN 1 ELSE 0 END) AS sem_bairro,
                  SUM(CASE WHEN tipo_lampada IS NULL OR TRIM(tipo_lampada) = '' THEN 1 ELSE 0 END) AS sem_tipo_lampada,
                  SUM(CASE WHEN potencia IS NULL OR potencia <= 0 THEN 1 ELSE 0 END) AS sem_potencia,
                  SUM(CASE WHEN lat IS NULL OR lng IS NULL THEN 1 ELSE 0 END) AS sem_coordenada
                FROM pontos_ilp
                GROUP BY COALESCE(origem_dado, 'manual')
                ORDER BY total DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def _find_or_create_point_for_softluz(self, conn, payload):
        etiqueta = str(payload.get("etiqueta") or payload.get("ponto") or "").strip()
        endereco = str(payload.get("endereco") or "").strip() or "Endereço não informado"
        bairro = str(payload.get("bairro") or "").strip() or None
        if etiqueta:
            row = conn.execute("SELECT id FROM pontos_ilp WHERE etiqueta = ?", (etiqueta,)).fetchone()
            if row:
                return row["id"]
        if payload.get("lat") not in (None, "") and payload.get("lng") not in (None, ""):
            lat = to_float(payload.get("lat"), None)
            lng = to_float(payload.get("lng"), None)
            if lat is not None and lng is not None:
                row = conn.execute(
                    """
                    SELECT id FROM pontos_ilp
                    WHERE lat IS NOT NULL AND lng IS NOT NULL
                      AND ABS(lat - ?) < 0.0005 AND ABS(lng - ?) < 0.0005
                    LIMIT 1
                    """,
                    (lat, lng),
                ).fetchone()
                if row:
                    return row["id"]
        point_payload = {
            "etiqueta": etiqueta or f"ILP-MAC-{datetime.utcnow().strftime('%H%M%S%f')[:5]}",
            "endereco": endereco,
            "bairro": bairro,
            "cidade": str(payload.get("cidade") or "Macapá"),
            "lat": to_float(payload.get("lat"), None),
            "lng": to_float(payload.get("lng"), None),
            "tipo_poste": str(payload.get("tipo_poste") or "Concreto"),
            "altura": to_int(payload.get("altura"), 9),
            "tipo_luminaria": str(payload.get("tipo_luminaria") or "Fechada"),
            "braco": str(payload.get("braco") or "Simples"),
            "tipo_lampada": str(payload.get("tipo_lampada") or "LED"),
            "potencia": to_int(payload.get("potencia"), 100),
            "status": "cadastrado",
        }
        data = self._normalize_ponto_payload(point_payload, partial=False)
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cur = conn.execute(f"INSERT INTO pontos_ilp ({columns}) VALUES ({placeholders})", list(data.values()))
        return cur.lastrowid

    def _create_point(self, payload):
        data = self._normalize_ponto_payload(payload, partial=False)
        with get_db() as conn:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur = conn.execute(f"INSERT INTO pontos_ilp ({columns}) VALUES ({placeholders})", list(data.values()))
            conn.commit()
            point = self._fetch_ponto(conn, cur.lastrowid)
        self._append_runtime_log("IPCadastro", "Cadastrou ponto", f"{point['etiqueta']} — {point['endereco']}")
        return point

    def _update_point(self, ponto_id, payload):
        data = self._normalize_ponto_payload(payload, partial=True)
        if not data:
            raise ValueError("payload_vazio")
        with get_db() as conn:
            set_sql = ", ".join([f"{k} = ?" for k in data.keys()])
            conn.execute(f"UPDATE pontos_ilp SET {set_sql} WHERE id = ?", [*data.values(), ponto_id])
            conn.commit()
            item = self._fetch_ponto(conn, ponto_id)
        if not item:
            raise ValueError("ponto_nao_encontrado")
        self._append_runtime_log("IPCadastro", "Atualizou ponto", f"{item['etiqueta']} — {item['endereco']}")
        return item

    def _delete_point(self, ponto_id):
        with get_db() as conn:
            conn.execute("DELETE FROM pontos_ilp WHERE id = ?", (ponto_id,))
            conn.commit()
        self._append_runtime_log("IPCadastro", "Excluiu ponto", f"ID {ponto_id}")
        return {"deleted": True, "id": ponto_id}

    def _create_order(self, payload):
        data = self._normalize_os_payload(payload, partial=False)
        with get_db() as conn:
            exists = conn.execute("SELECT id FROM pontos_ilp WHERE id = ?", (data["ponto_ilp_id"],)).fetchone()
            if not exists:
                raise ValueError("ponto_ilp_id_nao_encontrado")
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur = conn.execute(f"INSERT INTO ordens_servico ({columns}) VALUES ({placeholders})", list(data.values()))
            conn.commit()
            item = self._fetch_os(conn, cur.lastrowid)
        self._append_runtime_log("Ordens de Serviço", "Criou OS", f"{item['numero_os']} — {item['ponto_etiqueta']}")
        return item

    def _update_order(self, os_id, payload):
        data = self._normalize_os_payload(payload, partial=True)
        if not data:
            raise ValueError("payload_vazio")
        with get_db() as conn:
            if data.get("ponto_ilp_id") is not None:
                exists = conn.execute("SELECT id FROM pontos_ilp WHERE id = ?", (data["ponto_ilp_id"],)).fetchone()
                if not exists:
                    raise ValueError("ponto_ilp_id_nao_encontrado")
            set_sql = ", ".join([f"{k} = ?" for k in data.keys()])
            conn.execute(f"UPDATE ordens_servico SET {set_sql} WHERE id = ?", [*data.values(), os_id])
            conn.commit()
            item = self._fetch_os(conn, os_id)
        if not item:
            raise ValueError("os_nao_encontrada")
        self._append_runtime_log("Ordens de Serviço", "Atualizou OS", f"{item['numero_os']} — status {item['status']}")
        return item

    def _delete_order(self, os_id):
        with get_db() as conn:
            conn.execute("DELETE FROM ordens_servico WHERE id = ?", (os_id,))
            conn.commit()
        self._append_runtime_log("Ordens de Serviço", "Excluiu OS", f"ID {os_id}")
        return {"deleted": True, "id": os_id}

    def _softluz_bootstrap(self):
        runtime = load_runtime_data()
        summary = self._db_summary()
        points = self._db_points(limit=250)["items"]
        orders = self._db_orders(limit=250)["items"]
        pontos = [
            {
                "id": item["id"],
                "et": item["etiqueta"],
                "end": item["endereco"],
                "bairro": item["bairro"],
                "poste": item["tipo_poste"],
                "alt": f"{item['altura']}m" if item["altura"] else None,
                "lum": item["tipo_luminaria"],
                "braco": item["braco"],
                "lamp": item["tipo_lampada"],
                "pot": f"{item['potencia']}W" if item["potencia"] else None,
                "lat": item["lat"],
                "lng": item["lng"],
                "status": item["status"],
            }
            for item in points
        ]
        ordens = [
            {
                "id": item["numero_os"],
                "dbId": item["id"],
                "end": item["ponto_endereco"],
                "ponto": item["ponto_etiqueta"],
                "tipo": item["tipo"],
                "tec": item["solicitante"] or "Equipe Operacional",
                "data": item["data_abertura"],
                "prev": item["data_resolucao"] or item["data_abertura"],
                "origem": "App Cidadão" if "APP CIDADAO" in str(item["solicitante"]).upper() else "Sistema",
                "status": {"aberta": "aberta", "em_andamento": "andamento", "resolvida": "concluida", "cancelada": "cancelada"}.get(item["status"], item["status"]),
            }
            for item in orders
        ]
        return {
            "summary": summary,
            "ordens": ordens,
            "pontos": pontos,
            "medicao": runtime["medicao"],
            "estoque": runtime["estoque"],
            "garantia": runtime["garantia"],
            "aplicados": runtime["aplicados"],
            "logs": runtime["logs"],
            "appCidadao": runtime["appCidadao"],
            "consumoBairros": runtime["consumoBairros"],
            "usuariosExtras": runtime["usuariosExtras"],
            "config": runtime["config"],
        }

    def _softluz_create_order(self, payload, status_override=None):
        tipo = str(payload.get("tipo") or "").strip()
        if not tipo:
            raise ValueError("campo_obrigatorio: tipo")
        with get_db() as conn:
            ponto_id = self._find_or_create_point_for_softluz(conn, payload)
            numero_os = str(payload.get("numero_os") or f"OS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
            record = {
                "numero_os": numero_os,
                "ponto_ilp_id": ponto_id,
                "tipo": tipo,
                "descricao": str(payload.get("descricao") or "").strip(),
                "solicitante": str(payload.get("origem") or payload.get("solicitante") or "Sistema"),
                "status": status_override or {"aberta": "aberta", "andamento": "em_andamento", "concluida": "resolvida", "cancelada": "cancelada"}.get(str(payload.get("status") or "aberta"), "aberta"),
            }
            data = self._normalize_os_payload(record, partial=False)
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            cur = conn.execute(f"INSERT INTO ordens_servico ({columns}) VALUES ({placeholders})", list(data.values()))
            conn.commit()
            item = self._fetch_os(conn, cur.lastrowid)
        self._append_runtime_log("Ordens de Serviço", "Criou OS", f"{item['numero_os']} — {item['ponto_etiqueta']}", user="Carlos Alberto", perfil="Admin")
        return item

    def _softluz_create_point(self, payload):
        return self._create_point(
            {
                "etiqueta": payload.get("etiqueta") or payload.get("et") or payload.get("ponto"),
                "endereco": payload.get("endereco") or payload.get("end"),
                "bairro": payload.get("bairro"),
                "cidade": payload.get("cidade") or "Macapá",
                "lat": payload.get("lat"),
                "lng": payload.get("lng"),
                "tipo_poste": payload.get("poste") or payload.get("tipo_poste"),
                "altura": str(payload.get("alt") or payload.get("altura") or "9").replace("m", ""),
                "tipo_luminaria": payload.get("lum") or payload.get("tipo_luminaria"),
                "braco": payload.get("braco"),
                "tipo_lampada": payload.get("lamp") or payload.get("tipo_lampada"),
                "potencia": str(payload.get("pot") or payload.get("potencia") or "100").replace("W", ""),
                "status": payload.get("status") or "cadastrado",
            }
        )

    def _softluz_material_entry(self, payload):
        codigo = str(payload.get("cod") or payload.get("codigo") or "").strip()
        descricao = str(payload.get("desc") or payload.get("descricao") or "").strip()
        quantidade = to_int(payload.get("qtd") or payload.get("quantidade"), None)
        if not codigo:
            raise ValueError("campo_obrigatorio: cod")
        if quantidade is None:
            raise ValueError("campo_obrigatorio: qtd")
        runtime = load_runtime_data()
        item = next((row for row in runtime["estoque"] if row["cod"] == codigo), None)
        if item:
            item["qtd"] += quantidade
            item["sit"] = "baixo" if item["qtd"] < item["min"] else "ok"
        else:
            minimo = to_int(payload.get("min"), 50)
            runtime["estoque"].insert(0, {"cod": codigo, "desc": descricao or "Material", "tipo": str(payload.get("tipo") or "Material"), "pot": str(payload.get("pot") or payload.get("potencia") or "-"), "qtd": quantidade, "min": minimo, "sit": "baixo" if quantidade < minimo else "ok"})
        runtime["garantia"].insert(0, {"equip": descricao or "Material", "serie": f"SER-{datetime.utcnow().strftime('%H%M%S%f')[:6]}", "ponto": "Estoque", "inst": datetime.now().strftime("%d/%m/%Y"), "fim": datetime.now().strftime("%d/%m/%Y"), "forn": str(payload.get("fornecedor") or "Fornecedor"), "status": "ativa"})
        save_runtime_data(runtime)
        self._append_runtime_log("Materiais", "Registrou entrada", f"{codigo} — +{quantidade} unidades", user="Carlos Alberto", perfil="Admin")
        return {"ok": True, "estoque": runtime["estoque"][0]}

    def _softluz_save_config(self, payload):
        runtime = load_runtime_data()
        runtime["config"].update({k: v for k, v in payload.items() if k in runtime["config"]})
        save_runtime_data(runtime)
        self._append_runtime_log("Administração", "Salvou configurações", runtime["config"].get("contrato", ""), user="Carlos Alberto", perfil="Admin")
        return {"ok": True, "config": runtime["config"]}

    def _softluz_create_user(self, payload):
        nome = str(payload.get("nome") or "").strip()
        email = str(payload.get("email") or "").strip()
        perfil = str(payload.get("perfil") or "").strip() or "Operador"
        if not nome:
            raise ValueError("campo_obrigatorio: nome")
        if not email:
            raise ValueError("campo_obrigatorio: email")
        runtime = load_runtime_data()
        runtime["usuariosExtras"].insert(0, {"nome": nome, "email": email, "perfil": perfil, "ultimo": "Agora"})
        runtime["usuariosExtras"] = runtime["usuariosExtras"][:50]
        save_runtime_data(runtime)
        self._append_runtime_log("Administração", "Cadastrou usuário", f"{nome} — {perfil}", user="Carlos Alberto", perfil="Admin")
        return {"ok": True, "user": runtime["usuariosExtras"][0]}

    def _create_app_order(self, payload):
        nome = str(payload.get("nome") or "").strip()
        descricao = str(payload.get("descricao") or "").strip()
        if not nome:
            raise ValueError("campo_obrigatorio: nome")
        if not descricao:
            raise ValueError("campo_obrigatorio: descricao")
        body = {
            "ponto": str(payload.get("ponto") or ""),
            "endereco": str(payload.get("endereco") or "Local informado pelo app"),
            "bairro": str(payload.get("bairro") or ""),
            "lat": payload.get("lat"),
            "lng": payload.get("lng"),
            "tipo": "app_cidadao",
            "descricao": descricao,
            "solicitante": f"APP CIDADAO - {nome}" + (f" ({payload.get('telefone')})" if payload.get("telefone") else ""),
            "origem": "App Cidadão",
        }
        result = self._softluz_create_order(body, status_override="aberta")
        runtime = load_runtime_data()
        runtime["appCidadao"].insert(0, {"os": result["numero_os"], "dt": datetime.now().strftime("%d/%m/%Y %H:%M"), "loc": f"{payload.get('lat')}, {payload.get('lng')}", "ponto": result["ponto_etiqueta"], "foto": "📸", "status": "aberta"})
        runtime["appCidadao"] = runtime["appCidadao"][:100]
        save_runtime_data(runtime)
        return {"ok": True, "mensagem": "Solicitação recebida e O.S. aberta com sucesso.", "os": result, "ponto_criado": True}

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
        content = base64.b64decode(content_base64, validate=True)
        points = parse_uploaded_file(filename, content)
        with get_db() as conn:
            stats = import_points_to_db(conn, points, origem_dado=f"upload:{Path(filename).suffix.lower().lstrip('.')}")
            conn.commit()
        self._append_runtime_log("IPCadastro", "Importou arquivo", f"{filename} — {stats.get('inserted', 0)} inseridos")
        return {"ok": True, "filename": filename, "stats": stats}

    def do_OPTIONS(self):
        origin = (self.headers.get("Origin") or "").strip()
        if origin and not origin_is_allowed(origin):
            return self._send_json({"error": "forbidden_origin"}, status=403)
        self._send_json({"ok": True})

    def do_GET(self):
        path, query = self._parse_query()
        try:
            if self._serve_static(path):
                return
            if path == "/auth/me":
                return self._send_json({"user": self._serialize_user(self._require_auth())})
            if path == "/auth/users":
                self._require_admin()
                return self._send_json(self._list_users())
            if path == "/health":
                return self._send_json({"ok": True, "service": "cipemac-api", "db_path": str(DB_PATH), "frontend_file": FRONTEND_FILE, "softluz_file": SOFTLUZ_FRONTEND_FILE})
            if path == "/dashboard/summary":
                return self._send_json(self._db_summary())
            if path == "/qualidade/summary":
                return self._send_json({"items": self._quality_summary_items()})
            if path == "/pontos-ilp":
                return self._send_json(self._db_points(limit=min(to_int(query.get("limit", ["100"])[0], 100), 500), offset=max(to_int(query.get("offset", ["0"])[0], 0), 0), status=query.get("status", [None])[0], bairro=query.get("bairro", [None])[0], search=query.get("search", [None])[0]))
            if path == "/pontos-ilp/map":
                data = self._db_points(limit=min(to_int(query.get("limit", ["5000"])[0], 5000), 20000), only_map=True, status=query.get("status", [None])[0], bairro=query.get("bairro", [None])[0])
                return self._send_json({"total": data["total"], "limit": data["limit"], "items": [{"id": r["id"], "etiqueta": r["etiqueta"], "lat": r["lat"], "lng": r["lng"], "status": r["status"], "bairro": r["bairro"], "tipo_lampada": r["tipo_lampada"], "potencia": r["potencia"]} for r in data["items"]]})
            if path == "/ordens-servico":
                return self._send_json(self._db_orders(limit=min(to_int(query.get("limit", ["100"])[0], 100), 500), offset=max(to_int(query.get("offset", ["0"])[0], 0), 0), status=query.get("status", [None])[0]))
            if path == "/softluz/bootstrap":
                return self._send_json(self._softluz_bootstrap())
            ponto_id = self._extract_id(path, "/pontos-ilp")
            if ponto_id is not None:
                with get_db() as conn:
                    item = self._fetch_ponto(conn, ponto_id)
                return self._send_json(item if item else {"error": "not_found"}, status=200 if item else 404)
            os_id = self._extract_id(path, "/ordens-servico")
            if os_id is not None:
                with get_db() as conn:
                    item = self._fetch_os(conn, os_id)
                return self._send_json(item if item else {"error": "not_found"}, status=200 if item else 404)
            return self._send_json({"error": "not_found"}, status=404)
        except ValueError as exc:
            return self._send_json({"error": "bad_request", "message": str(exc)}, status=400)
        except PermissionError as exc:
            return self._send_json({"error": "unauthorized", "message": str(exc)}, status=401 if str(exc) == "auth_required" else 403)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def do_POST(self):
        path, _ = self._parse_query()
        try:
            payload = parse_json_body(self)
            if path == "/auth/login":
                return self._send_json(self._login_user(payload), status=200)
            if path == "/auth/register":
                self._require_admin()
                return self._send_json({"user": self._create_auth_user(payload)}, status=201)
            if path == "/pontos-ilp":
                self._require_auth()
                return self._send_json(self._create_point(payload), status=201)
            if path == "/ordens-servico":
                self._require_auth()
                return self._send_json(self._create_order(payload), status=201)
            if path == "/app-cidadao/solicitacoes":
                return self._send_json(self._create_app_order(payload), status=201)
            if path == "/import/file":
                self._require_admin()
                return self._send_json(self._import_file(payload), status=201)
            if path == "/softluz/ordens-servico":
                self._require_auth()
                return self._send_json(self._softluz_create_order(payload), status=201)
            if path == "/softluz/pontos-ilp":
                self._require_auth()
                return self._send_json(self._softluz_create_point(payload), status=201)
            if path == "/softluz/materials/entrada":
                self._require_auth()
                return self._send_json(self._softluz_material_entry(payload), status=201)
            if path == "/softluz/config":
                self._require_admin()
                return self._send_json(self._softluz_save_config(payload), status=200)
            if path == "/softluz/usuarios":
                self._require_admin()
                return self._send_json(self._softluz_create_user(payload), status=201)
            return self._send_json({"error": "not_found"}, status=404)
        except ValueError as exc:
            return self._send_json({"error": "bad_request", "message": str(exc)}, status=400)
        except PermissionError as exc:
            code = 401 if str(exc) in {"auth_required", "credenciais_invalidas"} else 403
            return self._send_json({"error": "unauthorized", "message": str(exc)}, status=code)
        except sqlite3.IntegrityError as exc:
            return self._send_json({"error": "integrity_error", "message": str(exc)}, status=409)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def do_PUT(self):
        path, _ = self._parse_query()
        try:
            self._require_auth()
            payload = parse_json_body(self)
            ponto_id = self._extract_id(path, "/pontos-ilp")
            if ponto_id is not None:
                return self._send_json(self._update_point(ponto_id, payload))
            os_id = self._extract_id(path, "/ordens-servico")
            if os_id is not None:
                return self._send_json(self._update_order(os_id, payload))
            return self._send_json({"error": "not_found"}, status=404)
        except ValueError as exc:
            return self._send_json({"error": "bad_request", "message": str(exc)}, status=400)
        except PermissionError as exc:
            code = 401 if str(exc) in {"auth_required", "credenciais_invalidas"} else 403
            return self._send_json({"error": "unauthorized", "message": str(exc)}, status=code)
        except sqlite3.IntegrityError as exc:
            return self._send_json({"error": "integrity_error", "message": str(exc)}, status=409)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)

    def do_DELETE(self):
        path, _ = self._parse_query()
        try:
            self._require_auth()
            ponto_id = self._extract_id(path, "/pontos-ilp")
            if ponto_id is not None:
                return self._send_json(self._delete_point(ponto_id))
            os_id = self._extract_id(path, "/ordens-servico")
            if os_id is not None:
                return self._send_json(self._delete_order(os_id))
            return self._send_json({"error": "not_found"}, status=404)
        except PermissionError as exc:
            code = 401 if str(exc) in {"auth_required", "credenciais_invalidas"} else 403
            return self._send_json({"error": "unauthorized", "message": str(exc)}, status=code)
        except sqlite3.IntegrityError as exc:
            return self._send_json({"error": "integrity_error", "message": str(exc)}, status=409)
        except Exception as exc:
            return self._send_json({"error": "internal_error", "message": str(exc)}, status=500)


def run():
    if is_production() and not auth_secret_is_secure():
        raise RuntimeError("MACAPALUZ_AUTH_SECRET deve ser definido com pelo menos 32 caracteres em producao")
    ensure_db()
    load_runtime_data()
    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"CIPEMAC API em http://{HOST}:{PORT}")
    print(f"Banco: {DB_PATH}")
    print(f"Frontend: {REPO_ROOT / FRONTEND_FILE}")
    print(f"Softluz: {REPO_ROOT / SOFTLUZ_FRONTEND_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    run()
