from __future__ import annotations

import hashlib
import sqlite3
import time
import unittest
from uuid import uuid4

from app.database import init_db, seed_db
from app.api import Application
from app.models import NivelRisco
from app.services import AcademicService, AppError, AuthService, DEFAULT_RISCO_THRESHOLDS, MotorIA
from app import notifications


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_db(self.conn)
        seed_db(self.conn)
        self.service = AcademicService(self.conn, MotorIA())

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

    def test_recalcular_riscos_processa_ultimos_desempenhos(self) -> None:
        result = self.service.recalcular_riscos()
        self.assertEqual(result["total"], 3)

    def test_rota_inicial_publica_existe(self) -> None:
        app = Application()
        status, payload = app.dispatch("GET", "/", {}, {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "online")

    def test_professor_nao_pode_cadastrar_aluno(self) -> None:
        app = Application()
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
        app = Application()
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

    # --- Sessao (logout, expiracao, migracao de hash legado) ---------------

    def test_logout_invalida_sessao(self) -> None:
        auth = AuthService(self.conn)
        login = auth.login("professor@sigma.edu", "professor123")
        token = f"Bearer {login['token']}"
        self.assertIsNotNone(auth.current_user(token))
        auth.logout(token)
        self.assertIsNone(auth.current_user(token))

    def test_sessao_expirada_retorna_none(self) -> None:
        auth = AuthService(self.conn)
        login = auth.login("professor@sigma.edu", "professor123")
        self.conn.execute(
            "UPDATE sessoes SET expira_em = ? WHERE token = ?",
            (time.time() - 10, login["token"]),
        )
        self.conn.commit()
        self.assertIsNone(auth.current_user(f"Bearer {login['token']}"))

    def test_login_migra_hash_legado(self) -> None:
        senha = "legado123"
        legado_hash = hashlib.sha256(senha.encode("utf-8")).hexdigest()
        self.conn.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?)",
            ("Usuario Legado", "legado@sigma.edu", legado_hash, "professor"),
        )
        self.conn.commit()
        auth = AuthService(self.conn)
        result = auth.login("legado@sigma.edu", senha)
        self.assertIn("token", result)
        row = self.conn.execute(
            "SELECT senha_hash FROM usuarios WHERE email = ?", ("legado@sigma.edu",)
        ).fetchone()
        self.assertIn("$", row[0])

    def test_rate_limit_bloqueia_apos_tentativas(self) -> None:
        auth = AuthService(self.conn)
        email = "professor@sigma.edu"
        for _ in range(AuthService.MAX_TENTATIVAS):
            with self.assertRaises(AppError) as ctx:
                auth.login(email, "senha_errada")
            self.assertEqual(ctx.exception.status, 401)
        with self.assertRaises(AppError) as ctx:
            auth.login(email, "senha_errada")
        self.assertEqual(ctx.exception.status, 429)

    def test_desativar_usuario_revoga_sessao(self) -> None:
        app = Application()
        professor_login = app.auth.login("professor@sigma.edu", "professor123")
        gestor_login = app.auth.login("gestor@sigma.edu", "gestor123")
        status, _ = app.dispatch(
            "DELETE",
            "/usuarios/1",
            {},
            {"authorization": f"Bearer {gestor_login['token']}"},
        )
        self.assertEqual(status, 200)
        self.assertIsNone(app.auth.current_user(f"Bearer {professor_login['token']}"))

    # --- CRUD: editar/desativar usuario, aluno, materia ---------------------

    def test_atualizar_usuario(self) -> None:
        atualizado = self.service.atualizar_usuario(1, {"nome": "Ana Atualizada"})
        self.assertEqual(atualizado["nome"], "Ana Atualizada")

    def test_criar_usuario_email_duplicado_retorna_409(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.criar_usuario(
                {
                    "nome": "Outro Professor",
                    "email": "professor@sigma.edu",
                    "senha": "senha123",
                    "perfil": "professor",
                }
            )
        self.assertEqual(ctx.exception.status, 409)

    def test_desativar_ultimo_gestor_falha(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.desativar_usuario(2)
        self.assertEqual(ctx.exception.status, 400)

    def test_atualizar_materia(self) -> None:
        atualizada = self.service.atualizar_materia(1, {"nome": "Calculo II"})
        self.assertEqual(atualizada["nome"], "Calculo II")

    def test_atualizar_aluno(self) -> None:
        atualizado = self.service.atualizar_aluno(1, {"status": "Aprovado"})
        self.assertEqual(atualizado["status"], "Aprovado")

    def test_desativar_aluno_bloqueia_registrar_desempenho(self) -> None:
        self.service.desativar_aluno(1)
        with self.assertRaises(AppError) as ctx:
            self.service.registrar_desempenho(1, {"notas": [8.0], "frequencia": 90})
        self.assertEqual(ctx.exception.status, 400)

    def test_vincular_materia_bloqueada_quando_materia_inativa(self) -> None:
        self.service.desativar_materia(3)
        with self.assertRaises(AppError):
            self.service.vincular_materia(1, 3)

    # --- Migracoes versionadas ------------------------------------------------

    def test_migracoes_sao_registradas_na_schema_migrations(self) -> None:
        linhas = self.conn.execute("SELECT versao FROM schema_migrations ORDER BY versao").fetchall()
        versoes = [linha["versao"] for linha in linhas]
        self.assertEqual(versoes, [1, 2])

    def test_init_db_e_idempotente(self) -> None:
        # Chamar init_db novamente (ex.: segundo boot do processo) nao deve
        # duplicar migracoes nem falhar por colunas/indices ja existentes.
        init_db(self.conn)
        linhas = self.conn.execute("SELECT versao FROM schema_migrations").fetchall()
        self.assertEqual(len(linhas), 2)

    # --- Auditoria -------------------------------------------------------------

    def test_criar_aluno_registra_auditoria(self) -> None:
        ator = {"id": 2, "nome": "Bruno Gestor"}
        aluno = self.service.criar_aluno({"nome": "Felipe Teste", "matricula": "AUD001"}, ator=ator)
        auditoria = self.service.listar_auditoria()
        entrada = next(item for item in auditoria["itens"] if item["entidade_id"] == aluno["id"] and item["entidade"] == "aluno")
        self.assertEqual(entrada["acao"], "criar")
        self.assertEqual(entrada["usuario_id"], 2)
        self.assertEqual(entrada["usuario_nome"], "Bruno Gestor")

    def test_desativar_usuario_registra_auditoria_sem_ator(self) -> None:
        self.service.criar_usuario(
            {"nome": "Carlos Professor", "email": "carlos@sigma.edu", "senha": "senha123", "perfil": "professor"}
        )
        usuarios = self.service.listar_usuarios()
        novo = next(u for u in usuarios if u["email"] == "carlos@sigma.edu")
        self.service.desativar_usuario(novo["id"])
        auditoria = self.service.listar_auditoria()
        entrada = next(item for item in auditoria["itens"] if item["entidade_id"] == novo["id"] and item["acao"] == "desativar")
        self.assertIsNone(entrada["usuario_id"])

    def test_reativar_usuario_gera_acao_reativar(self) -> None:
        self.service.atualizar_usuario(1, {"ativo": False})
        self.service.atualizar_usuario(1, {"ativo": True})
        auditoria = self.service.listar_auditoria()
        acoes = [item["acao"] for item in auditoria["itens"] if item["entidade_id"] == 1 and item["entidade"] == "usuario"]
        self.assertIn("reativar", acoes)

    def test_listar_auditoria_pagina_resultados(self) -> None:
        for indice in range(5):
            self.service.criar_aluno({"nome": f"Aluno Pag {indice}", "matricula": f"PAG{indice}"})
        pagina = self.service.listar_auditoria(pagina=1, tamanho_pagina=2)
        self.assertEqual(len(pagina["itens"]), 2)
        self.assertGreaterEqual(pagina["total"], 5)

    # --- Importacao de alunos via CSV ------------------------------------------

    def test_importar_alunos_csv_sucesso(self) -> None:
        csv_texto = "nome,matricula,email\nJoao Importado,IMP001,joao@sigma.edu\nMaria Importada,IMP002,\n"
        resultado = self.service.importar_alunos_csv(csv_texto)
        self.assertEqual(resultado["importados"], 2)
        self.assertEqual(resultado["erros"], [])

    def test_importar_alunos_csv_reporta_erros_sem_interromper(self) -> None:
        csv_texto = (
            "nome,matricula\n"
            "Aluno Valido,IMP010\n"
            ",\n"
            "Carla Lima,2026001\n"  # matricula ja existe no seed
        )
        resultado = self.service.importar_alunos_csv(csv_texto)
        self.assertEqual(resultado["importados"], 1)
        self.assertEqual(len(resultado["erros"]), 2)

    def test_importar_alunos_csv_sem_cabecalho_valido_falha(self) -> None:
        with self.assertRaises(AppError):
            self.service.importar_alunos_csv("coluna_errada\nvalor\n")

    def test_importar_alunos_csv_vazio_falha(self) -> None:
        with self.assertRaises(AppError):
            self.service.importar_alunos_csv("   ")

    # --- Paginacao e filtro de /alunos -----------------------------------------

    def test_listar_alunos_pagina_e_filtra(self) -> None:
        pagina = self.service.listar_alunos(pagina=1, tamanho_pagina=2)
        self.assertEqual(pagina["tamanho_pagina"], 2)
        self.assertEqual(len(pagina["itens"]), 2)
        self.assertEqual(pagina["total"], 3)

    def test_listar_alunos_filtra_por_termo(self) -> None:
        resultado = self.service.listar_alunos(termo="carla")
        self.assertEqual(resultado["total"], 1)
        self.assertEqual(resultado["itens"][0]["nome"], "Carla Lima")

    def test_listar_alunos_filtra_por_risco(self) -> None:
        resultado = self.service.listar_alunos(risco="Alto")
        self.assertTrue(all(item["status_risco"] == "Alto" for item in resultado["itens"]))

    def test_listar_alunos_filtra_por_materia(self) -> None:
        # No seed: materia 1 (Calculo I) tem os alunos 1 (Carla) e 2 (Diego)
        # matriculados -- usado pela tela "Minhas Turmas" do professor.
        resultado = self.service.listar_alunos(materia_id=1)
        nomes = {item["nome"] for item in resultado["itens"]}
        self.assertEqual(resultado["total"], 2)
        self.assertEqual(nomes, {"Carla Lima", "Diego Souza"})

    # --- Notificacao por email (best-effort, sem rede) --------------------------

    def test_notificacoes_desativadas_por_padrao(self) -> None:
        self.assertFalse(notifications.notificacoes_habilitadas())

    def test_registrar_desempenho_alto_risco_nao_falha_sem_smtp_configurado(self) -> None:
        # Sem SIGMA_SMTP_HOST/SIGMA_ALERTA_EMAIL_TO configurados, o envio deve
        # ser silenciosamente ignorado -- a chamada principal nao pode falhar.
        resultado = self.service.registrar_desempenho(
            1, {"materia_id": 1, "notas": [2.0, 3.0], "frequencia": 40}
        )
        self.assertEqual(resultado["analise"]["nivel"], "Alto")

    # --- Motor de risco: thresholds configuraveis -------------------------------

    def test_motor_ia_classificar_usa_thresholds_padrao(self) -> None:
        fator = MotorIA.calcular_fator_risco(media=8.0, frequencia=95.0, deficit_atividades=0.0)
        nivel, _ = MotorIA.classificar(8.0, 95.0, 0.0, fator)
        self.assertEqual(nivel, NivelRisco.BAIXO)

    def test_motor_ia_classificar_aceita_thresholds_customizados(self) -> None:
        # media 6.5 cai por padrao em Medio (< medio_media=7.0, mas >= alto_media=5.0).
        # Com um limiar de media "Alto" mais permissivo (8.0), a mesma media
        # passa a ser classificada como Alto.
        fator = MotorIA.calcular_fator_risco(media=6.5, frequencia=90.0, deficit_atividades=0.0)
        nivel_padrao, _ = MotorIA.classificar(6.5, 90.0, 0.0, fator)
        nivel_customizado, _ = MotorIA.classificar(6.5, 90.0, 0.0, fator, thresholds={"alto_media": 8.0})
        self.assertEqual(nivel_padrao, NivelRisco.MEDIO)
        self.assertEqual(nivel_customizado, NivelRisco.ALTO)

    # --- Limiares de risco configuraveis (persistidos) ---------------------------

    def test_obter_config_risco_retorna_padroes_quando_nao_configurado(self) -> None:
        self.assertEqual(self.service.obter_config_risco(), DEFAULT_RISCO_THRESHOLDS)

    def test_atualizar_config_risco_persiste_e_mescla_com_padroes(self) -> None:
        atualizado = self.service.atualizar_config_risco({"alto_media": 6.0})
        self.assertEqual(atualizado["alto_media"], 6.0)
        novamente = self.service.obter_config_risco()
        self.assertEqual(novamente["alto_media"], 6.0)
        self.assertEqual(novamente["medio_media"], DEFAULT_RISCO_THRESHOLDS["medio_media"])

    def test_atualizar_config_risco_rejeita_valor_fora_da_faixa(self) -> None:
        with self.assertRaises(AppError):
            self.service.atualizar_config_risco({"alto_frequencia": 150})

    def test_atualizar_config_risco_sem_campos_validos_falha(self) -> None:
        with self.assertRaises(AppError):
            self.service.atualizar_config_risco({"campo_inexistente": 1})

    def test_config_risco_influencia_classificacao_em_registrar_desempenho(self) -> None:
        self.service.atualizar_config_risco({"alto_media": 9.5})
        resultado = self.service.registrar_desempenho(1, {"materia_id": 1, "notas": [8.0], "frequencia": 95})
        self.assertEqual(resultado["analise"]["nivel"], "Alto")

    # --- Plano de acao / intervencoes ---------------------------------------------

    def test_registrar_intervencao_cria_pendente(self) -> None:
        intervencao = self.service.registrar_intervencao(
            1, {"tipo": "Contato", "descricao": "Liguei para o responsavel."}, ator={"id": 2, "nome": "Bruno Gestor"}
        )
        self.assertEqual(intervencao["status"], "Pendente")
        self.assertEqual(intervencao["aluno_id"], 1)
        self.assertEqual(intervencao["criado_por"], 2)

    def test_listar_intervencoes_ordena_pendentes_primeiro(self) -> None:
        self.service.registrar_intervencao(1, {"tipo": "Contato"})
        concluida = self.service.registrar_intervencao(1, {"tipo": "Reuniao"})
        self.service.atualizar_intervencao(concluida["id"], {"status": "Concluída"})
        itens = self.service.listar_intervencoes(1)
        self.assertEqual(itens[0]["status"], "Pendente")

    def test_atualizar_intervencao_para_concluida_define_resolvido_em(self) -> None:
        intervencao = self.service.registrar_intervencao(1, {"tipo": "Contato"})
        atualizada = self.service.atualizar_intervencao(intervencao["id"], {"status": "Concluída"})
        self.assertEqual(atualizada["status"], "Concluída")
        self.assertIsNotNone(atualizada["resolvido_em"])

    def test_atualizar_intervencao_status_invalido_falha(self) -> None:
        intervencao = self.service.registrar_intervencao(1, {"tipo": "Contato"})
        with self.assertRaises(AppError):
            self.service.atualizar_intervencao(intervencao["id"], {"status": "Invalido"})

    def test_atualizar_intervencao_inexistente_404(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.atualizar_intervencao(9999, {"status": "Concluída"})
        self.assertEqual(ctx.exception.status, 404)

    def test_registrar_intervencao_aluno_inexistente_404(self) -> None:
        with self.assertRaises(AppError) as ctx:
            self.service.registrar_intervencao(9999, {"tipo": "Contato"})
        self.assertEqual(ctx.exception.status, 404)

    def test_obter_aluno_inclui_intervencoes(self) -> None:
        self.service.registrar_intervencao(1, {"tipo": "Contato"})
        aluno = self.service.obter_aluno(1)
        self.assertEqual(len(aluno["intervencoes"]), 1)

    # --- Alterar senha self-service -----------------------------------------------

    def test_alterar_senha_sucesso(self) -> None:
        auth = AuthService(self.conn)
        auth.alterar_senha(1, "professor123", "novaSenha456")
        login = auth.login("professor@sigma.edu", "novaSenha456")
        self.assertIn("token", login)

    def test_alterar_senha_atual_incorreta_falha(self) -> None:
        auth = AuthService(self.conn)
        with self.assertRaises(AppError) as ctx:
            auth.alterar_senha(1, "senha_errada", "novaSenha456")
        self.assertEqual(ctx.exception.status, 401)

    def test_alterar_senha_curta_falha(self) -> None:
        auth = AuthService(self.conn)
        with self.assertRaises(AppError):
            auth.alterar_senha(1, "professor123", "123")

    # --- Comparativo de turmas da mesma materia -----------------------------------

    def test_comparativo_materias_detecta_grupo_com_dois_professores(self) -> None:
        outro_professor = self.service.criar_usuario(
            {"nome": "Outro Professor", "email": "outro@sigma.edu", "senha": "senha123", "perfil": "professor"}
        )
        nova_turma = self.service.criar_materia(
            {"nome": "Calculo I", "carga_horaria": 80, "semestre": "2026.1", "professor_id": outro_professor["id"]}
        )
        # Turma nova com desempenho bem melhor que a turma 1 (mesma materia,
        # professor original do seed) para o comparativo detectar destaque/atencao.
        self.service.registrar_desempenho(
            2, {"materia_id": nova_turma["id"], "notas": [9.5, 10.0, 9.0], "frequencia": 98}
        )
        comparativo = self.service.comparativo_materias()
        grupo = next(g for g in comparativo if g["materia_nome"] == "Calculo I")
        self.assertEqual(len(grupo["turmas"]), 2)
        self.assertEqual(grupo["destaque_materia_id"], nova_turma["id"])
        self.assertEqual(grupo["atencao_materia_id"], 1)

    def test_comparativo_materias_ignora_grupos_com_professor_unico(self) -> None:
        # No seed, todas as materias (Calculo I, Programacao, Logica) tem o
        # mesmo professor (id 1) -- nenhum grupo deve aparecer no comparativo.
        comparativo = self.service.comparativo_materias()
        self.assertEqual(comparativo, [])


if __name__ == "__main__":
    unittest.main()
