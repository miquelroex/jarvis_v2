"""
core/reticle_scan.py — "Escanea esto" (Análisis con Retícula).

Jarvis captura la pantalla, la analiza con visión (Gemini) y dibuja retículas /
cajas de seguimiento estilo HUD de combate de Iron Man SOBRE tu escritorio real
(ventana tkinter transparente a pantalla completa), narrando lo detectado:
"Identificado: traceback de Python. Analizando…".

El parseo de las detecciones del modelo, su conversión a coordenadas de pantalla
y la narración son funciones PURAS y testeables. La captura (mss), la llamada a
visión (genai) y el overlay (tkinter) se aíslan y NUNCA se instancian en CI.
"""
import os
import re
import json
import logging
import threading

logger = logging.getLogger(__name__)

SCREENSHOT_PATH = "logs/latest_screenshot.png"

# Tipos de elemento que el modelo puede etiquetar y su prioridad para narrar.
_KIND_ICON = {"error": "⚠", "text": "≡", "window": "▢", "object": "◎", "code": "</>"}
_PRIORITY = {"error": 0, "code": 1, "window": 2, "text": 3, "object": 4}

_SCAN_PROMPT = (
    "Eres el sistema de análisis visual de Jarvis. Examina esta captura de "
    "pantalla y devuelve las regiones más relevantes (errores/excepciones "
    "visibles, ventanas/apps, bloques de código, textos destacados u objetos). "
    "Responde ÚNICAMENTE con un JSON válido, sin markdown, con esta forma:\n"
    '{"detections": [{"label": "<texto corto>", "kind": "error|code|window|text|object", '
    '"box": [ymin, xmin, ymax, xmax]}]}\n'
    "Las coordenadas de box son enteros 0-1000 normalizados respecto a la imagen. "
    "Devuelve como mucho 8 detecciones, las más relevantes."
)


# ----------------------------------------------------------------------------
# Parseo y geometría (puro)
# ----------------------------------------------------------------------------
def parse_detections(raw_text: str):
    """Extrae la lista de detecciones del JSON del modelo (tolerante). Puro.

    Acepta JSON con o sin vallas markdown, como objeto {"detections": [...]} o
    como lista directa. Descarta entradas mal formadas o con box inválida."""
    if not raw_text or not raw_text.strip():
        return []
    text = raw_text.strip()
    # Quita vallas ```json ... ```
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text.strip()).strip()
    try:
        data = json.loads(text)
    except Exception:
        # Último recurso: localizar el primer bloque {...} o [...].
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except Exception:
            return []
    items = data.get("detections", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        box = it.get("box")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            ymin, xmin, ymax, xmax = (int(v) for v in box)
        except (TypeError, ValueError):
            continue
        if ymax <= ymin or xmax <= xmin:
            continue
        kind = str(it.get("kind", "object")).lower()
        if kind not in _KIND_ICON:
            kind = "object"
        label = str(it.get("label", "")).strip()[:60] or "elemento"
        out.append({"label": label, "kind": kind,
                    "box": [_clamp(ymin), _clamp(xmin), _clamp(ymax), _clamp(xmax)]})
    return out


def _clamp(v, lo=0, hi=1000):
    return max(lo, min(hi, v))


def to_reticles(detections, width: int, height: int, max_n: int = 8):
    """Convierte detecciones (box 0-1000) a retículas en píxeles de pantalla. Puro.

    Devuelve [{label, kind, x, y, w, h}] ordenadas por prioridad (errores primero)."""
    if width <= 0 or height <= 0:
        return []
    ordered = sorted(detections or [], key=lambda d: _PRIORITY.get(d.get("kind"), 9))
    reticles = []
    for d in ordered[:max_n]:
        ymin, xmin, ymax, xmax = d["box"]
        x = int(xmin / 1000 * width)
        y = int(ymin / 1000 * height)
        w = int((xmax - xmin) / 1000 * width)
        h = int((ymax - ymin) / 1000 * height)
        if w <= 0 or h <= 0:
            continue
        reticles.append({"label": d["label"], "kind": d["kind"], "x": x, "y": y, "w": w, "h": h})
    return reticles


def build_narration(detections) -> str:
    """Narración estilo HUD de combate de lo detectado (puro)."""
    if not detections:
        return "Escaneo completado, señor. No he detectado nada reseñable en pantalla."
    ordered = sorted(detections, key=lambda d: _PRIORITY.get(d.get("kind"), 9))
    n = len(detections)
    prefix = ""
    top = ordered[0]
    if top["kind"] in ("error", "code"):
        prefix = f"Identificado: {top['label']}. Analizando… "
    etiquetas = ", ".join(d["label"] for d in ordered[:4])
    cuerpo = (f"Escaneo completado, señor. He marcado {n} "
              f"{'elemento' if n == 1 else 'elementos'}: {etiquetas}.")
    return prefix + cuerpo


# ----------------------------------------------------------------------------
# Captura / visión / overlay (aislado, nunca en CI)
# ----------------------------------------------------------------------------
def _capture_screen(path: str = SCREENSHOT_PATH):
    """Captura el monitor principal a PNG. Devuelve (ok, width, height)."""
    try:
        import mss
        import mss.tools
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=path)
            return True, shot.size[0], shot.size[1]
    except Exception as e:
        logger.warning(f"[Reticle] No se pudo capturar la pantalla: {e}")
        return False, 0, 0


