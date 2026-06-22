"""
core/proactive_vision.py — JARVIS Proactivo Visual ("Te estoy mirando, señor").

Cada cierto tiempo captura la pantalla, la analiza con Gemini Vision y decide si
merece la pena interrumpir al usuario por voz (un error de código sin resolver,
una notificación importante, señales de estar atascado…).

Privacidad/coste: DESACTIVADO por defecto. Cuando se activa, envía capturas de
pantalla a Google (Gemini). Imports de mss/PIL/genai perezosos para que el
módulo sea ligero y testeable de forma aislada.
"""
import os
import re
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SCREENSHOT_PATH = "logs/proactive_screenshot.png"

_PROMPT = (
    "Eres Jarvis, observando la pantalla del usuario para asistirle de forma "
    "proactiva. Analiza esta captura y decide si AHORA hay algo lo bastante "
    "relevante como para interrumpirle por voz. Sé MUY conservador: interrumpe "
    "SOLO si detectas algo claramente útil, por ejemplo: un error o excepción "
    "visible en código/terminal, una notificación o mensaje importante sin leer, "
    "o señales claras de que lleva mucho tiempo atascado en lo mismo. En la "
    "mayoría de los casos NO se debe interrumpir.\n"
    "Responde ÚNICAMENTE con un JSON válido, sin texto adicional ni markdown:\n"
    '{"interrupt": true|false, "message": "<aviso breve y formal estilo Jarvis, o cadena vacía>"}'
)


def _capture_screen(path: str = SCREENSHOT_PATH) -> bool:
    """Captura el monitor principal a un PNG. True si tuvo éxito."""
    try:
        import mss
        import mss.tools
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=path)
        return True
    except Exception as e:
        logger.warning(f"[ProactiveVision] No se pudo capturar la pantalla: {e}")
        return False


def _parse_decision(text: str) -> dict:
    """Extrae {interrupt, message} del texto de Gemini. Conservador ante fallos."""
    default = {"interrupt": False, "message": ""}
    if not text:
        return default
    s = text.strip()
    # Quitar fences de markdown ```json ... ```
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if not match:
        return default
    try:
        data = json.loads(match.group(0))
        return {
            "interrupt": bool(data.get("interrupt", False)),
            "message": str(data.get("message", "") or "").strip(),
        }
    except Exception:
        return default


def _analyze_screen(image_path: str = SCREENSHOT_PATH) -> dict:
    """Envía la captura a Gemini Vision y devuelve la decisión {interrupt, message}."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.info("[ProactiveVision] Sin GOOGLE_API_KEY; análisis visual desactivado.")
        return {"interrupt": False, "message": ""}
    try:
        from PIL import Image
        from google import genai
        img = Image.open(image_path)
        client = genai.Client(api_key=api_key)
        model = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")
        response = client.models.generate_content(model=model, contents=[img, _PROMPT])
        return _parse_decision(response.text)
    except Exception as e:
        logger.warning(f"[ProactiveVision] Error al analizar la pantalla con Gemini: {e}")
        return {"interrupt": False, "message": ""}


def run_proactive_check() -> dict:
    """Captura la pantalla y la analiza. Devuelve la decisión {interrupt, message}.

    No habla ni emite: solo decide. La entrega la gestiona el daemon (Fase 2).
    """
    if not _capture_screen():
        return {"interrupt": False, "message": ""}
    decision = _analyze_screen()
    decision["timestamp"] = datetime.now(timezone.utc).isoformat()
    return decision