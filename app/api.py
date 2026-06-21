from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from threading import RLock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .database import connect, init_db, seed_db
from .logging_config import configure_logging
from .scheduler import iniciar_recalculo_periodico
from .services import AcademicService, AppError, AuthService, MotorIA

logger = logging.getLogger("sigma.api")


RouteHandler = Callable[[dict[str, str], dict[str, Any], dict[str, str]], tuple[int, Any]]

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
STATIC_MOUNT = "/app"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Application:
    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self.conn = conn if conn is not None else connect()
        init_db(self.conn)
        seed_db(self.conn)
        self.auth = AuthService(self.conn)
        self.academic = AcademicService(self.conn, MotorIA())
        self.lock = RLock()
        self.routes: list[tuple[str, re.Pattern[str], RouteHandler, bool]] = []
        self._register_routes()

    def _register_routes(self) -> None:
        self.add("GET", r"^/$", self.home, public=True)
        self.add("GET", r"^/health$", self.health, public=True)
        self.add("POST", r"^/auth/login$", self.login, public=True)
        self.add("POST", r"^/auth/logout$", self.logout, public=True)
        self.add("GET", r"^/usuarios$", self.usuarios)
        self.add("POST", r"^/usuarios$", self.criar_usuario)
        self.add("PATCH", r"^/usuarios/(?P<usuario_id>\d+)$", self.atualizar_usuario)
        self.add("DELETE", r"^/usuarios/(?P<usuario_id>\d+)$", self.desativar_usuario)
        self.add("GET", r"^/materias$", self.materias)
        self.add("POST", r"^/materias$", self.criar_materia)
        self.add("PATCH", r"^/materias/(?P<materia_id>\d+)$", self.atualizar_materia)
        self.add("DELETE", r"^/materias/(?P<materia_id>\d+)$", self.desativar_materia)
        self.add("GET", r"^/alunos$", self.alunos)
        self.add("POST", r"^/alunos$", self.criar_aluno)
        self.add("POST", r"^/alunos/importar$", self.importar_alunos)
        self.add("GET", r"^/alunos/(?P<aluno_id>\d+)$", self.aluno)
        self.add("PATCH", r"^/alunos/(?P<aluno_id>\d+)$", self.atualizar_aluno)
        self.add("DELETE", r"^/alunos/(?P<aluno_id>\d+)$", self.desativar_aluno)
        self.add("POST", r"^/alunos/(?P<aluno_id>\d+)/materias/(?P<materia_id>\d+)$", self.vincular_materia)
        self.add("POST", r"^/alunos/(?P<aluno_id>\d+)/desempenhos$", self.registrar_desempenho)
        self.add("GET", r"^/alunos/(?P<aluno_id>\d+)/intervencoes$", self.listar_intervencoes)
        self.add("POST", r"^/alunos/(?P<aluno_id>\d+)/intervencoes$", self.registrar_intervencao)
        self.add("PATCH", r"^/intervencoes/(?P<intervencao_id>\d+)$", self.atualizar_intervencao)
        self.add("POST", r"^/analises/recalcular$", self.recalcular_riscos)
        self.add("GET", r"^/dashboard$", self.dashboard)
        self.add(
            "GET",
            r"^/dashboard/aluno/(?P<aluno_id>\d+)$",
            self.dashboard_individual
        )
        self.add("GET", r"^/alertas$", self.alertas)
        self.add("GET", r"^/relatorios$", self.relatorios)
        self.add("POST", r"^/relatorios$", self.criar_relatorio)
        self.add("GET", r"^/auditoria$", self.auditoria)
        self.add("GET", r"^/config/risco$", self.obter_config_risco)
        self.add("PATCH", r"^/config/risco$", self.atualizar_config_risco)
        self.add("POST", r"^/auth/senha$", self.alterar_senha)
        self.add("GET", r"^/materias/comparativo$", self.comparativo_materias)

    def add(self, method: str, pattern: str, handler: RouteHandler, public: bool = False) -> None:
        self.routes.append((method, re.compile(pattern), handler, public))

    def dispatch(self, method: str, path: str, body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        with self.lock:
            for route_method, pattern, handler, public in self.routes:
                if route_method != method:
                    continue
                match = pattern.match(path)
                if not match:
                    continue
                user = self.auth.current_user(headers.get("authorization"))
                if not public and not user:
                    raise AppError("Autenticacao obrigatoria.", 401)
                body["_current_user"] = user
                return handler(match.groupdict(), body, headers)
        raise AppError("Rota nao encontrada.", 404)

    def health(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, {"status": "ok", "service": "gestao-desempenho-estudantil"}

    def home(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, {
            "mensagem": "Backend do Sistema de Gestao do Desempenho Estudantil",
            "status": "online",
            "frontend": f"GET {STATIC_MOUNT}/",
            "autenticacao": {
                "endpoint": "POST /auth/login",
                "logout": "POST /auth/logout",
                "usuarios_demo": [
                    {"email": "professor@sigma.edu", "senha": "professor123"},
                    {"email": "gestor@sigma.edu", "senha": "gestor123"},
                ],
            },
            "endpoints_publicos": ["GET /", "GET /health", "POST /auth/login", "POST /auth/logout"],
            "endpoints_autenticados": [
                "GET /dashboard",
                "GET /dashboard/aluno/{aluno_id}",
                "GET /alunos?page=&page_size=&termo=&risco=&materia_id=",
                "POST /alunos/importar (CSV no campo 'csv', somente gestor)",
                "PATCH /alunos/{aluno_id}",
                "DELETE /alunos/{aluno_id}",
                "GET /usuarios",
                "PATCH /usuarios/{usuario_id}",
                "DELETE /usuarios/{usuario_id}",
                "GET /materias",
                "PATCH /materias/{materia_id}",
                "DELETE /materias/{materia_id}",
                "GET /alertas",
                "GET /relatorios",
                "GET /auditoria?page=&page_size= (somente gestor)",
                "POST /alunos/{aluno_id}/desempenhos",
                "POST /analises/recalcular",
                "GET /alunos/{aluno_id}/intervencoes",
                "POST /alunos/{aluno_id}/intervencoes",
                "PATCH /intervencoes/{intervencao_id}",
                "GET /config/risco",
                "PATCH /config/risco (somente gestor)",
                "POST /auth/senha",
                "GET /materias/comparativo (somente gestor)",
            ],
        }

    def login(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.auth.login(str(body.get("email", "")), str(body.get("senha", "")))

    def logout(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        self.auth.logout(headers.get("authorization"))
        return 200, {"mensagem": "Sessao finalizada."}

    def usuarios(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_usuarios()

    def criar_usuario(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 201, self.academic.criar_usuario(body, ator=body.get("_current_user"))

    def atualizar_usuario(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.atualizar_usuario(int(params["usuario_id"]), body, ator=body.get("_current_user"))

    def desativar_usuario(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.desativar_usuario(int(params["usuario_id"]), ator=body.get("_current_user"))

    def materias(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_materias()

    def criar_materia(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 201, self.academic.criar_materia(body, ator=body.get("_current_user"))

    def atualizar_materia(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.atualizar_materia(int(params["materia_id"]), body, ator=body.get("_current_user"))

    def desativar_materia(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.desativar_materia(int(params["materia_id"]), ator=body.get("_current_user"))

    def alunos(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        query = body.get("_query", {})
        pagina = _parse_int_query(query, "page", 1)
        tamanho_pagina = _parse_int_query(query, "page_size", 10)
        termo = (query.get("termo") or "").strip() or None
        risco = (query.get("risco") or "").strip() or None
        materia_id_raw = (query.get("materia_id") or "").strip()
        materia_id = None
        if materia_id_raw:
            try:
                materia_id = int(materia_id_raw)
            except ValueError:
                raise AppError("Parametro 'materia_id' deve ser um numero inteiro.", 400)
        return 200, self.academic.listar_alunos(pagina, tamanho_pagina, termo, risco, materia_id)

    def criar_aluno(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 201, self.academic.criar_aluno(body, ator=body.get("_current_user"))

    def importar_alunos(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        csv_texto = body.get("csv", "")
        return 200, self.academic.importar_alunos_csv(csv_texto, ator=body.get("_current_user"))

    def aluno(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.obter_aluno(int(params["aluno_id"]))

    def atualizar_aluno(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.atualizar_aluno(int(params["aluno_id"]), body, ator=body.get("_current_user"))

    def desativar_aluno(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.desativar_aluno(int(params["aluno_id"]), ator=body.get("_current_user"))

    def vincular_materia(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.vincular_materia(
            int(params["aluno_id"]), int(params["materia_id"]), ator=body.get("_current_user")
        )

    def registrar_desempenho(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 201, self.academic.registrar_desempenho(int(params["aluno_id"]), body, ator=body.get("_current_user"))

    def listar_intervencoes(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_intervencoes(int(params["aluno_id"]))

    def registrar_intervencao(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 201, self.academic.registrar_intervencao(
            int(params["aluno_id"]), body, ator=body.get("_current_user")
        )

    def atualizar_intervencao(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.atualizar_intervencao(
            int(params["intervencao_id"]), body, ator=body.get("_current_user")
        )

    def recalcular_riscos(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.recalcular_riscos()

    def dashboard(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.dashboard()

    def dashboard_individual(
        self,
        params: dict[str, str],
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[int, Any]:
        return 200, self.academic.obter_aluno(
            int(params["aluno_id"])
        )

    def alertas(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_alertas()

    def relatorios(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_relatorios()

    def criar_relatorio(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        user = body.get("_current_user") or {}
        return 201, self.academic.criar_relatorio(body, user.get("id"))

    def auditoria(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        query = body.get("_query", {})
        pagina = _parse_int_query(query, "page", 1)
        tamanho_pagina = _parse_int_query(query, "page_size", 20)
        return 200, self.academic.listar_auditoria(pagina, tamanho_pagina)

    def obter_config_risco(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.obter_config_risco()

    def atualizar_config_risco(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.atualizar_config_risco(body, ator=body.get("_current_user"))

    def alterar_senha(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        user = body.get("_current_user") or {}
        self.auth.alterar_senha(user.get("id"), str(body.get("senha_atual", "")), str(body.get("nova_senha", "")))
        return 200, {"mensagem": "Senha alterada com sucesso."}

    def comparativo_materias(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.comparativo_materias()


class RequestHandler(BaseHTTPRequestHandler):
    app: Application
    allowed_origins: set[str] = set()

    def do_OPTIONS(self) -> None:
        self._send(204, None)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == STATIC_MOUNT or parsed.path.startswith(f"{STATIC_MOUNT}/"):
            self._serve_static(parsed.path)
            return
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        started = time.monotonic()
        status = 500
        try:
            body = self._read_json()
            body["_query"] = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            headers = {key.lower(): value for key, value in self.headers.items()}
            status, response = self.app.dispatch(self.command, parsed.path, body, headers)
            self._send(status, response)
        except AppError as exc:
            self.app.conn.rollback()
            status = exc.status
            self._send(status, {"erro": exc.message})
        except json.JSONDecodeError:
            self.app.conn.rollback()
            status = 400
            self._send(status, {"erro": "JSON invalido."})
        except Exception as exc:
            self.app.conn.rollback()
            status = 500
            logger.exception("Erro interno ao processar %s %s", self.command, parsed.path)
            self._send(status, {"erro": "Erro interno.", "detalhe": str(exc)})
        finally:
            duracao_ms = (time.monotonic() - started) * 1000
            logger.info("%s %s -> %s (%.1fms)", self.command, parsed.path, status, duracao_ms)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _serve_static(self, path: str) -> None:
        relative = path[len(STATIC_MOUNT) :] or "/"
        if relative == "/":
            relative = "/index.html"
        candidate = (FRONTEND_DIR / relative.lstrip("/")).resolve()
        frontend_root = FRONTEND_DIR.resolve()
        if frontend_root not in candidate.parents and candidate != frontend_root:
            self._send_static_error(403, "Acesso negado.")
            return
        if not candidate.exists() or candidate.is_dir():
            # Fallback de SPA: rotas client-side (#/...) sempre recebem o index.html.
            candidate = frontend_root / "index.html"
        if not candidate.exists():
            self._send_static_error(404, "Frontend nao encontrado. Confira a pasta 'frontend/'.")
            return
        content_type = MIME_TYPES.get(candidate.suffix, "application/octet-stream")
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._write_cors_headers()
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _send_static_error(self, status: int, message: str) -> None:
        encoded = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _write_cors_headers(self) -> None:
        """Reflete o header Origin somente se ele estiver na allowlist do servidor.

        Evita o antigo 'Access-Control-Allow-Origin: *', que permitiria que
        qualquer site na internet lesse respostas autenticadas via fetch
        cross-origin no navegador da vitima.
        """
        origin = self.headers.get("Origin")
        if origin and (origin in self.allowed_origins or "*" in self.allowed_origins):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send(self, status: int, payload: Any) -> None:
        self.send_response(status)
        self._write_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if payload is None:
            self.end_headers()
            return
        encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def create_server(
    host: str = "127.0.0.1", port: int = 8000, recalculo_automatico: bool = True
) -> ThreadingHTTPServer:
    configure_logging()
    app = Application()
    RequestHandler.app = app
    RequestHandler.allowed_origins = resolve_allowed_origins(host, port)
    if recalculo_automatico:
        iniciar_recalculo_periodico(app.academic, app.lock)
    return ThreadingHTTPServer((host, port), RequestHandler)


def resolve_allowed_origins(host: str, port: int) -> set[str]:
    """Origens permitidas para CORS.

    Por padrao, soh a propria origem do servidor (em suas formas usuais de
    acesso local). Pode ser sobrescrito com a variavel de ambiente
    SIGMA_ALLOWED_ORIGINS (lista separada por virgulas, ou "*" para liberar
    qualquer origem).
    """
    env_value = os.environ.get("SIGMA_ALLOWED_ORIGINS")
    if env_value:
        return {origin.strip() for origin in env_value.split(",") if origin.strip()}
    return {
        f"http://{host}:{port}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    }


def require_gestor(body: dict[str, Any]) -> None:
    user = body.get("_current_user") or {}
    if user.get("perfil") != "gestor":
        raise AppError("Acesso restrito ao gestor.", 403)


def _parse_int_query(query: dict[str, str], key: str, default: int) -> int:
    value = query.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        raise AppError(f"Parametro '{key}' deve ser um numero inteiro.", 400)
