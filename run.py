from __future__ import annotations

import argparse

from app.api import create_server
from app.backup import iniciar_backup_periodico


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend academico da Equipe Sigma")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument(
        "--sem-backup", action="store_true", help="Desativa o backup automatico periodico do banco."
    )
    parser.add_argument(
        "--sem-recalculo",
        action="store_true",
        help="Desativa o recalculo automatico (noturno) dos indicadores de risco.",
    )
    args = parser.parse_args()

    server = create_server(args.host, args.port, recalculo_automatico=not args.sem_recalculo)
    if not args.sem_backup:
        iniciar_backup_periodico()
    print(f"Servidor iniciado em http://{args.host}:{args.port}")
    print("Usuarios de demonstracao:")
    print("  professor@sigma.edu / professor123")
    print("  gestor@sigma.edu / gestor123")
    server.serve_forever()


if __name__ == "__main__":
    main()
