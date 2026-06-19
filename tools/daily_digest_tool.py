from langchain.tools import tool


@tool
def daily_digest(send_telegram: bool = False) -> str:
    """
    Generates the nightly summary of the user's day: today's git commits,
    active reminders and scheduled tasks, notes saved today, Jarvis system
    status and upcoming scheduled steps.
    Use this when the user asks for their daily summary, nightly recap,
    "resumen del día", "resumen nocturno" or "¿cómo ha ido el día?".
    Set send_telegram=True only if the user explicitly asks to send it to their phone.
    """
    from core.daily_digest import generate_daily_digest, send_digest_to_telegram

    digest = generate_daily_digest()
    if send_telegram:
        sent = send_digest_to_telegram(digest)
        suffix = "\n\n(Enviado también a su Telegram, señor.)" if sent else \
                 "\n\n(No se pudo enviar por Telegram; revise la configuración del bot.)"
        return digest + suffix
    return digest
