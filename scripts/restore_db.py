"""Script standalone para restaurar o banco de dados a partir de um backup.

Contraparte de scripts/backup_db.py. Copia um arquivo de data/backups/ de
volta para data/academico.db, fazendo antes uma copia de seguranca do banco
atual (assim, se a restauracao for um erro, nada se perde).

Uso:
    python scripts/restore_db.py --listar
        Lista os backups disponiveis em data/backups/, do mais recente ao mais antigo.

    python scripts/restore_db.py --mais-recente
        Restaura o backup mais recente (pede confirmacao antes de sobrescrever).

    python scripts/restore_db.py academico-20260619-030000.db
        Restaura um backup especifico pelo nome (dentro de data/backups/) ou
        por caminho completo.

    Acrescente --sim a qualquer um dos comandos acima para pular a confirmacao
    interativa (util em scripts nao interativos).

IMPORTANTE: pare o servidor (run.py) antes de restaurar -- caso contrario o
processo em execucao pode sobrescrever o arquivo restaurado.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backup import BACKUP_DIR  # noqa: E402
from app.database import DB_PATH  # noqa: E402


def listar_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("academico-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def resolver_backup(identificador: str) -> Path:
    candidato = Path(identificador)
    if not candidato.is_absolute():
        direto = BACKUP_DIR / identificador
        if direto.exists():
            return direto
    if candidato.exists():
        return candidato
    raise SystemExit(f"Backup nao encontrado: {identificador}")


def restaurar(origem: Path, confirmar: bool) -> None:
    if not origem.exists():
        raise SystemExit(f"Arquivo de backup nao encontrado: {origem}")
    if confirmar:
        resposta = input(
            f"Isso vai SOBRESCREVER {DB_PATH} com o conteudo de {origem.name}.\n"
            "Pare o servidor (run.py) antes de continuar. Confirma? [s/N] "
        )
        if resposta.strip().lower() not in ("s", "sim", "y", "yes"):
            print("Restauracao cancelada.")
            return
    if DB_PATH.exists():
        seguranca = DB_PATH.parent / f"pre-restore-{datetime.now():%Y%m%d-%H%M%S}.db"
        shutil.copy2(DB_PATH, seguranca)
        print(f"Copia de seguranca do banco atual criada em {seguranca}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, DB_PATH)
    print(f"Banco restaurado a partir de {origem}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura o banco a partir de um backup em data/backups/.")
    parser.add_argument("arquivo", nargs="?", help="Nome ou caminho do arquivo de backup a restaurar.")
    parser.add_argument("--listar", action="store_true", help="Lista os backups disponiveis e sai.")
    parser.add_argument("--mais-recente", action="store_true", help="Restaura o backup mais recente.")
    parser.add_argument("--sim", action="store_true", help="Nao pede confirmacao interativa.")
    args = parser.parse_args()

    if args.listar:
        backups = listar_backups()
        if not backups:
            print("Nenhum backup encontrado em data/backups/.")
            return
        for backup in backups:
            tamanho_kb = backup.stat().st_size / 1024
            print(f"{backup.name}  ({tamanho_kb:.1f} KB)")
        return

    if args.mais_recente:
        backups = listar_backups()
        if not backups:
            raise SystemExit("Nenhum backup encontrado em data/backups/.")
        origem = backups[0]
    elif args.arquivo:
        origem = resolver_backup(args.arquivo)
    else:
        parser.print_help()
        raise SystemExit("\nInforme um arquivo, use --mais-recente ou --listar.")

    restaurar(origem, confirmar=not args.sim)


if __name__ == "__main__":
    main()
