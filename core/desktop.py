"""
core/desktop.py — App de Escritorio Nativa (pywebview).

Modo OPCIONAL: en vez de abrir el navegador, Jarvis se muestra en su propia
ventana (WebView2/Chromium en Windows) con el MISMO Flask+SocketIO por debajo.
Ventana propia, sin pestañas, sin caché molesta, icono en bandeja y cierre
limpio (al cerrar la ventana se detiene Jarvis).

pywebview/pystray son dependencias OPCIONALES de importación perezosa: si no
están instaladas, Jarvis cae al modo navegador de siempre (cero riesgo).

Activar:  python main.py --desktop   (o JARVIS_DESKTOP=true)
Instalar: pip install pywebview pystray pillow

La detección de modo y la configuración de ventana son funciones PURAS y
testeables; la ventana, la bandeja y el apagado se aíslan (necesitan GUI real).
"""
import os
import sys
import logging
import threading

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Decisión de modo / configuración (puro)
# ----------------------------------------------------------------------------
def desktop_enabled() -> bool:
    """¿Se ha pedido el modo escritorio? (--desktop o JARVIS_DESKTOP). Puro."""
    return ("--desktop" in sys.argv or
            os.getenv("JARVIS_DESKTOP", "false").lower() in ("true", "1", "yes"))


def window_config() -> dict:
    """Parámetros de la ventana de escritorio desde el entorno (puro)."""
    def _int(name, default):
        try:
            return int(os.getenv(name, default))
        except (TypeError, ValueError):
            return int(default)
    return {
        "title": os.getenv("JARVIS_DESKTOP_TITLE", "J.A.R.V.I.S."),
        "width": _int("JARVIS_DESKTOP_WIDTH", "1280"),
        "height": _int("JARVIS_DESKTOP_HEIGHT", "800"),
        "fullscreen": os.getenv("JARVIS_DESKTOP_FULLSCREEN", "false").lower() in ("true", "1", "yes"),
    }


def is_available() -> bool:
    """¿Está pywebview instalado?"""
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


def use_desktop() -> bool:
    """¿Debe usarse el modo escritorio? (pedido Y disponible). Si se pidió pero no
    está instalado, se cae al navegador."""
    if not desktop_enabled():
        return False
    if not is_available():
        logger.warning("[Desktop] Modo escritorio pedido pero pywebview no está "
                       "instalado. Cayendo al navegador. Instala: pip install pywebview pystray pillow")
        return False
    return True


# ----------------------------------------------------------------------------
# Ventana / bandeja / apagado (aislado, necesita GUI real)
# ----------------------------------------------------------------------------
def _shutdown():
    """Detiene Jarvis limpiamente al cerrar la ventana de escritorio."""
    logger.info("[Desktop] Ventana cerrada; deteniendo Jarvis...")
    try:
        from core.services import stop_all_services
        stop_all_services()
    except Exception as e:
        logger.error(f"[Desktop] Error al detener servicios: {e}")
    try:
        from core.instance_lock import release_instance_lock
        release_instance_lock()
    except Exception:
        pass
    os._exit(0)


def _start_tray():
    """Icono en bandeja con opción de salir (opcional, best-effort)."""
    if os.getenv("JARVIS_DESKTOP_TRAY", "true").lower() not in ("true", "1", "yes"):
        return
    try:
        import pystray
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (64, 64), (5, 8, 13))
        d = ImageDraw.Draw(img)
        d.ellipse((14, 14, 50, 50), outline=(0, 229, 255), width=4)  # aro estilo reactor

        def _on_quit(icon, item):
            try:
                icon.stop()
            except Exception:
                pass
            _shutdown()

        menu = pystray.Menu(pystray.MenuItem("Salir de Jarvis", _on_quit))
        icon = pystray.Icon("jarvis", img, "J.A.R.V.I.S.", menu)
        threading.Thread(target=icon.run, name="JarvisTray", daemon=True).start()
        logger.info("[Desktop] Icono de bandeja activo.")
    except Exception as e:
        logger.debug(f"[Desktop] Bandeja no disponible: {e}")


def run_window_blocking(url: str = "http://localhost:5000"):
    """Crea la ventana de escritorio y BLOQUEA hasta que se cierra.

    DEBE llamarse desde el hilo PRINCIPAL (pywebview lo requiere en Windows).
    Al cerrarse la ventana, apaga Jarvis."""
    try:
        import webview
    except Exception as e:
        logger.error(f"[Desktop] pywebview no disponible: {e}")
        return
    cfg = window_config()
    logger.info(f"[Desktop] Abriendo ventana nativa ({cfg['width']}x{cfg['height']})...")
    webview.create_window(cfg["title"], url, width=cfg["width"], height=cfg["height"],
                          fullscreen=cfg["fullscreen"], background_color="#05080d")
    _start_tray()
    backend = os.getenv("JARVIS_DESKTOP_BACKEND", "").strip()  # p.ej. 'edgechromium'
    try:
        if backend:
            webview.start(gui=backend)
        else:
            webview.start()
    finally:
        _shutdown()
