"""Notificacoes por email (somente biblioteca padrao -- `smtplib`).

Desativado por padrao. Para habilitar, defina as variaveis de ambiente:

    SIGMA_SMTP_HOST         servidor SMTP (ex.: smtp.gmail.com)
    SIGMA_SMTP_PORT         porta (opcional, padrao 587)
    SIGMA_SMTP_USER         usuario para autenticacao (opcional)
    SIGMA_SMTP_PASS         senha para autenticacao (opcional)
    SIGMA_SMTP_FROM         remetente (opcional, padrao = SIGMA_SMTP_USER)
    SIGMA_ALERTA_EMAIL_TO   destinatario(s) do alerta, separados por virgula

Se SIGMA_SMTP_HOST ou SIGMA_ALERTA_EMAIL_TO nao estiverem definidos, o envio
e silenciosamente ignorado (apenas logado em nivel DEBUG) -- a funcionalidade
de notificacao nunca deve interromper ou atrasar o fluxo principal da
aplicacao (registro de desempenho, calculo de risco etc.).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("sigma.notifications")


def notificacoes_habilitadas() -> bool:
    return bool(os.environ.get("SIGMA_SMTP_HOST")) and bool(os.environ.get("SIGMA_ALERTA_EMAIL_TO"))


def enviar_alerta_risco(aluno_nome: str, matricula: str, nivel: str, mensagem: str) -> bool:
    """Envia (best-effort) um email avisando que um aluno entrou em risco alto.

    Retorna True se o email foi efetivamente enviado, False se a notificacao
    esta desativada (sem configuracao) ou se o envio falhou. Qualquer
    exception de rede/SMTP e capturada e apenas logada -- nunca propagada.
    """
    if not notificacoes_habilitadas():
        logger.debug("Notificacao por email desativada (configure SIGMA_SMTP_HOST e SIGMA_ALERTA_EMAIL_TO).")
        return False

    host = os.environ["SIGMA_SMTP_HOST"]
    port = int(os.environ.get("SIGMA_SMTP_PORT", "587"))
    usuario = os.environ.get("SIGMA_SMTP_USER")
    senha = os.environ.get("SIGMA_SMTP_PASS")
    remetente = os.environ.get("SIGMA_SMTP_FROM") or usuario or "sigma@localhost"
    destinatarios = [d.strip() for d in os.environ["SIGMA_ALERTA_EMAIL_TO"].split(",") if d.strip()]
    if not destinatarios:
        return False

    msg = EmailMessage()
    msg["Subject"] = f"[Sigma Academico] Aluno em risco {nivel}: {aluno_nome}"
    msg["From"] = remetente
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(
        f"O aluno {aluno_nome} (matricula {matricula}) foi classificado como risco {nivel}.\n\n"
        f"{mensagem}\n\n"
        "Acesse o sistema Sigma Academico para mais detalhes."
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            if usuario and senha:
                smtp.login(usuario, senha)
            smtp.send_message(msg)
        logger.info("Email de alerta enviado para %s (aluno %s).", destinatarios, aluno_nome)
        return True
    except Exception:
        logger.exception("Falha ao enviar email de alerta para o aluno %s.", aluno_nome)
        return False
