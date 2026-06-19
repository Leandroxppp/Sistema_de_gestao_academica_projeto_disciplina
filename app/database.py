from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "academico.db"


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            carga_horaria INTEGER NOT NULL,
            semestre TEXT NOT NULL,
            professor_id INTEGER,
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

        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            curso TEXT NOT NULL,
            semestre TEXT NOT NULL,
            ano INTEGER NOT NULL,
            professor_id INTEGER,
            FOREIGN KEY (professor_id) REFERENCES usuarios(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS turma_disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turma_id INTEGER NOT NULL,
            materia_id INTEGER NOT NULL,
            UNIQUE (turma_id, materia_id),
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
            FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE CASCADE
        );
        """
    )
    ensure_column(conn, "desempenhos", "atividades_entregues", "INTEGER")
    ensure_column(conn, "desempenhos", "atividades_esperadas", "INTEGER")
    ensure_column(conn, "analises", "atividades_entregues", "INTEGER")
    ensure_column(conn, "analises", "atividades_esperadas", "INTEGER")
    ensure_column(conn, "alunos", "turma_id", "INTEGER")
    conn.execute(
        "UPDATE analises SET mensagem = REPLACE(mensagem, 'risco critico', 'risco alto') "
        "WHERE mensagem LIKE '%risco critico%'"
    )
    conn.execute(
        "UPDATE alertas SET mensagem = REPLACE(mensagem, 'risco critico', 'risco alto') "
        "WHERE mensagem LIKE '%risco critico%'"
    )
    conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_db(conn: sqlite3.Connection) -> bool:
    """Popula o banco com dados de demonstracao. Retorna True se populou."""
    existing = fetch_one(conn, "SELECT id FROM usuarios LIMIT 1")
    if existing:
        return False

    import json

    # ── Usuarios (mantem as credenciais demo de login) ────────────────────────
    usuarios = [
        ("Ana Costa", "professor@sigma.edu", "professor123", "professor", "Matematica", None),
        ("Bruno Gestor", "gestor@sigma.edu", "gestor123", "gestor", None, "Coordenador Academico"),
        ("Carlos Mendes", "carlos.mendes@sigma.edu", "professor123", "professor", "Fisica", None),
        ("Beatriz Rocha", "beatriz.rocha@sigma.edu", "professor123", "professor", "Quimica", None),
        ("Roberto Alves", "roberto.alves@sigma.edu", "professor123", "professor", "Engenharia", None),
        ("Fernanda Lima", "fernanda.lima@sigma.edu", "professor123", "professor", "Administracao", None),
    ]
    conn.executemany(
        """
        INSERT INTO usuarios (nome, email, senha_hash, perfil, especializacao, cargo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [(n, e, password_hash(s), p, esp, c) for (n, e, s, p, esp, c) in usuarios],
    )

    # ── Materias (id implicito = ordem) ───────────────────────────────────────
    # (nome, carga_horaria, semestre, professor_id)
    materias = [
        ("Calculo I", 80, "2026.1", 1),       # 1
        ("Algebra Linear", 60, "2026.1", 1),  # 2
        ("Fisica Geral", 80, "2026.1", 3),    # 3
        ("Mecanica", 60, "2026.1", 3),        # 4
        ("Quimica Geral", 80, "2026.1", 4),   # 5
        ("Programacao", 80, "2026.1", 5),     # 6
        ("Estatistica", 60, "2026.1", 6),     # 7
        ("Economia", 60, "2026.1", 6),        # 8
    ]
    conn.executemany(
        "INSERT INTO materias (nome, carga_horaria, semestre, professor_id) VALUES (?, ?, ?, ?)",
        materias,
    )

    # ── Turmas (id implicito = ordem) ─────────────────────────────────────────
    # (nome, curso, semestre, ano, professor_id, [materia_ids], [perfis_risco_dos_6_alunos])
    turmas = [
        ("MAT-301", "Matematica", "2026.1", 2026, 1, [1, 2],
         ["baixo", "baixo", "baixo", "baixo", "medio", "alto"]),       # turma forte
        ("FIS-201", "Fisica", "2026.1", 2026, 3, [3, 4],
         ["baixo", "baixo", "medio", "medio", "alto", "alto"]),        # turma fraca
        ("QUI-101", "Quimica", "2026.1", 2026, 4, [5],
         ["baixo", "baixo", "baixo", "medio", "medio", "alto"]),       # turma media
        ("ENG-301", "Engenharia", "2026.1", 2026, 5, [6, 1],
         ["baixo", "baixo", "baixo", "medio", "medio", "medio"]),      # sem risco alto
        ("ADM-201", "Administracao", "2026.1", 2026, 6, [7, 8],
         ["baixo", "medio", "medio", "medio", "alto", "alto"]),        # turma critica
    ]
    conn.executemany(
        "INSERT INTO turmas (nome, curso, semestre, ano, professor_id) VALUES (?, ?, ?, ?, ?)",
        [(nome, curso, sem, ano, prof) for (nome, curso, sem, ano, prof, _mats, _perfis) in turmas],
    )
    for turma_id, (_n, _c, _s, _a, _p, mats, _perfis) in enumerate(turmas, start=1):
        conn.executemany(
            "INSERT INTO turma_disciplinas (turma_id, materia_id) VALUES (?, ?)",
            [(turma_id, m) for m in mats],
        )

    # ── Alunos + matriculas + desempenhos ─────────────────────────────────────
    # 6 alunos por turma com risco distribuido: 3 baixo, 2 medio, 1 alto.
    nomes = [
        "Carla Lima", "Diego Souza", "Elisa Rocha", "Felipe Nunes", "Gabriela Dias", "Hugo Martins",
        "Isabela Freitas", "Joao Pedro", "Karina Melo", "Lucas Barros", "Marina Teixeira", "Nathan Gomes",
        "Olivia Castro", "Paulo Ramos", "Quezia Pinto", "Rafael Tavares", "Sofia Andrade", "Thiago Moraes",
        "Ursula Pires", "Victor Hugo", "Wanessa Reis", "Xavier Lopes", "Yara Cunha", "Zeca Antunes",
        "Bruna Farias", "Caio Vidal", "Daniela Rios", "Eduardo Sa", "Fabiana Lopes", "Gustavo Neri",
    ]
    aluno_rows = []        # (nome, matricula, email, status, turma_id)
    desempenho_specs = []  # (aluno_index0, materia_id, notas, freq, entregues, esperadas)
    matricula_pairs = []   # (aluno_index0, materia_id)

    idx = 0
    for turma_id, (_n, _c, _s, _a, _p, mats, perfis) in enumerate(turmas, start=1):
        for j in range(6):
            nome = nomes[idx]
            matricula = f"2026{idx + 1:03d}"
            email = nome.lower().replace(" ", ".") + "@sigma.edu"
            aluno_rows.append((nome, matricula, email, "Cursando_Materia", turma_id))

            # matricula em todas as disciplinas da turma
            for m in mats:
                matricula_pairs.append((idx, m))

            risco = perfis[j]
            var = (j % 3) * 0.3  # pequena variacao para os graficos nao ficarem identicos
            if risco == "baixo":
                notas = [round(min(10.0, 7.6 + var), 1), round(min(10.0, 8.2 + var), 1), round(min(10.0, 8.8 + var), 1)]
                freq = 88 + j
                entregues, esperadas = 9 + (j % 2), 10
            elif risco == "medio":
                notas = [round(5.6 + var, 1), round(6.0 + var, 1), round(6.4 + var, 1)]
                freq = 74 + j
                entregues, esperadas = 6, 10
            else:  # alto
                notas = [round(3.0 + var, 1), round(3.6 + var, 1), round(4.2 + var, 1)]
                freq = 58 - j
                entregues, esperadas = 3, 10

            desempenho_specs.append((idx, mats[0], notas, freq, entregues, esperadas))
            idx += 1

    conn.executemany(
        "INSERT INTO alunos (nome, matricula, email, status, turma_id) VALUES (?, ?, ?, ?, ?)",
        aluno_rows,
    )

    # ids dos alunos sao sequenciais a partir de 1 (banco recem-criado)
    conn.executemany(
        "INSERT INTO matriculas (aluno_id, materia_id) VALUES (?, ?)",
        [(i + 1, m) for (i, m) in matricula_pairs],
    )
    conn.executemany(
        """
        INSERT INTO desempenhos
        (aluno_id, materia_id, notas_json, frequencia, atividades_entregues, atividades_esperadas, data_referencia)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (i + 1, materia_id, json.dumps(notas), freq, ent, esp, "2026-06-10")
            for (i, materia_id, notas, freq, ent, esp) in desempenho_specs
        ],
    )

    conn.commit()
    return True