def _detect(path: str) -> str:
    """Llama a Gemini Vision y devuelve el texto crudo de la respuesta ("" si falla)."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return ""
    try:
        from PIL import Image
        from google import genai
        img = Image.open(path)
        client = genai.Client(api_key=api_key)
        model = os.getenv("JARVIS_MODEL_GEMINI", "gemini-3.5-flash")
        response = client.models.generate_content(model=model, contents=[img, _SCAN_PROMPT])
        return response.text or ""
    except Exception as e:
        logger.warning(f"[Reticle] Falló el análisis de visión: {e}")
        return ""


def _draw_reticle(canvas, x, y, w, h, label, color, accent):
    """Dibuja una caja de seguimiento con esquinas en L y etiqueta (tkinter)."""
    seg = max(8, min(w, h) // 5)
    pts = [
        (x, y, x + seg, y), (x, y, x, y + seg),                       # sup-izq
        (x + w, y, x + w - seg, y), (x + w, y, x + w, y + seg),       # sup-der
        (x, y + h, x + seg, y + h), (x, y + h, x, y + h - seg),       # inf-izq
        (x + w, y + h, x + w - seg, y + h), (x + w, y + h, x + w, y + h - seg),  # inf-der
    ]
    for x1, y1, x2, y2 in pts:
        canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
    canvas.create_rectangle(x, y, x + w, y + h, outline=accent, width=1)
    canvas.create_text(x + 4, max(0, y - 10), text=label, anchor="w",
                       fill=color, font=("Consolas", 9, "bold"))


def _show_overlay(reticles, duration: float):
    """Overlay tkinter transparente a pantalla completa con las retículas."""
    try:
        import tkinter as tk
    except Exception:
        return
    trans = "#010203"
    accent = "#00e5ff"
    err = "#ff3b30"
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        pass
    root.configure(bg=trans)
    try:
        root.attributes("-transparentcolor", trans)  # sólo se ven las retículas
    except Exception:
        root.attributes("-alpha", 0.4)
    canvas = tk.Canvas(root, bg=trans, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    for r in reticles:
        color = err if r["kind"] == "error" else accent
        tag = f"{_KIND_ICON.get(r['kind'], '◎')} {r['label']}"
        _draw_reticle(canvas, r["x"], r["y"], r["w"], r["h"], tag, color, accent)
    root.bind("<Escape>", lambda e: root.destroy())
    root.after(int(max(1.0, duration) * 1000), root.destroy)
    root.mainloop()


def _launch_overlay(reticles):
    if os.getenv("JARVIS_RETICLE_OVERLAY", "true").lower() not in ("true", "1", "yes"):
        return
    if not reticles:
        return
    duration = float(os.getenv("JARVIS_RETICLE_DURATION", "5"))
    threading.Thread(target=_show_overlay, args=(reticles, duration),
                     name="ReticleOverlay", daemon=True).start()


def scan_screen() -> str:
    """Captura, analiza y dibuja retículas sobre la pantalla. Devuelve la narración."""
    ok, width, height = _capture_screen()
    if not ok:
        return "No he podido capturar la pantalla, señor."
    if not os.getenv("GOOGLE_API_KEY"):
        return ("No tengo configurada la visión, señor. Defina GOOGLE_API_KEY "
                "para el análisis con retícula.")
    raw = _detect(SCREENSHOT_PATH)
    detections = parse_detections(raw)
    reticles = to_reticles(detections, width, height)
    _launch_overlay(reticles)
    narration = build_narration(detections)
    # Refleja la narración también en el HUD web (reusa el Stream de Pensamiento).
    try:
        from core.narration import narrate
        narrate(narration, speak=False, tone="alert" if any(
            d["kind"] == "error" for d in detections) else "neutral")
    except Exception:
        pass
    return narration
