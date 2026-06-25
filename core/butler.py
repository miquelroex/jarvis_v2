"""
core/butler.py — Protocolo "Mayordomo" ("Buenos días, señor").

Con un comando matutino, Jarvis prepara tu estación de trabajo (abre las apps y
URLs que configures) y te da el parte del día reutilizando el briefing matutino
(saludo, fecha, clima, estado del repositorio y recordatorios).

La preparación del entorno y el briefing se aíslan; el parseo de objetivos y el
montaje del informe son puros y testeables.
"""
import os
import re
import logging

logger = logging.getLogger(__name__)


def _parse_targets(spec: str) -> list:
    """Parsea una lista separada por comas/; en objetivos limpios (puro)."""
    if not spec:
        return []
    return [p.strip() for p in re.split(r"[;,]", spec) if p.strip()]


def build_butler_report(briefing: str, launched: list) -> str:
    """Combina el briefing con la línea de 'estación preparada' (puro)."""
    lines = [briefing] if briefing else []
    if launched:
        lines.append("He preparado su estación de trabajo: " + ", ".join(launched) + ".")
    return "\n".join(lines)


def _launch_environment() -> list:
    """Abre las apps (JARVIS_BUTLER_APPS) y URLs (JARVIS_BUTLER_URLS). Best-effort.
    Devuelve la lista de objetivos abiertos con éxito."""
    launched = []
    for app in _parse_targets(os.getenv("JARVIS_BUTLER_APPS", "")):
        try:
            from tools.launcher import open_windows_app
            open_windows_app.invoke({"app_executable": app})
            launched.append(app)
        except Exception as e:
            logger.warning(f"[Butler] No se pudo abrir la app '{app}': {e}")
    for url in _parse_targets(os.getenv("JARVIS_BUTLER_URLS", "")):
        try:
            from tools.browser import open_website
            open_website.invoke({"url": url})
            launched.append(url)
        except Exception as e:
            logger.warning(f"[Butler] No se pudo abrir la URL '{url}': {e}")
    return launched


def _get_briefing() -> str:
    try:
        from core.morning_briefing import generate_morning_briefing
        return generate_morning_briefing()
    except Exception as e:
        logger.warning(f"[Butler] No se pudo generar el briefing: {e}")
        try:
            from core.startup import _get_greeting_by_time
            return f"{_get_greeting_by_time()}, señor."
        except Exception:
            return "Buenos días, señor."


def run_butler(launch: bool = True, announce: bool = True) -> str:
    """Ejecuta el Protocolo Mayordomo: prepara el entorno y entrega el parte.
    Devuelve el texto del informe."""
    launched = _launch_environment() if launch else []
    report = build_butler_report(_get_briefing(), launched)
    if announce:
        try:
            from tools.voice import speak
            speak(report, disable_vad=True)
        except Exception as e:
            logger.warning(f"[Butler] No se pudo entregar el parte por voz: {e}")
    return report
