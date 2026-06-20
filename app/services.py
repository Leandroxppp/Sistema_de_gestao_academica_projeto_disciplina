from __future__ import annotations

import csv
import io
import json
import logging
import secrets
import sqlite3
import time
from datetime import datetime
from typing import Any

from .database import fetch_all, fetch_one, password_hash, verify_password
from .models import AnaliseRisco, NivelRisco, StatusAluno, now_iso, today_iso
from .notifications import enviar_alerta_risco

SESSION_TTL_SECONDS = 8 * 60 * 60  # token de sessao expira apos 8 horas

logger = logging.getLogger("sigma.services")

# Limiares padrao do motor de risco. Configuraveis pelo gestor (tabela
# `configuracoes`, chave 'risco_thresholds') via AcademicService.obter_config_risco/
# atualizar_config_risco -- estes valores aqui sao apenas o fallback quando nada
# foi configurado ainda (e tambem os valores originais, antes hardcoded).
DEFAULT_RISCO_THRESHOLDS: dict[str, float] = {
    "alto_media": 5.0,
    "alto_frequencia": 65.0,
    "alto_deficit_atividades": 0.5,
    "alto_fator": 0.7,
    "medio_media": 7.0,
    "medio_frequencia": 80.0,
    "medio_deficit_atividades": 0.25,
    "medio_fator": 0.4,
}


def _ator_info(ator: dict[str, Any] | None) -> tuple[int | None, str | None]:
    """Extrai (id, nome) de um usuario autenticado para fins de auditoria.

    `ator` normalmente e o dict `_current_user` injetado pelo dispatcher --
    aceita None para chamadas internas/scripts sem usuario associado.
    """
    if not ator:
        return None, None
    return ator.get("id"), ator.get("nome")


