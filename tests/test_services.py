from __future__ import annotations

import sqlite3
import unittest
from uuid import uuid4

from app.database import init_db, seed_db
from app.api import Application
from app.services import AcademicService, AppError, AuthService, MotorIA


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_db(self.conn)
        seed_db(self.conn)
        self.service = AcademicService(self.conn, MotorIA())

    def tearDown(self) -> None:
        self.conn.close()

    def test_login_valido_retorna_token(self) -> None:
        auth = AuthService(self.conn)
        result = auth.login("professor@sigma.edu", "professor123")
        self.assertIn("token", result)
        self.assertEqual(result["usuario"]["perfil"], "professor")

    def test_registrar_desempenho_alto_risco_gera_alerta(self) -> None:
        result = self.service.registrar_desempenho(
            1,
            {"materia_id": 1, "notas": [2.0, 3.0, 4.0], "frequencia": 50},
        )
        self.assertEqual(result["analise"]["nivel"], "Alto")
        self.assertIn("fator_risco", result["analise"])
        self.assertNotIn("probabilidade_evasao", result["analise"])
        dashboard = self.service.dashboard()
        self.assertGreaterEqual(dashboard["indicadores"]["alertas_ativos"], 1)

    def test_atividades_entregues_influenciam_risco(self) -> None:
        result = self.service.registrar_desempenho(
            1,
            {
                "materia_id": 1,
                "notas": [8.0, 8.5, 9.0],
                "frequencia": 95,
                "atividades_entregues": 1,
                "atividades_esperadas": 4,
            },
        )
        self.assertEqual(result["analise"]["nivel"], "Alto")
        self.assertEqual(result["analise"]["atividades_entregues"], 1)
        self.assertEqual(result["analise"]["atividades_esperadas"], 4)

    def test_registrar_desempenho_rejeita_nota_negativa(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.registrar_desempenho(
                1,
                {"materia_id": 1, "notas": [7.0, -1.0], "frequencia": 80},
            )

        self.assertEqual(ctx.exception.message, "Notas devem estar entre 0 e 10.")
        total = self.conn.execute("SELECT COUNT(*) FROM desempenhos WHERE notas_json LIKE '%-1.0%'").fetchone()[0]
        self.assertEqual(total, 0)

    def test_registrar_desempenho_rejeita_frequencia_negativa(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.registrar_desempenho(
                1,
                {"materia_id": 1, "notas": [7.0, 8.0], "frequencia": -10},
            )

        self.assertEqual(ctx.exception.message, "Frequencia deve estar entre 0 e 100.")

    def test_registrar_desempenho_rejeita_atividades_esperadas_zero(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.registrar_desempenho(
                1,
                {
                    "materia_id": 1,
                    "notas": [7.0, 8.0],
                    "frequencia": 80,
                    "atividades_entregues": 1,
                    "atividades_esperadas": 0,
                },
            )

        self.assertEqual(ctx.exception.message, "Atividades esperadas deve ser maior que zero.")

    def test_registrar_desempenho_rejeita_atividades_entregues_sem_esperadas(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.registrar_desempenho(
                1,
                {
                    "materia_id": 1,
                    "notas": [7.0, 8.0],
                    "frequencia": 80,
                    "atividades_entregues": 1,
                },
            )

        self.assertEqual(
            ctx.exception.message,
            "Atividades esperadas deve ser informada junto com atividades entregues.",
        )

    def test_criar_materia_rejeita_carga_horaria_negativa(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.criar_materia(
                {"nome": "Turma Teste", "carga_horaria": -40, "semestre": "2026.1"},
            )

        self.assertEqual(ctx.exception.message, "Carga horaria deve ser maior que zero.")

    def test_recalcular_riscos_processa_ultimos_desempenhos(self) -> None:
        expected = self.conn.execute(
            "SELECT COUNT(DISTINCT aluno_id) FROM desempenhos"
        ).fetchone()[0]
        result = self.service.recalcular_riscos()
        self.assertEqual(result["total"], expected)

    def test_alerta_pode_ser_resolvido_e_reaberto(self) -> None:
        self.service.recalcular_riscos()
        alerta_id = self.conn.execute(
            "SELECT id FROM alertas WHERE ativo = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]

        resolvido = self.service.atualizar_status_alerta(alerta_id, False)
        self.assertEqual(resolvido["ativo"], 0)
        self.assertIsNotNone(resolvido["resolvido_em"])

        reaberto = self.service.atualizar_status_alerta(alerta_id, True)
        self.assertEqual(reaberto["ativo"], 1)
        self.assertIsNone(reaberto["resolvido_em"])

    def test_rota_pode_resolver_alerta(self) -> None:
        self.service.recalcular_riscos()
        alerta_id = self.conn.execute(
            "SELECT id FROM alertas WHERE ativo = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        app = Application(self.conn)
        login = app.auth.login("professor@sigma.edu", "professor123")

        status, payload = app.dispatch(
            "PATCH",
            f"/alertas/{alerta_id}",
            {"ativo": False},
            {"authorization": f"Bearer {login['token']}"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["ativo"], 0)
        self.assertIsNotNone(payload["resolvido_em"])

    def test_rota_inicial_publica_existe(self) -> None:
        app = Application(self.conn)
        status, payload = app.dispatch("GET", "/", {}, {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "online")

    def test_professor_nao_pode_cadastrar_aluno(self) -> None:
        app = Application(self.conn)
        login = app.auth.login("professor@sigma.edu", "professor123")
        with self.assertRaises(Exception) as ctx:
            app.dispatch(
                "POST",
                "/alunos",
                {"nome": "Aluno Teste", "matricula": "T001"},
                {"authorization": f"Bearer {login['token']}"},
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_gestor_pode_cadastrar_aluno(self) -> None:
        app = Application(self.conn)
        login = app.auth.login("gestor@sigma.edu", "gestor123")
        matricula = f"G{uuid4().hex[:8]}"
        status, payload = app.dispatch(
            "POST",
            "/alunos",
            {"nome": "Aluno Gestor", "matricula": matricula},
            {"authorization": f"Bearer {login['token']}"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["matricula"], matricula)


if __name__ == "__main__":
    unittest.main()
