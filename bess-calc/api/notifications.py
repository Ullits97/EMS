"""Outbound email for new-lead notifications, stdlib smtplib only.

No third-party dependency: SMTP config comes from env vars
(SMTP_HOST/PORT/USER/PASSWORD/FROM). If SMTP_HOST is unset, sending is
skipped (logged) rather than failing the request — keeps local dev/demo
working without a real mail account configured.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from .leads import LeadContact, LeadSummary

logger = logging.getLogger("bess-calc.notifications")


def _format_body(lead_id: int, contact: LeadContact, summary: LeadSummary) -> str:
    pv_line = f"{summary.pv_kwp:.1f} kWp" if summary.pv_kwp else "Ingen solceller"
    payback = (
        f"{summary.payback_years_low}-{summary.payback_years_high} år"
        if summary.payback_years_low is not None
        else "over batteriets levetid"
    )
    return (
        f"Nyt lead fra batteriberegneren (id {lead_id})\n\n"
        f"Navn: {contact.name or '-'}\n"
        f"Telefon: {contact.phone or '-'}\n"
        f"Email: {contact.email or '-'}\n\n"
        f"Forbrug: {summary.annual_kwh:.0f} kWh/år\n"
        f"Solceller: {pv_line}\n"
        f"Batteri: {summary.battery_name}\n"
        f"Besparelse: {summary.annual_savings_dkk_low:.0f}-{summary.annual_savings_dkk_high:.0f} kr./år\n"
        f"Nutidsværdi: {summary.npv_dkk:.0f} kr.\n"
        f"Tilbagebetalingstid: {payback}\n"
    )


def send_lead_notification(
    notify_email: str, lead_id: int, contact: LeadContact, summary: LeadSummary
) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        logger.warning("SMTP ikke konfigureret (SMTP_HOST mangler) — springer email over for lead %s", lead_id)
        return

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM", user or "noreply@bess-calc.local")

    msg = EmailMessage()
    msg["Subject"] = "Nyt lead fra batteriberegneren"
    msg["From"] = sender
    msg["To"] = notify_email
    msg.set_content(_format_body(lead_id, contact, summary))

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except Exception:
        logger.exception("Kunne ikke sende lead-notifikation for lead %s", lead_id)
