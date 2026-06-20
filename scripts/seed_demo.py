"""Script standalone para popular o banco com uma base de dados de demonstracao.

Reseta completamente data/academico.db (apaga e recria o esquema do zero,
SEM passar por `seed_db()` -- ou seja, NAO eh o seed minimo usado nos testes
automatizados) e povoa um cenario rico, passando por `AcademicService`/
`AuthService` (e nao por INSERTs diretos), para que auditoria, alertas e
analises de risco sejam gerados de forma realista, exatamente como aconteceria
em uso normal do sistema.

O cenario cobre todas as funcionalidades do sistema:
  - 2 perfis (professor e gestor), incluindo um segundo professor e um
    segundo gestor, e um professor INATIVO (para testar reativacao).
  - 6 materias, incluindo duas turmas de "Calculo I" com professores
    diferentes (para o comparativo entre turmas) e uma materia INATIVA.
  - 12 alunos cobrindo risco Baixo, Medio, Alto, "sem analise ainda"
    (recem-matriculado) e um aluno INATIVO -- mais de 10, para exercitar
    a paginacao do frontend.
  - Varios desempenhos por aluno (historico), gerando alertas automaticos
    para os alunos em risco Alto.
  - Intervencoes (plano de acao) pendentes e concluidas.
  - Relatorios gerados.
  - Um recalculo de risco final, para deixar tudo consistente.
  - Um arquivo de exemplo `data/exemplo_importacao.csv` com uma linha valida,
    uma duplicada e uma incompleta, para testar a importacao de alunos via CSV.

Uso:
    python scripts/seed_demo.py
        Reseta o banco e popula a base de demonstracao (pede confirmacao).

    python scripts/seed_demo.py --sim
        Mesma coisa, sem pedir confirmacao (util em scripts nao interativos).

IMPORTANTE: pare o servidor (run.py) antes de rodar -- caso contrario o
processo em execucao pode sobrescrever o banco gerado por este script.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import DATA_DIR, DB_PATH, connect, init_db  # noqa: E402
from app.services import AcademicService, AppError, MotorIA  # noqa: E402


def ator(usuario: dict[str, Any]) -> dict[str, Any]:
    """Monta o dict `ator` esperado pelos metodos de AcademicService a partir
    do dict retornado por `criar_usuario`."""
    return {"id": usuario["id"], "nome": usuario["nome"]}


SEED_ATOR = {"id": None, "nome": "Script de seed (demo)"}


def resetar_banco() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for sufixo in ("", "-journal", "-wal", "-shm"):
        caminho = DB_PATH.with_name(DB_PATH.name + sufixo) if sufixo else DB_PATH
        if caminho.exists():
            caminho.unlink()


def criar_usuarios(academic: AcademicService) -> dict[str, dict[str, Any]]:
    usuarios = {}
    usuarios["ana"] = academic.criar_usuario(
        {
            "nome": "Ana Professora",
            "email": "professor@sigma.edu",
            "senha": "professor123",
            "perfil": "professor",
            "especializacao": "Matematica",
        },
        ator=SEED_ATOR,
    )
    usuarios["bruno"] = academic.criar_usuario(
        {
            "nome": "Bruno Gestor",
            "email": "gestor@sigma.edu",
            "senha": "gestor123",
            "perfil": "gestor",
            "cargo": "Coordenador Academico",
        },
        ator=SEED_ATOR,
    )
    usuarios["camila"] = academic.criar_usuario(
        {
            "nome": "Camila Tavares",
            "email": "professor2@sigma.edu",
            "senha": "professor123",
            "perfil": "professor",
            "especializacao": "Ciencia da Computacao",
        },
        ator=ator(usuarios["bruno"]),
    )
    usuarios["diana"] = academic.criar_usuario(
        {
            "nome": "Diana Ramos",
            "email": "gestor2@sigma.edu",
            "senha": "gestor123",
            "perfil": "gestor",
            "cargo": "Vice-coordenadora",
        },
        ator=ator(usuarios["bruno"]),
    )
    usuarios["eduardo"] = academic.criar_usuario(
        {
            "nome": "Eduardo Lima",
            "email": "professor.inativo@sigma.edu",
            "senha": "professor123",
            "perfil": "professor",
            "especializacao": "Letras",
        },
        ator=ator(usuarios["bruno"]),
    )
    return usuarios


def criar_materias(academic: AcademicService, usuarios: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bruno = ator(usuarios["bruno"])
    materias = {}
    materias["calc_ana"] = academic.criar_materia(
        {"nome": "Calculo I", "semestre": "2026.1", "carga_horaria": 80, "professor_id": usuarios["ana"]["id"]},
        ator=bruno,
    )
    materias["calc_camila"] = academic.criar_materia(
        {"nome": "Calculo I", "semestre": "2026.1", "carga_horaria": 80, "professor_id": usuarios["camila"]["id"]},
        ator=bruno,
    )
    materias["prog"] = academic.criar_materia(
        {"nome": "Programacao", "semestre": "2026.1", "carga_horaria": 80, "professor_id": usuarios["ana"]["id"]},
        ator=bruno,
    )
    materias["logica"] = academic.criar_materia(
        {"nome": "Logica", "semestre": "2026.1", "carga_horaria": 60, "professor_id": usuarios["ana"]["id"]},
        ator=bruno,
    )
    materias["bd"] = academic.criar_materia(
        {"nome": "Banco de Dados", "semestre": "2026.1", "carga_horaria": 60, "professor_id": usuarios["camila"]["id"]},
        ator=bruno,
    )
    materias["fisica"] = academic.criar_materia(
        {"nome": "Fisica I", "semestre": "2026.1", "carga_horaria": 40, "professor_id": usuarios["camila"]["id"]},
        ator=bruno,
    )
    return materias


# Cada item: (chave, nome, matricula, email, [(chave_materia, ...)], [(chave_materia, notas, frequencia, data)])
ALUNOS_PLANO: list[dict[str, Any]] = [
    {
        "chave": "carla",
        "nome": "Carla Lima",
        "matricula": "2026001",
        "email": "carla.lima@sigma.edu",
        "materias": ["calc_ana", "prog"],
        "desempenhos": [
            ("calc_ana", [7.0, 7.5, 7.0], 88, "2026-05-04"),
            ("calc_ana", [8.0, 8.5, 8.0], 93, "2026-05-25"),
            ("prog", [8.5, 9.0, 9.0], 96, "2026-06-15"),
        ],
    },
    {
        "chave": "diego",
        "nome": "Diego Souza",
        "matricula": "2026002",
        "email": "diego.souza@sigma.edu",
        "materias": ["calc_ana", "logica"],
        "desempenhos": [
            ("calc_ana", [6.0, 6.5, 6.0], 78, "2026-05-10"),
            ("logica", [6.5, 6.0, 6.5], 76, "2026-06-10"),
        ],
    },
    {
        "chave": "elisa",
        "nome": "Elisa Rocha",
        "matricula": "2026003",
        "email": "elisa.rocha@sigma.edu",
        "materias": ["prog", "logica"],
        "desempenhos": [
            ("prog", [3.0, 4.0, 2.5], 58, "2026-06-01"),
        ],
    },
    {
        "chave": "fabio",
        "nome": "Fabio Nogueira",
        "matricula": "2026004",
        "email": "fabio.nogueira@sigma.edu",
        "materias": ["calc_ana"],
        "desempenhos": [
            ("calc_ana", [3.5, 4.0, 4.5], 60, "2026-06-05"),
        ],
    },
    {
        "chave": "giulia",
        "nome": "Giulia Martins",
        "matricula": "2026005",
        "email": "giulia.martins@sigma.edu",
        "materias": ["calc_camila"],
        "desempenhos": [
            ("calc_camila", [7.0, 7.5, 7.0], 85, "2026-06-08"),
        ],
    },
    {
        "chave": "henrique",
        "nome": "Henrique Alves",
        "matricula": "2026006",
        "email": "henrique.alves@sigma.edu",
        "materias": ["calc_camila"],
        "desempenhos": [
            ("calc_camila", [9.0, 9.5, 10.0], 97, "2026-06-08"),
        ],
    },
    {
        "chave": "isabela",
        "nome": "Isabela Castro",
        "matricula": "2026007",
        "email": "isabela.castro@sigma.edu",
        "materias": ["calc_camila", "bd"],
        "desempenhos": [
            ("calc_camila", [8.5, 9.0, 9.0], 93, "2026-06-08"),
            ("bd", [9.0, 8.5, 9.0], 94, "2026-06-12"),
        ],
    },
    {
        "chave": "joao",
        "nome": "Joao Pedro",
        "matricula": "2026008",
        "email": "joao.pedro@sigma.edu",
        "materias": ["logica"],
        "desempenhos": [],
    },
    {
        "chave": "karina",
        "nome": "Karina Souza",
        "matricula": "2026009",
        "email": "karina.souza@sigma.edu",
        "materias": ["prog"],
        "desempenhos": [
            ("prog", [6.0, 6.5, 6.5], 79, "2026-05-20"),
        ],
        "desativar": True,
    },
    {
        "chave": "mariana",
        "nome": "Mariana Costa",
        "matricula": "2026010",
        "email": "mariana.costa@sigma.edu",
        "materias": ["bd"],
        "desempenhos": [
            ("bd", [7.5, 8.0, 7.5], 89, "2026-06-11"),
        ],
    },
    {
        "chave": "nicolas",
        "nome": "Nicolas Ferreira",
        "matricula": "2026011",
        "email": "nicolas.ferreira@sigma.edu",
        "materias": ["logica", "prog"],
        "desempenhos": [
            ("logica", [6.0, 5.5, 6.0], 74, "2026-06-13"),
        ],
    },
    {
        "chave": "olivia",
        "nome": "Olivia Tanaka",
        "matricula": "2026012",
        "email": "olivia.tanaka@sigma.edu",
        "materias": ["calc_ana"],
        "desempenhos": [
            ("calc_ana", [3.0, 3.5, 4.0], 58, "2026-06-09"),
        ],
    },
]

# Professor responsavel por cada materia, para atribuir o ator correto nas
# chamadas de vinculo/desempenho (mais realista na trilha de auditoria).
PROFESSOR_DA_MATERIA = {
    "calc_ana": "ana",
    "calc_camila": "camila",
    "prog": "ana",
    "logica": "ana",
    "bd": "camila",
    "fisica": "camila",
}


def criar_alunos_e_desempenhos(
    academic: AcademicService,
    usuarios: dict[str, dict[str, Any]],
    materias: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    bruno = ator(usuarios["bruno"])
    alunos = {}
    for plano in ALUNOS_PLANO:
        aluno = academic.criar_aluno(
            {"nome": plano["nome"], "matricula": plano["matricula"], "email": plano["email"]},
            ator=bruno,
        )
        alunos[plano["chave"]] = aluno

        for chave_materia in plano["materias"]:
            professor_chave = PROFESSOR_DA_MATERIA[chave_materia]
            academic.vincular_materia(
                aluno["id"], materias[chave_materia]["id"], ator=ator(usuarios[professor_chave])
            )

        for chave_materia, notas, frequencia, data in plano["desempenhos"]:
            professor_chave = PROFESSOR_DA_MATERIA[chave_materia]
            academic.registrar_desempenho(
                aluno["id"],
                {
                    "materia_id": materias[chave_materia]["id"],
                    "notas": notas,
                    "frequencia": frequencia,
                    "data_referencia": data,
                },
                ator=ator(usuarios[professor_chave]),
            )

        if plano.get("desativar"):
            academic.desativar_aluno(aluno["id"], ator=bruno)

    return alunos


def criar_intervencoes(
    academic: AcademicService, usuarios: dict[str, dict[str, Any]], alunos: dict[str, dict[str, Any]]
) -> None:
    ana = ator(usuarios["ana"])
    bruno = ator(usuarios["bruno"])

    academic.registrar_intervencao(
        alunos["elisa"]["id"],
        {"tipo": "Contato", "descricao": "Ligar para o responsavel e agendar conversa sobre frequencia."},
        ator=ana,
    )

    academic.registrar_intervencao(
        alunos["fabio"]["id"],
        {"tipo": "Contato", "descricao": "Enviar e-mail solicitando retorno sobre as ultimas avaliacoes."},
        ator=ana,
    )
    reuniao_fabio = academic.registrar_intervencao(
        alunos["fabio"]["id"],
        {"tipo": "Reuniao", "descricao": "Reuniao com o aluno e a coordenacao para plano de recuperacao."},
        ator=bruno,
    )
    academic.atualizar_intervencao(reuniao_fabio["id"], {"status": "Concluída"}, ator=bruno)

    academic.registrar_intervencao(
        alunos["nicolas"]["id"],
        {"tipo": "Encaminhamento", "descricao": "Encaminhar para apoio pedagogico."},
        ator=ana,
    )

    conversa_olivia = academic.registrar_intervencao(
        alunos["olivia"]["id"],
        {"tipo": "Outro", "descricao": "Conversa informal apos a aula sobre dificuldades no conteudo."},
        ator=ana,
    )
    academic.atualizar_intervencao(conversa_olivia["id"], {"status": "Concluída"}, ator=ana)


def criar_relatorios(academic: AcademicService, usuarios: dict[str, dict[str, Any]]) -> None:
    bruno_id = usuarios["bruno"]["id"]
    academic.criar_relatorio({"tipo": "geral", "titulo": "Relatorio Geral - Demonstracao"}, usuario_id=bruno_id)
    academic.criar_relatorio(
        {"tipo": "risco", "titulo": "Relatorio de Alunos em Risco - Demonstracao"}, usuario_id=bruno_id
    )


def desativar_extras(
    academic: AcademicService, usuarios: dict[str, dict[str, Any]], materias: dict[str, dict[str, Any]]
) -> None:
    bruno = ator(usuarios["bruno"])
    academic.desativar_materia(materias["fisica"]["id"], ator=bruno)
    academic.desativar_usuario(usuarios["eduardo"]["id"], ator=bruno)


def gerar_csv_exemplo(alunos: dict[str, dict[str, Any]]) -> Path:
    matricula_duplicada = alunos["karina"]["matricula"]
    conteudo = (
        "nome,matricula,email\n"
        "Paulo Henrique,2026013,paulo.henrique@sigma.edu\n"
        "Quesia Andrade,2026014,quesia.andrade@sigma.edu\n"
        f"Karina Souza,{matricula_duplicada},duplicada@sigma.edu\n"
        "Rafael Nogueira,,rafael.nogueira@sigma.edu\n"
    )
    destino = DATA_DIR / "exemplo_importacao.csv"
    destino.write_text(conteudo, encoding="utf-8")
    return destino


def popular_demo() -> None:
    conn = connect()
    try:
        init_db(conn)
        academic = AcademicService(conn, MotorIA())

        usuarios = criar_usuarios(academic)
        materias = criar_materias(academic, usuarios)
        alunos = criar_alunos_e_desempenhos(academic, usuarios, materias)
        criar_intervencoes(academic, usuarios, alunos)
        criar_relatorios(academic, usuarios)
        desativar_extras(academic, usuarios, materias)
        academic.recalcular_riscos()
        csv_path = gerar_csv_exemplo(alunos)
    finally:
        conn.close()

    print("Base de demonstracao criada com sucesso em", DB_PATH)
    print()
    print("Credenciais de teste:")
    print("  professor@sigma.edu         / professor123   (Ana, professora - Calculo I, Programacao, Logica)")
    print("  professor2@sigma.edu        / professor123   (Camila, professora - Calculo I, Banco de Dados, Fisica I)")
    print("  gestor@sigma.edu            / gestor123      (Bruno, gestor)")
    print("  gestor2@sigma.edu           / gestor123      (Diana, gestora)")
    print("  professor.inativo@sigma.edu / professor123   (Eduardo - INATIVO, login deve falhar de proposito)")
    print()
    print(f"Arquivo de exemplo para teste de importacao CSV gerado em: {csv_path}")
    print("(linha 1 e 2 validas, linha 3 com matricula duplicada, linha 4 sem matricula)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reseta o banco e popula uma base de demonstracao completa (usuarios, materias, alunos, etc.)."
    )
    parser.add_argument("--sim", action="store_true", help="Nao pede confirmacao interativa.")
    args = parser.parse_args()

    if not args.sim:
        resposta = input(
            f"Isso vai APAGAR e RECRIAR {DB_PATH} com uma base de demonstracao.\n"
            "Todos os dados atuais serao perdidos. Pare o servidor (run.py) antes de continuar.\n"
            "Confirma? [s/N] "
        )
        if resposta.strip().lower() not in ("s", "sim", "y", "yes"):
            print("Operacao cancelada.")
            return

    resetar_banco()
    try:
        popular_demo()
    except AppError as exc:
        raise SystemExit(f"Erro ao popular a base de demonstracao: {exc}")


if __name__ == "__main__":
    main()
