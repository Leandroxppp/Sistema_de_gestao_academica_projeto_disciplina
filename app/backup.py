"""Backup automatico do banco de dados (somente biblioteca padrao).

`iniciar_backup_periodico()` inicia uma thread daemon que copia
`data/academico.db` para `data/backups/` imediatamente e depois a cada 24h,
mantendo apenas as `MAX_BACKUPS` copias mais recentes. Tambem pode ser
disparado manualmente (ou via cron/Tarefas Agendadas) atraves de
`scripts/backup_db.py`, que chama `fazer_backup()` uma unica vez.
"""
from __future__ import annotations

import logging
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from .database import DB_PATH

logger = logging.getLogger("sigma.backup")

BACKUP_DIR = DB_PATH.parent / "backups"
INTERVALO_SEGUNDOS = 24 * 60 * 60
MAX_BACKUPS = 7


def fazer_backup() -> Path | None:
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    destino = BACKUP_DIR / f"academico-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(DB_PATH, destino)
    _limpar_backups_antigos()
    logger.info("Backup do banco criado em %s", destino)
    return destino


def _limpar_backups_antigos() -> None:
    backups = sorted(BACKUP_DIR.glob("academico-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for antigo in backups[MAX_BACKUPS:]:
        antigo.unlink(missing_ok=True)


def iniciar_backup_periodico() -> None:
    """Inicia, em background, o loop de backup a cada 24h (mais um backup imediato)."""

    def loop() -> None:
        while True:
            try:
                fazer_backup()
            except Exception:
                logger.exception("Falha ao executar backup automatico do banco.")
            time.sleep(INTERVALO_SEGUNDOS)

    thread = threading.Thread(target=loop, name="sigma-backup", daemon=True)
    thread.start()
