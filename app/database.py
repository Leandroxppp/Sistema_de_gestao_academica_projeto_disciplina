from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "academico.db"

PBKDF2_ITERATIONS = 200_000


def password_hash(password: str, salt: str | None = None) -> str:
    """Gera hash salgado da senha (PBKDF2-HMAC-SHA256). Formato: 'salt$hash_hex'."""
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return f"{salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> tuple[bool, str | None]:
    """Verifica a senha contra o hash armazenado.

    Retorna (valido, hash_atualizado). `hash_atualizado` vem preenchido quando
    o hash estava no formato legado (sha256 sem salt) e deve ser migrado para
    o formato salgado apos uma autenticacao bem sucedida.
    """
    if "$" in stored_hash:
        salt, _, _ = stored_hash.partition("$")
        valido = hmac.compare_digest(password_hash(password, salt), stored_hash)
        return valido, None
    legado = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(legado, stored_hash):
        return True, password_hash(password)
    return False, None


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_all(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]


def fetch_one(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, tuple(params)).fetchone()
    return dict(row) if row else None


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK (perfil IN ('professor', 'gestor')),
            especializacao TEXT,
            cargo TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            carga_horaria INTEGER NOT NULL,
            semestre TEXT NOT NULL,
            professor_id INTEGER,
            ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (professor_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            matricula TEXT NOT NULL UNIQUE,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'Cadastrado',
            status_risco TEXT NOT NULL DEFAULT 'Baixo',
            probabilidade_evasao REAL NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS matriculas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            materia_id INTEGER NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1,
            UNIQUE (aluno_id, materia_id),
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE,
            FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS desempenhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            materia_id INTEGER,
            notas_json TEXT NOT NULL,
            frequencia REAL NOT NULL,
            atividades_entregues INTEGER,
            atividades_esperadas INTEGER,
            data_referencia TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE,
            FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            nivel_risco TEXT NOT NULL,
            probabilidade_evasao REAL NOT NULL,
            media_notas REAL NOT NULL,
            frequencia REAL NOT NULL,
            atividades_entregues INTEGER,
            atividades_esperadas INTEGER,
            mensagem TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            mensagem TEXT NOT NULL,
            nivel_risco TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolvido_em TEXT,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            criado_por INTEGER,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (criado_por) REFERENCES usuarios(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS sessoes (
            token TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            expira_em REAL NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            usuario_nome TEXT,
            acao TEXT NOT NULL,
            entidade TEXT NOT NULL,
            entidade_id INTEGER,
            detalhes TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
        );

        -- Acoes de acompanhamento (plano de acao) registradas para um aluno em
        -- risco: contato com responsavel, reuniao, encaminhamento etc.
        CREATE TABLE IF NOT EXISTS intervencoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            descricao TEXT,
            status TEXT NOT NULL DEFAULT 'Pendente',
            responsavel_id INTEGER,
            criado_por INTEGER,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT,
            resolvido_em TEXT,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE,
            FOREIGN KEY (responsavel_id) REFERENCES usuarios(id) ON DELETE SET NULL,
            FOREIGN KEY (criado_por) REFERENCES usuarios(id) ON DELETE SET NULL
        );

        -- Configuracoes chave/valor (ex.: limiares de risco). Valor armazenado
        -- como texto (JSON quando for um objeto) para manter o schema simples.
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Indices de performance: colunas usadas com frequencia em filtros, joins
        -- e ordenacoes. CREATE INDEX IF NOT EXISTS e idempotente, entao pode viver
        -- direto aqui (assim como as tabelas acima), sem precisar de migracao.
        CREATE INDEX IF NOT EXISTS idx_alunos_status_risco ON alunos(status_risco);
        CREATE INDEX IF NOT EXISTS idx_alunos_ativo ON alunos(ativo);
        CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);
        CREATE INDEX IF NOT EXISTS idx_materias_ativo ON materias(ativo);
        CREATE INDEX IF NOT EXISTS idx_materias_professor ON materias(professor_id);
        CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes(usuario_id);
        CREATE INDEX IF NOT EXISTS idx_desempenhos_aluno ON desempenhos(aluno_id);
        CREATE INDEX IF NOT EXISTS idx_analises_aluno ON analises(aluno_id);
        CREATE INDEX IF NOT EXISTS idx_alertas_aluno ON alertas(aluno_id);
        CREATE INDEX IF NOT EXISTS idx_alertas_ativo ON alertas(ativo);
        CREATE INDEX IF NOT EXISTS idx_matriculas_aluno ON matriculas(aluno_id);
        CREATE INDEX IF NOT EXISTS idx_matriculas_materia ON matriculas(materia_id);
        CREATE INDEX IF NOT EXISTS idx_auditoria_criado_em ON auditoria(criado_em);
        CREATE INDEX IF NOT EXISTS idx_intervencoes_aluno ON intervencoes(aluno_id);
        CREATE INDEX IF NOT EXISTS idx_intervencoes_status ON intervencoes(status);
        """
    )
    run_migrations(conn)
    conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# --- Migracoes versionadas --------------------------------------------------
# CREATE TABLE/INDEX IF NOT EXISTS (acima) ja sao idempotentes e cobrem a
# maior parte da evolucao do schema. O unico caso que o SQLite nao permite
# expressar de forma idempotente e ALTER TABLE ADD COLUMN -- por isso essas
# mudancas continuam passando por `ensure_column`, mas agora orquestradas por
# uma lista de migracoes numeradas e rastreadas na tabela `schema_migrations`,
# em vez de chamadas soltas dentro de init_db.


def _migracao_001_colunas_atividades(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "desempenhos", "atividades_entregues", "INTEGER")
    ensure_column(conn, "desempenhos", "atividades_esperadas", "INTEGER")
    ensure_column(conn, "analises", "atividades_entregues", "INTEGER")
    ensure_column(conn, "analises", "atividades_esperadas", "INTEGER")


def _migracao_002_soft_delete(conn: sqlite3.Connection) -> None:
    ensure_column(conn, "usuarios", "ativo", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "alunos", "ativo", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "materias", "ativo", "INTEGER NOT NULL DEFAULT 1")


MIGRATIONS: list[tuple[int, str, Any]] = [
    (1, "adiciona atividades_entregues/atividades_esperadas em desempenhos e analises", _migracao_001_colunas_atividades),
    (2, "adiciona coluna ativo (soft delete) em usuarios, alunos e materias", _migracao_002_soft_delete),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            versao INTEGER PRIMARY KEY,
            descricao TEXT NOT NULL,
            aplicada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    aplicadas = {row["versao"] for row in conn.execute("SELECT versao FROM schema_migrations").fetchall()}
    for versao, descricao, migrar in MIGRATIONS:
        if versao in aplicadas:
            continue
        migrar(conn)
        conn.execute(
            "INSERT INTO schema_migrations (versao, descricao) VALUES (?, ?)",
            (versao, descricao),
        )


def seed_db(conn: sqlite3.Connection) -> None:
    existing = fetch_one(conn, "SELECT id FROM usuarios LIMIT 1")
    if existing:
        return

    conn.executemany(
        """
        INSERT INTO usuarios (nome, email, senha_hash, perfil, especializacao, cargo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("Ana Professora", "professor@sigma.edu", password_hash("professor123"), "professor", "Matematica", None),
            ("Bruno Gestor", "gestor@sigma.edu", password_hash("gestor123"), "gestor", None, "Coordenador Academico"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO materias (nome, carga_horaria, semestre, professor_id)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("Calculo I", 80, "2026.1", 1),
            ("Programacao", 80, "2026.1", 1),
            ("Logica", 60, "2026.1", 1),
        ],
    )
    conn.executemany(
        """
        INSERT INTO alunos (nome, matricula, email, status, status_risco, probabilidade_evasao)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("Carla Lima", "2026001", "carla@sigma.edu", "Regular", "Baixo", 0.12),
            ("Diego Souza", "2026002", "diego@sigma.edu", "Risco_Medio", "Medio", 0.52),
            ("Elisa Rocha", "2026003", "elisa@sigma.edu", "Risco_Alto", "Alto", 0.84),
        ],
    )
    conn.executemany(
        "INSERT INTO matriculas (aluno_id, materia_id) VALUES (?, ?)",
        [(1, 1), (1, 2), (2, 1), (2, 3), (3, 2), (3, 3)],
    )
    conn.executemany(
        """
        INSERT INTO desempenhos (aluno_id, materia_id, notas_json, frequencia, data_referencia)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "[8.0, 7.5, 9.0]", 92, "2026-05-18"),
            (2, 1, "[5.5, 6.0, 5.0]", 74, "2026-05-18"),
            (3, 2, "[3.0, 4.0, 2.5]", 58, "2026-05-18"),
        ],
    )
    conn.commit()
