"""Recalculo periodico (noturno) dos indicadores de risco dos alunos.

Mesmo padrao de `app/backup.py`: uma thread daemon que roda a tarefa uma vez
imediatamente ao iniciar o servidor e depois a cada 24h. Como a tarefa escreve
no banco (via `AcademicService.recalcular_riscos`), cada execucao adquire o
mesmo lock usado por `Application.dispatch()` (veja `app/api.py`) para nao
concorrer com requisicoes HTTP que tambem usam a conexao sqlite compartilhada
entre threads.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from threading import RLock

    from .services import AcademicService

logger = logging.getLogger("sigma.scheduler")

INTERVALO_SEGUNDOS = 24 * 60 * 60


def iniciar_recalculo_periodico(academic: "AcademicService", lock: "RLock") -> None:
    """Inicia, em background, o recalculo de risco de todos os alunos a cada
    24h (mais uma execucao imediata ao iniciar o servidor)."""

    def loop() -> None:
        while True:
            try:
                with lock:
                    resultado = academic.recalcular_riscos()
                logger.info("Recalculo automatico de risco concluido: %s alunos.", resultado.get("total"))
            except Exception:
                logger.exception("Falha ao executar recalculo automatico de risco.")
            time.sleep(INTERVALO_SEGUNDOS)

    thread = threading.Thread(target=loop, name="sigma-recalculo", daemon=True)
    thread.start()
