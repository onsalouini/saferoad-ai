# api/services/mailer.py
"""
Envoi d'e-mails (SMTP). Sans SMTP_HOST, les e-mails sont affichés dans la console
du serveur : pratique en développement (lien de réinitialisation, alertes).
"""
from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "SafeRoad AI <no-reply@saferoad.local>")
SMTP_SSL = os.getenv("SMTP_SSL", "false").lower() == "true"


def configured() -> bool:
    return bool(SMTP_HOST)


def _send(to: str, subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_FROM, to, subject
    msg.set_content(text)
    smtp_cls = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
    with smtp_cls(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        if not SMTP_SSL:
            s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASSWORD or "")
        s.send_message(msg)


async def send(to: str, subject: str, text: str) -> bool:
    """True si l'e-mail est parti (ou affiché en mode console)."""
    if not configured():
        print(f"\n--- E-mail (SMTP non configuré) ---\nÀ : {to}\nObjet : {subject}\n\n{text}\n-----------------------------------\n")
        return True
    try:
        await asyncio.to_thread(_send, to, subject, text)
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"Échec d'envoi de l'e-mail à {to} : {e}")
        return False
