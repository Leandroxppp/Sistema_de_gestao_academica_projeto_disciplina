"""Configuracao de logging estruturado (somente biblioteca padrao).

Cada requisicao HTTP e logada (metodo, caminho, status, duracao) e qualquer
excecao nao tratada e registrada com stack trace -- tudo isso vai para
`logs/app.log` (com rotacao automatica) e tambem para o console.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return  # idempotente: chamar mais de uma vez nao duplica handlers
    _CONFIGURED = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger("sigma")
    root_logger.setLevel(logging.INFO)

    arquivo = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root_logger.addHandler(arquivo)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root_logger.addHandler(console)
