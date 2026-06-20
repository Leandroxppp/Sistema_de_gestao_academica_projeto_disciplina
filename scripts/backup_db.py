"""Script standalone para copiar o banco de dados imediatamente.

Uso:
    python scripts/backup_db.py

Util para agendar via cron / Tarefas Agendadas do Windows, rodando mesmo
quando o servidor da aplicacao nao estiver em execucao (o backup periodico
embutido em `run.py` so funciona enquanto o processo do servidor existe).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backup import fazer_backup  # noqa: E402


def main() -> None:
    destino = fazer_backup()
    if destino:
        print(f"Backup criado em {destino}")
    else:
        print("Nenhum banco encontrado em data/academico.db -- nada para copiar.")


if __name__ == "__main__":
    main()