class AppError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class AuthService:
    # Protecao simples contra forca bruta: limite de tentativas falhas por email,
    # dentro de uma janela de tempo. Estado em memoria (por processo), reiniciado
    # se o servidor for reiniciado -- compromisso aceitavel para esta aplicacao
    # de instancia unica.
    MAX_TENTATIVAS = 5
    JANELA_TENTATIVAS_SEGUNDOS = 5 * 60

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._tentativas: dict[str, list[float]] = {}

    def login(self, email: str, senha: str) -> dict[str, Any]:
        self._verificar_rate_limit(email)
        user = fetch_one(self.conn, "SELECT * FROM usuarios WHERE email = ?", (email,))
        if not user or not user.get("ativo", 1):
            self._registrar_falha(email)
            raise AppError("Credenciais invalidas.", 401)
        valido, novo_hash = verify_password(senha, user["senha_hash"])
        if not valido:
            self._registrar_falha(email)
            raise AppError("Credenciais invalidas.", 401)
        self._limpar_tentativas(email)
        if novo_hash:
            self.conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (novo_hash, user["id"]))

        # Sessao persistida em SQLite: sobrevive a reinicios do servidor e
        # permite revogacao imediata quando um usuario e desativado.
        token = secrets.token_urlsafe(24)
        expira_em = time.time() + SESSION_TTL_SECONDS
        self.conn.execute("DELETE FROM sessoes WHERE expira_em < ?", (time.time(),))
        self.conn.execute(
            "INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (?, ?, ?)",
            (token, user["id"], expira_em),
        )
        self.conn.commit()
        safe_user = self._safe_user(user)
        return {"token": token, "usuario": safe_user, "expira_em_segundos": SESSION_TTL_SECONDS}

    def logout(self, authorization: str | None) -> None:
        token = self._extract_token(authorization)
        if token:
            self.conn.execute("DELETE FROM sessoes WHERE token = ?", (token,))
            self.conn.commit()

    def current_user(self, authorization: str | None) -> dict[str, Any] | None:
        token = self._extract_token(authorization)
        if not token:
            return None
        row = fetch_one(
            self.conn,
            """
            SELECT u.*, s.expira_em AS _expira_em
            FROM sessoes s
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.token = ?
            """,
            (token,),
        )
        if not row:
            return None
        if row["_expira_em"] < time.time() or not row.get("ativo", 1):
            self.conn.execute("DELETE FROM sessoes WHERE token = ?", (token,))
            self.conn.commit()
            return None
        return self._safe_user(row)

    def alterar_senha(self, usuario_id: int, senha_atual: str, nova_senha: str) -> None:
        """Troca de senha self-service: o proprio usuario autenticado informa a
        senha atual (confirmando identidade) e a nova senha. Diferente de
        atualizar_usuario (gestor-only), nao exige perfil de gestor.
        """
        user = fetch_one(self.conn, "SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        if not user:
            raise AppError("Usuario nao encontrado.", 404)
        valido, _ = verify_password(senha_atual or "", user["senha_hash"])
        if not valido:
            raise AppError("Senha atual incorreta.", 401)
        if not nova_senha or len(nova_senha) < 6:
            raise AppError("A nova senha deve ter ao menos 6 caracteres.")
        self.conn.execute(
            "UPDATE usuarios SET senha_hash = ? WHERE id = ?", (password_hash(nova_senha), usuario_id)
        )
        self.conn.execute(
            """
            INSERT INTO auditoria (usuario_id, usuario_nome, acao, entidade, entidade_id, detalhes)
            VALUES (?, ?, 'atualizar', 'usuario', ?, 'Alterou a propria senha.')
            """,
            (usuario_id, user["nome"], usuario_id),
        )
        self.conn.commit()

    def _verificar_rate_limit(self, email: str) -> None:
        agora = time.time()
        tentativas = [t for t in self._tentativas.get(email, []) if agora - t < self.JANELA_TENTATIVAS_SEGUNDOS]
        self._tentativas[email] = tentativas
        if len(tentativas) >= self.MAX_TENTATIVAS:
            raise AppError("Muitas tentativas de login. Aguarde alguns minutos e tente novamente.", 429)

    def _registrar_falha(self, email: str) -> None:
        self._tentativas.setdefault(email, []).append(time.time())

    def _limpar_tentativas(self, email: str) -> None:
        self._tentativas.pop(email, None)

    @staticmethod
    def _extract_token(authorization: str | None) -> str | None:
        if not authorization:
            return None
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return None
        return authorization[len(prefix) :]

    @staticmethod
    def _safe_user(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "nome": user["nome"],
            "email": user["email"],
            "perfil": user["perfil"],
            "especializacao": user.get("especializacao"),
            "cargo": user.get("cargo"),
            "ativo": bool(user.get("ativo", 1)),
        }


class MotorIA:
    """Motor preditivo por regras, conforme contingencia prevista no plano."""

    @staticmethod
    def calcular_fator_risco(media: float, frequencia: float, deficit_atividades: float) -> float:
        deficit_nota = max(0.0, (7.0 - media) / 7.0)
        deficit_freq = max(0.0, (75.0 - frequencia) / 75.0)
        return min(
            0.95,
            0.10 + (deficit_nota * 0.45) + (deficit_freq * 0.30) + (deficit_atividades * 0.15),
        )

    @staticmethod
    def classificar(
        media: float,
        frequencia: float,
        deficit_atividades: float,
        fator_risco: float,
        thresholds: dict[str, float] | None = None,
    ) -> tuple[NivelRisco, str]:
        """Classifica (nivel, mensagem) a partir dos indicadores e dos limiares.

        `thresholds` pode trazer apenas um subconjunto das chaves de
        DEFAULT_RISCO_THRESHOLDS -- as ausentes caem no valor padrao. Extraido
        de `analisar()` para ser reutilizavel tanto na analise por aluno quanto
        na agregacao por turma (comparativo entre professores da mesma materia).
        """
        t = {**DEFAULT_RISCO_THRESHOLDS, **(thresholds or {})}
        if (
            media < t["alto_media"]
            or frequencia < t["alto_frequencia"]
            or deficit_atividades >= t["alto_deficit_atividades"]
            or fator_risco >= t["alto_fator"]
        ):
            return NivelRisco.ALTO, "Aluno em risco critico: desempenho e/ou frequencia exigem intervencao imediata."
        if (
            media < t["medio_media"]
            or frequencia < t["medio_frequencia"]
            or deficit_atividades >= t["medio_deficit_atividades"]
            or fator_risco >= t["medio_fator"]
        ):
            return NivelRisco.MEDIO, "Aluno em atencao: acompanhar proximas avaliacoes e frequencia."
        return NivelRisco.BAIXO, "Aluno regular: indicadores academicos dentro do esperado."

    def analisar(
        self,
        aluno_id: int,
        notas: list[float],
        frequencia: float,
        atividades_entregues: int | None = None,
        atividades_esperadas: int | None = None,
        thresholds: dict[str, float] | None = None,
    ) -> AnaliseRisco:
        if not notas:
            raise AppError("Informe ao menos uma nota para analise.")
        if frequencia < 0 or frequencia > 100:
            raise AppError("Frequencia deve estar entre 0 e 100.")
        if atividades_entregues is not None and atividades_entregues < 0:
            raise AppError("Atividades entregues nao pode ser negativo.")
        if atividades_esperadas is not None and atividades_esperadas <= 0:
            raise AppError("Atividades esperadas deve ser maior que zero.")
        if (
            atividades_entregues is not None
            and atividades_esperadas is not None
            and atividades_entregues > atividades_esperadas
        ):
            raise AppError("Atividades entregues nao pode ser maior que atividades esperadas.")

        media = sum(notas) / len(notas)
        deficit_atividades = 0.0
        if atividades_entregues is not None and atividades_esperadas is not None:
            percentual_entrega = atividades_entregues / atividades_esperadas
            deficit_atividades = max(0.0, 1.0 - percentual_entrega)

        fator_risco = self.calcular_fator_risco(media, frequencia, deficit_atividades)
        nivel, mensagem = self.classificar(media, frequencia, deficit_atividades, fator_risco, thresholds)

        return AnaliseRisco(
            aluno_id=aluno_id,
            nivel=nivel,
            fator_risco=fator_risco,
            media_notas=media,
            frequencia=frequencia,
            atividades_entregues=atividades_entregues,
            atividades_esperadas=atividades_esperadas,
            mensagem=mensagem,
            criado_em=datetime.now(),
        )


class AcademicService:
    def __init__(self, conn: sqlite3.Connection, motor_ia: MotorIA) -> None:
        self.conn = conn
        self.motor_ia = motor_ia

    def _registrar_auditoria(
        self,
        ator: dict[str, Any] | None,
        acao: str,
        entidade: str,
        entidade_id: int | None,
        detalhes: str | None = None,
    ) -> None:
        """Grava uma linha de auditoria na MESMA transacao da acao que a originou.

        Por isso este metodo nunca chama commit/rollback -- quem chama decide
        quando persistir. Se a operacao principal for revertida, a entrada de
        auditoria correspondente tambem e revertida (consistencia atomica).
        """
        ator_id, ator_nome = _ator_info(ator)
        self.conn.execute(
            """
            INSERT INTO auditoria (usuario_id, usuario_nome, acao, entidade, entidade_id, detalhes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ator_id, ator_nome, acao, entidade, entidade_id, detalhes),
        )

    def listar_auditoria(self, pagina: int = 1, tamanho_pagina: int = 20) -> dict[str, Any]:
        pagina = max(1, pagina)
        tamanho_pagina = max(1, min(tamanho_pagina, 100))
        total = fetch_one(self.conn, "SELECT COUNT(*) AS total FROM auditoria")["total"]
        offset = (pagina - 1) * tamanho_pagina
        itens = fetch_all(
            self.conn,
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ? OFFSET ?",
            (tamanho_pagina, offset),
        )
        return {"itens": itens, "total": total, "pagina": pagina, "tamanho_pagina": tamanho_pagina}

    # --- Limiares de risco configuraveis ------------------------------------

    def obter_config_risco(self) -> dict[str, Any]:
        row = fetch_one(self.conn, "SELECT valor FROM configuracoes WHERE chave = 'risco_thresholds'")
        thresholds = dict(DEFAULT_RISCO_THRESHOLDS)
        if row:
            try:
                dados = json.loads(row["valor"])
            except (json.JSONDecodeError, TypeError):
                dados = {}
            for chave in DEFAULT_RISCO_THRESHOLDS:
                if chave in dados:
                    thresholds[chave] = dados[chave]
        return thresholds

    def atualizar_config_risco(self, payload: dict[str, Any], ator: dict[str, Any] | None = None) -> dict[str, Any]:
        atual = self.obter_config_risco()
        alterados: list[str] = []
        for chave in DEFAULT_RISCO_THRESHOLDS:
            if chave not in payload:
                continue
            try:
                valor = float(payload[chave])
            except (TypeError, ValueError):
                raise AppError(f"O campo '{chave}' deve ser numerico.")
            if "_frequencia" in chave and not (0 <= valor <= 100):
                raise AppError(f"O campo '{chave}' deve estar entre 0 e 100.")
            if "_fator" in chave and not (0 <= valor <= 1):
                raise AppError(f"O campo '{chave}' deve estar entre 0 e 1.")
            atual[chave] = valor
            alterados.append(chave)
        if not alterados:
            raise AppError("Nenhum limiar valido foi informado.")
        self.conn.execute(
            """
            INSERT INTO configuracoes (chave, valor, atualizado_em) VALUES ('risco_thresholds', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, atualizado_em = CURRENT_TIMESTAMP
            """,
            (json.dumps(atual),),
        )
        self._registrar_auditoria(
            ator, "atualizar", "configuracao", None, f"Atualizou limiares de risco: {', '.join(alterados)}."
        )
        self.conn.commit()
        return atual

    def importar_alunos_csv(self, csv_texto: str, ator: dict[str, Any] | None = None) -> dict[str, Any]:
        """Importa alunos em lote a partir de texto CSV (colunas: nome, matricula, email).

        Usa apenas o modulo `csv` da biblioteca padrao -- sem upload multipart,
        o conteudo chega como texto dentro do corpo JSON (`{"csv": "..."}"`).
        Linhas com matricula duplicada ou campos obrigatorios ausentes sao
        reportadas em `erros`, mas nao interrompem a importacao das demais.
        """
        if not csv_texto or not csv_texto.strip():
            raise AppError("Conteudo CSV vazio.")
        leitor = csv.DictReader(io.StringIO(csv_texto))
        if not leitor.fieldnames:
            raise AppError("CSV deve conter uma linha de cabecalho com as colunas 'nome' e 'matricula'.")
        cabecalho = {(c or "").strip().lower() for c in leitor.fieldnames}
        if not {"nome", "matricula"}.issubset(cabecalho):
            raise AppError("CSV deve conter ao menos as colunas 'nome' e 'matricula'.")
        leitor.fieldnames = [(c or "").strip().lower() for c in leitor.fieldnames]

        importados = 0
        erros: list[dict[str, Any]] = []
        for numero_linha, linha in enumerate(leitor, start=2):  # linha 1 e o cabecalho
            nome = (linha.get("nome") or "").strip()
            matricula = (linha.get("matricula") or "").strip()
            email = (linha.get("email") or "").strip() or None
            if not nome or not matricula:
                erros.append({"linha": numero_linha, "motivo": "nome e matricula sao obrigatorios."})
                continue
            try:
                cur = self.conn.execute(
                    "INSERT INTO alunos (nome, matricula, email, status) VALUES (?, ?, ?, ?)",
                    (nome, matricula, email, StatusAluno.CADASTRADO.value),
                )
            except sqlite3.IntegrityError:
                erros.append({"linha": numero_linha, "motivo": f"matricula '{matricula}' ja cadastrada."})
                continue
            self._registrar_auditoria(
                ator, "criar", "aluno", cur.lastrowid, f"Importado via CSV: {nome} ({matricula})."
            )
            importados += 1
        self.conn.commit()
        return {"importados": importados, "total_linhas": importados + len(erros), "erros": erros}

    def listar_usuarios(self) -> list[dict[str, Any]]:
        rows = fetch_all(self.conn, "SELECT * FROM usuarios ORDER BY nome")
        return [AuthService._safe_user(row) for row in rows]

    def criar_usuario(self, payload: dict[str, Any], ator: dict[str, Any] | None = None) -> dict[str, Any]:
        nome = require(payload, "nome")
        email = require(payload, "email")
        senha = require(payload, "senha")
        perfil = require(payload, "perfil")
        if perfil not in {"professor", "gestor"}:
            raise AppError("Perfil deve ser professor ou gestor.")
        try:
            cur = self.conn.execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash, perfil, especializacao, cargo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (nome, email, password_hash(senha), perfil, payload.get("especializacao"), payload.get("cargo")),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Ja existe um usuario cadastrado com este email.", 409)
        self._registrar_auditoria(ator, "criar", "usuario", cur.lastrowid, f"Cadastrou o usuario {nome} ({email}).")
        self.conn.commit()
        return self.obter_usuario(cur.lastrowid)

    def obter_usuario(self, usuario_id: int) -> dict[str, Any]:
        user = fetch_one(self.conn, "SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        if not user:
            raise AppError("Usuario nao encontrado.", 404)
        return AuthService._safe_user(user)

    def atualizar_usuario(
        self, usuario_id: int, payload: dict[str, Any], ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._ensure_usuario(usuario_id)
        campos: list[str] = []
        valores: list[Any] = []
        nomes_alterados: list[str] = []
        if payload.get("nome"):
            campos.append("nome = ?")
            valores.append(payload["nome"])
            nomes_alterados.append("nome")
        if payload.get("email"):
            campos.append("email = ?")
            valores.append(payload["email"])
            nomes_alterados.append("email")
        if payload.get("perfil"):
            if payload["perfil"] not in {"professor", "gestor"}:
                raise AppError("Perfil deve ser professor ou gestor.")
            campos.append("perfil = ?")
            valores.append(payload["perfil"])
            nomes_alterados.append("perfil")
        if "especializacao" in payload:
            campos.append("especializacao = ?")
            valores.append(payload.get("especializacao"))
            nomes_alterados.append("especializacao")
        if "cargo" in payload:
            campos.append("cargo = ?")
            valores.append(payload.get("cargo"))
            nomes_alterados.append("cargo")
        if payload.get("senha"):
            campos.append("senha_hash = ?")
            valores.append(password_hash(payload["senha"]))
            nomes_alterados.append("senha")
        if "ativo" in payload:
            campos.append("ativo = ?")
            valores.append(1 if payload.get("ativo") else 0)
            nomes_alterados.append("ativo")
        if not campos:
            raise AppError("Nenhum campo para atualizar foi informado.")
        valores.append(usuario_id)
        try:
            self.conn.execute(f"UPDATE usuarios SET {', '.join(campos)} WHERE id = ?", valores)
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Ja existe um usuario cadastrado com este email.", 409)
        # Quando o unico campo alterado e "ativo" virando verdadeiro, trata-se de
        # uma reativacao (acao distinta de uma edicao de dados comum no log).
        acao = "reativar" if nomes_alterados == ["ativo"] and payload.get("ativo") else "atualizar"
        self._registrar_auditoria(
            ator, acao, "usuario", usuario_id, f"Campos alterados: {', '.join(nomes_alterados)}."
        )
        self.conn.commit()
        return self.obter_usuario(usuario_id)

    def desativar_usuario(self, usuario_id: int, ator: dict[str, Any] | None = None) -> dict[str, Any]:
        usuario = self._ensure_usuario(usuario_id)
        ator_id, _ = _ator_info(ator)
        if ator_id is not None and ator_id == usuario_id:
            raise AppError("Voce nao pode desativar seu proprio usuario.")
        if usuario["perfil"] == "gestor":
            outros = fetch_one(
                self.conn,
                "SELECT COUNT(*) AS total FROM usuarios WHERE perfil = 'gestor' AND ativo = 1 AND id != ?",
                (usuario_id,),
            )
            if not outros or outros["total"] == 0:
                raise AppError("Nao e possivel desativar o ultimo gestor ativo.")
        self.conn.execute("UPDATE usuarios SET ativo = 0 WHERE id = ?", (usuario_id,))
        self.conn.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario_id,))
        self._registrar_auditoria(ator, "desativar", "usuario", usuario_id, f"Desativou o usuario {usuario['nome']}.")
        self.conn.commit()
        return self.obter_usuario(usuario_id)

    def listar_materias(self) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT m.*, u.nome AS professor_nome
            FROM materias m
            LEFT JOIN usuarios u ON u.id = m.professor_id
            ORDER BY m.nome
            """,
        )

    def criar_materia(self, payload: dict[str, Any], ator: dict[str, Any] | None = None) -> dict[str, Any]:
        nome = require(payload, "nome")
        semestre = require(payload, "semestre")
        try:
            carga_horaria = int(require(payload, "carga_horaria"))
        except (TypeError, ValueError):
            raise AppError("carga_horaria deve ser um numero inteiro.")
        professor_id = optional_int(payload.get("professor_id"))
        try:
            cur = self.conn.execute(
                """
                INSERT INTO materias (nome, carga_horaria, semestre, professor_id)
                VALUES (?, ?, ?, ?)
                """,
                (nome, carga_horaria, semestre, professor_id),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Professor informado nao existe.", 400)
        self._registrar_auditoria(ator, "criar", "materia", cur.lastrowid, f"Cadastrou a materia {nome}.")
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM materias WHERE id = ?", (cur.lastrowid,))

    def atualizar_materia(
        self, materia_id: int, payload: dict[str, Any], ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._ensure_materia(materia_id)
        campos: list[str] = []
        valores: list[Any] = []
        nomes_alterados: list[str] = []
        if payload.get("nome"):
            campos.append("nome = ?")
            valores.append(payload["nome"])
            nomes_alterados.append("nome")
        if payload.get("carga_horaria") is not None:
            try:
                valores.append(int(payload["carga_horaria"]))
            except (TypeError, ValueError):
                raise AppError("carga_horaria deve ser um numero inteiro.")
            campos.append("carga_horaria = ?")
            nomes_alterados.append("carga_horaria")
        if payload.get("semestre"):
            campos.append("semestre = ?")
            valores.append(payload["semestre"])
            nomes_alterados.append("semestre")
        if "professor_id" in payload:
            campos.append("professor_id = ?")
            valores.append(optional_int(payload.get("professor_id")))
            nomes_alterados.append("professor_id")
        if "ativo" in payload:
            campos.append("ativo = ?")
            valores.append(1 if payload.get("ativo") else 0)
            nomes_alterados.append("ativo")
        if not campos:
            raise AppError("Nenhum campo para atualizar foi informado.")
        valores.append(materia_id)
        try:
            self.conn.execute(f"UPDATE materias SET {', '.join(campos)} WHERE id = ?", valores)
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Professor informado nao existe.", 400)
        acao = "reativar" if nomes_alterados == ["ativo"] and payload.get("ativo") else "atualizar"
        self._registrar_auditoria(
            ator, acao, "materia", materia_id, f"Campos alterados: {', '.join(nomes_alterados)}."
        )
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM materias WHERE id = ?", (materia_id,))

    def desativar_materia(self, materia_id: int, ator: dict[str, Any] | None = None) -> dict[str, Any]:
        materia = self._ensure_materia(materia_id)
        self.conn.execute("UPDATE materias SET ativo = 0 WHERE id = ?", (materia_id,))
        self._registrar_auditoria(ator, "desativar", "materia", materia_id, f"Desativou a materia {materia['nome']}.")
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM materias WHERE id = ?", (materia_id,))

    def listar_alunos(
        self,
        pagina: int = 1,
        tamanho_pagina: int = 10,
        termo: str | None = None,
        risco: str | None = None,
        materia_id: int | None = None,
    ) -> dict[str, Any]:
        pagina = max(1, pagina)
        tamanho_pagina = max(1, min(tamanho_pagina, 100))
        condicoes: list[str] = []
        parametros: list[Any] = []
        if termo:
            condicoes.append("(LOWER(nome) LIKE ? OR LOWER(matricula) LIKE ?)")
            termo_like = f"%{termo.strip().lower()}%"
            parametros.extend([termo_like, termo_like])
        if risco:
            condicoes.append("status_risco = ?")
            parametros.append(risco)
        if materia_id is not None:
            # Restringe aos alunos vinculados a esta materia/turma -- usado pela
            # tela "Minhas Turmas" do professor para listar somente os alunos
            # da turma selecionada, sem precisar paginar a lista inteira.
            condicoes.append("id IN (SELECT aluno_id FROM matriculas WHERE materia_id = ? AND ativa = 1)")
            parametros.append(materia_id)
        where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

        total = fetch_one(self.conn, f"SELECT COUNT(*) AS total FROM alunos {where}", parametros)["total"]
        offset = (pagina - 1) * tamanho_pagina
        alunos = fetch_all(
            self.conn,
            f"SELECT * FROM alunos {where} ORDER BY nome LIMIT ? OFFSET ?",
            (*parametros, tamanho_pagina, offset),
        )
        for aluno in alunos:
            normalize_fator_risco(aluno)
            aluno["materias"] = self._materias_do_aluno(aluno["id"])
            aluno["ultima_analise"] = self._ultima_analise(aluno["id"])
        return {"itens": alunos, "total": total, "pagina": pagina, "tamanho_pagina": tamanho_pagina}

    def obter_aluno(self, aluno_id: int) -> dict[str, Any]:
        aluno = fetch_one(self.conn, "SELECT * FROM alunos WHERE id = ?", (aluno_id,))
        if not aluno:
            raise AppError("Aluno nao encontrado.", 404)
        normalize_fator_risco(aluno)
        aluno["materias"] = self._materias_do_aluno(aluno_id)
        aluno["desempenhos"] = fetch_all(
            self.conn,
            """
            SELECT d.*, m.nome AS materia_nome
            FROM desempenhos d
            LEFT JOIN materias m ON m.id = d.materia_id
            WHERE d.aluno_id = ?
            ORDER BY d.data_referencia DESC, d.id DESC
            """,
            (aluno_id,),
        )
        for desempenho in aluno["desempenhos"]:
            desempenho["notas"] = json.loads(desempenho.pop("notas_json"))
        aluno["ultima_analise"] = self._ultima_analise(aluno_id)
        aluno["intervencoes"] = self.listar_intervencoes(aluno_id)
        return aluno

    def criar_aluno(self, payload: dict[str, Any], ator: dict[str, Any] | None = None) -> dict[str, Any]:
        nome = require(payload, "nome")
        try:
            cur = self.conn.execute(
                """
                INSERT INTO alunos (nome, matricula, email, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    nome,
                    require(payload, "matricula"),
                    payload.get("email"),
                    payload.get("status", StatusAluno.CADASTRADO.value),
                ),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Ja existe um aluno cadastrado com esta matricula.", 409)
        self._registrar_auditoria(ator, "criar", "aluno", cur.lastrowid, f"Cadastrou o aluno {nome}.")
        self.conn.commit()
        return self.obter_aluno(cur.lastrowid)

    def atualizar_aluno(
        self, aluno_id: int, payload: dict[str, Any], ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._ensure_aluno(aluno_id)
        campos: list[str] = []
        valores: list[Any] = []
        nomes_alterados: list[str] = []
        if payload.get("nome"):
            campos.append("nome = ?")
            valores.append(payload["nome"])
            nomes_alterados.append("nome")
        if payload.get("matricula"):
            campos.append("matricula = ?")
            valores.append(payload["matricula"])
            nomes_alterados.append("matricula")
        if "email" in payload:
            campos.append("email = ?")
            valores.append(payload.get("email"))
            nomes_alterados.append("email")
        if payload.get("status"):
            valores_validos = {item.value for item in StatusAluno}
            if payload["status"] not in valores_validos:
                raise AppError("Status informado e invalido.")
            campos.append("status = ?")
            valores.append(payload["status"])
            nomes_alterados.append("status")
        if "ativo" in payload:
            campos.append("ativo = ?")
            valores.append(1 if payload.get("ativo") else 0)
            nomes_alterados.append("ativo")
        if not campos:
            raise AppError("Nenhum campo para atualizar foi informado.")
        valores.append(aluno_id)
        try:
            self.conn.execute(f"UPDATE alunos SET {', '.join(campos)} WHERE id = ?", valores)
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Ja existe um aluno cadastrado com esta matricula.", 409)
        acao = "reativar" if nomes_alterados == ["ativo"] and payload.get("ativo") else "atualizar"
        self._registrar_auditoria(
            ator, acao, "aluno", aluno_id, f"Campos alterados: {', '.join(nomes_alterados)}."
        )
        self.conn.commit()
        return self.obter_aluno(aluno_id)

    def desativar_aluno(self, aluno_id: int, ator: dict[str, Any] | None = None) -> dict[str, Any]:
        aluno = self._ensure_aluno(aluno_id)
        self.conn.execute("UPDATE alunos SET ativo = 0 WHERE id = ?", (aluno_id,))
        self._registrar_auditoria(ator, "desativar", "aluno", aluno_id, f"Desativou o aluno {aluno['nome']}.")
        self.conn.commit()
        return self.obter_aluno(aluno_id)

    def vincular_materia(
        self, aluno_id: int, materia_id: int, ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._ensure_aluno_ativo(aluno_id)
        materia = self._ensure_materia_ativa(materia_id)
        self.conn.execute(
            "INSERT OR IGNORE INTO matriculas (aluno_id, materia_id) VALUES (?, ?)",
            (aluno_id, materia_id),
        )
        self.conn.execute(
            "UPDATE alunos SET status = ? WHERE id = ? AND status = ?",
            (StatusAluno.CURSANDO_MATERIA.value, aluno_id, StatusAluno.CADASTRADO.value),
        )
        self._registrar_auditoria(
            ator, "vincular_materia", "aluno", aluno_id, f"Vinculou a materia {materia['nome']} ao aluno."
        )
        self.conn.commit()
        return self.obter_aluno(aluno_id)

    def registrar_desempenho(
        self, aluno_id: int, payload: dict[str, Any], ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._ensure_aluno_ativo(aluno_id)
        materia_id = optional_int(payload.get("materia_id"))
        if materia_id is not None:
            self._ensure_materia_ativa(materia_id)
        try:
            notas = [float(nota) for nota in require(payload, "notas")]
            frequencia = float(require(payload, "frequencia"))
        except (TypeError, ValueError):
            raise AppError("notas e frequencia devem ser numericos.")
        atividades_entregues = optional_int(payload.get("atividades_entregues"))
        atividades_esperadas = optional_int(payload.get("atividades_esperadas"))
        data_referencia = payload.get("data_referencia", today_iso())

        # A analise e calculada (e validada) ANTES de qualquer escrita no banco.
        # Assim, um payload invalido (ex.: frequencia fora de 0-100) nunca deixa
        # um registro de desempenho parcial/pendente na transacao da conexao.
        thresholds = self.obter_config_risco()
        analise = self.motor_ia.analisar(
            aluno_id, notas, frequencia, atividades_entregues, atividades_esperadas, thresholds=thresholds
        )

        try:
            self.conn.execute(
                """
                INSERT INTO desempenhos
                (aluno_id, materia_id, notas_json, frequencia, atividades_entregues, atividades_esperadas, data_referencia)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    aluno_id,
                    materia_id,
                    json.dumps(notas),
                    frequencia,
                    atividades_entregues,
                    atividades_esperadas,
                    data_referencia,
                ),
            )
            self._persistir_analise(analise)
            self._registrar_auditoria(
                ator,
                "registrar_desempenho",
                "aluno",
                aluno_id,
                f"Registrou desempenho (frequencia={frequencia}) - risco resultante: {analise.nivel.value}.",
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        if analise.nivel == NivelRisco.ALTO:
            aluno = fetch_one(self.conn, "SELECT nome, matricula FROM alunos WHERE id = ?", (aluno_id,))
            if aluno:
                try:
                    enviar_alerta_risco(aluno["nome"], aluno["matricula"], analise.nivel.value, analise.mensagem)
                except Exception:
                    # Notificacao por email e best-effort: o registro de desempenho
                    # ja foi salvo com sucesso e nao deve ser afetado por uma
                    # falha de envio (SMTP fora do ar, credenciais invalidas etc.).
                    logger.exception("Falha ao notificar risco alto do aluno %s.", aluno_id)

        return {"aluno": self.obter_aluno(aluno_id), "analise": analise.to_dict()}

    def recalcular_riscos(self) -> dict[str, Any]:
        desempenhos = fetch_all(
            self.conn,
            """
            SELECT d.*
            FROM desempenhos d
            INNER JOIN (
                SELECT aluno_id, MAX(id) AS max_id
                FROM desempenhos
                GROUP BY aluno_id
            ) ult ON ult.max_id = d.id
            ORDER BY d.aluno_id
            """,
        )
        thresholds = self.obter_config_risco()
        analises = []
        for desempenho in desempenhos:
            analise = self.motor_ia.analisar(
                desempenho["aluno_id"],
                [float(nota) for nota in json.loads(desempenho["notas_json"])],
                float(desempenho["frequencia"]),
                optional_int(desempenho.get("atividades_entregues")),
                optional_int(desempenho.get("atividades_esperadas")),
                thresholds=thresholds,
            )
            self._persistir_analise(analise)
            analises.append(analise.to_dict())
        self.conn.commit()
        return {"total": len(analises), "analises": analises}

    def dashboard(self) -> dict[str, Any]:
        alunos = fetch_all(self.conn, "SELECT * FROM alunos")
        total = len(alunos)
        por_risco = {"Baixo": 0, "Medio": 0, "Alto": 0}
        for aluno in alunos:
            por_risco[aluno["status_risco"]] = por_risco.get(aluno["status_risco"], 0) + 1
        alertas = fetch_all(
            self.conn,
            """
            SELECT a.*, al.nome AS aluno_nome, al.matricula
            FROM alertas a
            JOIN alunos al ON al.id = a.aluno_id
            WHERE a.ativo = 1
            ORDER BY a.id DESC
            LIMIT 10
            """,
        )
        analises = fetch_all(
            self.conn,
            """
            SELECT an.*, al.nome AS aluno_nome
            FROM analises an
            JOIN alunos al ON al.id = an.aluno_id
            ORDER BY an.id DESC
            LIMIT 10
            """,
        )
        fator_risco_medio = sum(float(aluno["probabilidade_evasao"]) for aluno in alunos) / total if total else 0
        for analise in analises:
            normalize_fator_risco(analise)
        return {
            "indicadores": {
                "total_alunos": total,
                "alunos_em_risco": por_risco.get("Medio", 0) + por_risco.get("Alto", 0),
                "alertas_ativos": len(alertas),
                "fator_risco_medio": round(fator_risco_medio, 4),
            },
            "distribuicao_risco": por_risco,
            "alertas": alertas,
            "previsoes_recentes": analises,
        }

    # --- Plano de acao / case-tracking de intervencoes ----------------------

    INTERVENCAO_STATUS = ("Pendente", "Concluída")
    INTERVENCAO_TIPOS = ("Contato", "Reuniao", "Encaminhamento", "Outro")

    def listar_intervencoes(self, aluno_id: int) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT i.*, r.nome AS responsavel_nome, c.nome AS criado_por_nome
            FROM intervencoes i
            LEFT JOIN usuarios r ON r.id = i.responsavel_id
            LEFT JOIN usuarios c ON c.id = i.criado_por
            WHERE i.aluno_id = ?
            ORDER BY (i.status = 'Pendente') DESC, i.criado_em DESC
            """,
            (aluno_id,),
        )

    def registrar_intervencao(
        self, aluno_id: int, payload: dict[str, Any], ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self._ensure_aluno(aluno_id)
        tipo = require(payload, "tipo")
        descricao = (payload.get("descricao") or "").strip() or None
        responsavel_id = optional_int(payload.get("responsavel_id"))
        ator_id, ator_nome = _ator_info(ator)
        if responsavel_id is None:
            responsavel_id = ator_id
        try:
            cur = self.conn.execute(
                """
                INSERT INTO intervencoes (aluno_id, tipo, descricao, status, responsavel_id, criado_por)
                VALUES (?, ?, ?, 'Pendente', ?, ?)
                """,
                (aluno_id, tipo, descricao, responsavel_id, ator_id),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Responsavel informado nao existe.", 400)
        self._registrar_auditoria(
            ator, "criar", "intervencao", cur.lastrowid, f"Registrou intervencao '{tipo}' para o aluno {aluno_id}."
        )
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM intervencoes WHERE id = ?", (cur.lastrowid,))

    def atualizar_intervencao(
        self, intervencao_id: int, payload: dict[str, Any], ator: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        intervencao = fetch_one(self.conn, "SELECT * FROM intervencoes WHERE id = ?", (intervencao_id,))
        if not intervencao:
            raise AppError("Intervencao nao encontrada.", 404)
        campos: list[str] = ["atualizado_em = CURRENT_TIMESTAMP"]
        valores: list[Any] = []
        if "status" in payload:
            status = payload["status"]
            if status not in self.INTERVENCAO_STATUS:
                raise AppError(f"status deve ser um de: {', '.join(self.INTERVENCAO_STATUS)}.")
            campos.append("status = ?")
            valores.append(status)
            campos.append("resolvido_em = ?")
            valores.append(self._agora_iso() if status == "Concluída" else None)
        if "descricao" in payload:
            campos.append("descricao = ?")
            valores.append((payload.get("descricao") or "").strip() or None)
        if "responsavel_id" in payload:
            campos.append("responsavel_id = ?")
            valores.append(optional_int(payload.get("responsavel_id")))
        valores.append(intervencao_id)
        try:
            self.conn.execute(f"UPDATE intervencoes SET {', '.join(campos)} WHERE id = ?", valores)
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise AppError("Responsavel informado nao existe.", 400)
        self._registrar_auditoria(ator, "atualizar", "intervencao", intervencao_id, "Atualizou intervencao.")
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM intervencoes WHERE id = ?", (intervencao_id,))

    @staticmethod
    def _agora_iso() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Comparativo de turmas da mesma materia ------------------------------

    def comparativo_materias(self) -> list[dict[str, Any]]:
        """Compara turmas (linhas de `materias`) que compartilham o mesmo nome
        de materia mas tem professores diferentes, para destacar quando uma
        turma esta com indicadores de risco bem melhores/piores que a outra.
        """
        materias = fetch_all(
            self.conn,
            """
            SELECT m.*, u.nome AS professor_nome
            FROM materias m
            LEFT JOIN usuarios u ON u.id = m.professor_id
            WHERE m.ativo = 1
            ORDER BY m.nome
            """,
        )
        grupos: dict[str, list[dict[str, Any]]] = {}
        for materia in materias:
            chave = materia["nome"].strip().lower()
            grupos.setdefault(chave, []).append(materia)

        thresholds = self.obter_config_risco()
        resultado: list[dict[str, Any]] = []
        for turmas in grupos.values():
            professores_distintos = {t["professor_id"] for t in turmas if t["professor_id"] is not None}
            if len(turmas) < 2 or len(professores_distintos) < 2:
                continue
            turmas_info = []
            for turma in turmas:
                stats = self._estatisticas_turma(turma["id"], thresholds)
                turmas_info.append(
                    {
                        "materia_id": turma["id"],
                        "semestre": turma["semestre"],
                        "professor_id": turma["professor_id"],
                        "professor_nome": turma["professor_nome"],
                        **stats,
                    }
                )
            comparaveis = [t for t in turmas_info if t["total_desempenhos"] > 0]
            destaque_id = atencao_id = None
            if len(comparaveis) >= 2:
                melhor = min(comparaveis, key=lambda t: t["fator_risco_medio"])
                pior = max(comparaveis, key=lambda t: t["fator_risco_medio"])
                if melhor["materia_id"] != pior["materia_id"] and melhor["fator_risco_medio"] < pior["fator_risco_medio"]:
                    destaque_id = melhor["materia_id"]
                    atencao_id = pior["materia_id"]
            resultado.append(
                {
                    "materia_nome": turmas[0]["nome"],
                    "turmas": turmas_info,
                    "destaque_materia_id": destaque_id,
                    "atencao_materia_id": atencao_id,
                }
            )
        resultado.sort(key=lambda g: g["materia_nome"].lower())
        return resultado

    def _estatisticas_turma(self, materia_id: int, thresholds: dict[str, float]) -> dict[str, Any]:
        desempenhos = fetch_all(self.conn, "SELECT * FROM desempenhos WHERE materia_id = ?", (materia_id,))
        total_alunos_row = fetch_one(
            self.conn,
            "SELECT COUNT(DISTINCT aluno_id) AS total FROM matriculas WHERE materia_id = ? AND ativa = 1",
            (materia_id,),
        )
        total_alunos = total_alunos_row["total"] if total_alunos_row else 0
        if not desempenhos:
            return {
                "total_desempenhos": 0,
                "total_alunos": total_alunos,
                "media_geral": None,
                "frequencia_media": None,
                "fator_risco_medio": None,
                "nivel_risco": None,
            }
        medias: list[float] = []
        frequencias: list[float] = []
        deficits: list[float] = []
        for desempenho in desempenhos:
            notas = [float(nota) for nota in json.loads(desempenho["notas_json"])]
            if notas:
                medias.append(sum(notas) / len(notas))
            frequencias.append(float(desempenho["frequencia"]))
            entregues = optional_int(desempenho.get("atividades_entregues"))
            esperadas = optional_int(desempenho.get("atividades_esperadas"))
            if entregues is not None and esperadas:
                deficits.append(max(0.0, 1.0 - (entregues / esperadas)))
        media_geral = sum(medias) / len(medias) if medias else 0.0
        frequencia_media = sum(frequencias) / len(frequencias) if frequencias else 0.0
        deficit_medio = sum(deficits) / len(deficits) if deficits else 0.0
        fator_risco_medio = self.motor_ia.calcular_fator_risco(media_geral, frequencia_media, deficit_medio)
        nivel, _ = self.motor_ia.classificar(media_geral, frequencia_media, deficit_medio, fator_risco_medio, thresholds)
        return {
            "total_desempenhos": len(desempenhos),
            "total_alunos": total_alunos,
            "media_geral": round(media_geral, 2),
            "frequencia_media": round(frequencia_media, 2),
            "fator_risco_medio": round(fator_risco_medio, 4),
            "nivel_risco": nivel.value,
        }

    def listar_alertas(self) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT a.*, al.nome AS aluno_nome, al.matricula
            FROM alertas a
            JOIN alunos al ON al.id = a.aluno_id
            ORDER BY a.ativo DESC, a.id DESC
            """,
        )

    def listar_relatorios(self) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT r.*, u.nome AS criado_por_nome
            FROM relatorios r
            LEFT JOIN usuarios u ON u.id = r.criado_por
            ORDER BY r.id DESC
            """,
        )

    def criar_relatorio(self, payload: dict[str, Any], usuario_id: int | None = None) -> dict[str, Any]:
        tipo = payload.get("tipo", "desempenho")
        titulo = payload.get("titulo", f"Relatorio de {tipo}")
        conteudo = payload.get("conteudo") or self._montar_relatorio_texto()
        cur = self.conn.execute(
            """
            INSERT INTO relatorios (titulo, tipo, conteudo, criado_por)
            VALUES (?, ?, ?, ?)
            """,
            (titulo, tipo, conteudo, usuario_id),
        )
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM relatorios WHERE id = ?", (cur.lastrowid,))

    def _montar_relatorio_texto(self) -> str:
        """Conteudo padrao (texto legivel) usado quando `criar_relatorio()` nao
        recebe `conteudo` explicito -- antes era um dump de JSON do dashboard,
        o que ficava ilegivel para quem nao e tecnico; agora monta um relatorio
        em texto corrido, com as mesmas informacoes do dashboard."""
        dados = self.dashboard()
        indicadores = dados["indicadores"]
        distribuicao = dados["distribuicao_risco"]

        linhas: list[str] = []
        linhas.append("RELATORIO GERAL DO SISTEMA")
        linhas.append(f"Gerado em: {now_iso().replace('T', ' ')}")
        linhas.append("")
        linhas.append("INDICADORES GERAIS")
        linhas.append(f"  Total de alunos cadastrados: {indicadores['total_alunos']}")
        linhas.append(f"  Alunos em risco (Medio + Alto): {indicadores['alunos_em_risco']}")
        linhas.append(f"  Alertas ativos: {indicadores['alertas_ativos']}")
        linhas.append(f"  Fator de risco medio da turma: {indicadores['fator_risco_medio']:.2f}")
        linhas.append("")
        linhas.append("DISTRIBUICAO POR NIVEL DE RISCO")
        for nivel in ("Baixo", "Medio", "Alto"):
            linhas.append(f"  {nivel}: {distribuicao.get(nivel, 0)} aluno(s)")
        linhas.append("")
        linhas.append("ALERTAS ATIVOS MAIS RECENTES")
        if dados["alertas"]:
            for alerta in dados["alertas"]:
                linhas.append(
                    f"  - {alerta['aluno_nome']} (matricula {alerta['matricula']}), "
                    f"risco {alerta['nivel_risco']}: {alerta['mensagem']}"
                )
        else:
            linhas.append("  Nenhum alerta ativo no momento.")
        linhas.append("")
        linhas.append("ANALISES DE RISCO MAIS RECENTES")
        if dados["previsoes_recentes"]:
            for analise in dados["previsoes_recentes"]:
                linhas.append(
                    f"  - {analise['aluno_nome']}: risco {analise['nivel_risco']}, "
                    f"media {float(analise['media_notas']):.1f}, frequencia {float(analise['frequencia']):.0f}%"
                )
        else:
            linhas.append("  Nenhuma analise registrada ainda.")
        return "\n".join(linhas)

    def _persistir_analise(self, analise: AnaliseRisco) -> None:
        status = {
            NivelRisco.BAIXO: StatusAluno.REGULAR.value,
            NivelRisco.MEDIO: StatusAluno.RISCO_MEDIO.value,
            NivelRisco.ALTO: StatusAluno.RISCO_ALTO.value,
        }[analise.nivel]
        self.conn.execute(
            """
            INSERT INTO analises
            (aluno_id, nivel_risco, probabilidade_evasao, media_notas, frequencia,
             atividades_entregues, atividades_esperadas, mensagem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analise.aluno_id,
                analise.nivel.value,
                analise.fator_risco,
                analise.media_notas,
                analise.frequencia,
                analise.atividades_entregues,
                analise.atividades_esperadas,
                analise.mensagem,
            ),
        )
        self.conn.execute(
            """
            UPDATE alunos
            SET status = ?, status_risco = ?, probabilidade_evasao = ?
            WHERE id = ?
            """,
            (status, analise.nivel.value, analise.fator_risco, analise.aluno_id),
        )
        self.conn.execute("UPDATE alertas SET ativo = 0, resolvido_em = CURRENT_TIMESTAMP WHERE aluno_id = ?", (analise.aluno_id,))
        if analise.nivel in {NivelRisco.MEDIO, NivelRisco.ALTO}:
            self.conn.execute(
                """
                INSERT INTO alertas (aluno_id, mensagem, nivel_risco)
                VALUES (?, ?, ?)
                """,
                (analise.aluno_id, analise.mensagem, analise.nivel.value),
            )

    def _materias_do_aluno(self, aluno_id: int) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT m.*
            FROM materias m
            JOIN matriculas ma ON ma.materia_id = m.id
            WHERE ma.aluno_id = ? AND ma.ativa = 1
            ORDER BY m.nome
            """,
            (aluno_id,),
        )

    def _ultima_analise(self, aluno_id: int) -> dict[str, Any] | None:
        analise = fetch_one(
            self.conn,
            "SELECT * FROM analises WHERE aluno_id = ? ORDER BY id DESC LIMIT 1",
            (aluno_id,),
        )
        if analise:
            normalize_fator_risco(analise)
        return analise

    def _ensure_aluno(self, aluno_id: int) -> dict[str, Any]:
        aluno = fetch_one(self.conn, "SELECT * FROM alunos WHERE id = ?", (aluno_id,))
        if not aluno:
            raise AppError("Aluno nao encontrado.", 404)
        return aluno

    def _ensure_aluno_ativo(self, aluno_id: int) -> None:
        aluno = fetch_one(self.conn, "SELECT id, ativo FROM alunos WHERE id = ?", (aluno_id,))
        if not aluno:
            raise AppError("Aluno nao encontrado.", 404)
        if not aluno.get("ativo", 1):
            raise AppError("Aluno esta inativo. Reative o cadastro antes de continuar.", 400)

    def _ensure_materia(self, materia_id: int) -> dict[str, Any]:
        materia = fetch_one(self.conn, "SELECT * FROM materias WHERE id = ?", (materia_id,))
        if not materia:
            raise AppError("Materia nao encontrada.", 404)
        return materia

    def _ensure_materia_ativa(self, materia_id: int) -> dict[str, Any]:
        materia = fetch_one(self.conn, "SELECT * FROM materias WHERE id = ?", (materia_id,))
        if not materia:
            raise AppError("Materia nao encontrada.", 404)
        if not materia.get("ativo", 1):
            raise AppError("Materia esta inativa. Reative antes de continuar.", 400)
        return materia

    def _ensure_usuario(self, usuario_id: int) -> dict[str, Any]:
        usuario = fetch_one(self.conn, "SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        if not usuario:
            raise AppError("Usuario nao encontrado.", 404)
        return usuario


def require(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if value is None or value == "":
        raise AppError(f"Campo obrigatorio ausente: {field}.")
    return value


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AppError("Valor informado deve ser um numero inteiro.")


def normalize_fator_risco(row: dict[str, Any]) -> None:
    if "probabilidade_evasao" in row:
        row["fator_risco"] = row.pop("probabilidade_evasao")
