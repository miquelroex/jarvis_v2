"""
core/autostart.py — Arranque automático con Windows ("Arranque Épico con el PC").

Registra (o quita) el arranque de Jarvis al encender Windows, de forma segura y
reversible: escribe un .bat lanzador (que fija el directorio de trabajo y arranca
Jarvis en modo --awake) y lo apunta en la clave de registro del usuario actual
(HKCU\\...\\Run). No requiere permisos de administrador ni toca nada del sistema.

La construcción del .bat es pura/testeable; el acceso al registro se aísla.
"""
import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "JarvisV2"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
BAT_PATH = PROJECT_ROOT / "logs" / "jarvis_autostart.bat"


def _pythonw() -> str:
    """Ruta a pythonw.exe (sin consola) si existe; si no, el intérprete actual."""
    exe_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(exe_dir, "pythonw.exe")
    return pyw if os.path.exists(pyw) else sys.executable


def build_bat_content(root: str, python_exe: str) -> str:
    """Contenido del .bat lanzador (puro)."""
    main = os.path.join(root, "main.py")
    return (
        "@echo off\r\n"
        f'cd /d "{root}"\r\n'
        f'start "" "{python_exe}" "{main}" --awake\r\n'
    )


# ── Acceso al registro (aislado, mockable) ─────────────────
def _reg_set(name: str, value: str) -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        return True
    except Exception as e:
        logger.warning(f"[Autostart] No se pudo escribir en el registro: {e}")
        return False


def _reg_get(name: str):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(f"[Autostart] No se pudo leer el registro: {e}")
        return None


def _reg_delete(name: str) -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
        return True
    except FileNotFoundError:
        return True  # ya no existe: objetivo cumplido
    except Exception as e:
        logger.warning(f"[Autostart] No se pudo borrar del registro: {e}")
        return False


def is_autostart_enabled() -> bool:
    return _reg_get(APP_NAME) is not None


def enable_autostart() -> bool:
    """Escribe el .bat lanzador y lo registra en el arranque del usuario."""
    try:
        BAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        BAT_PATH.write_text(build_bat_content(str(PROJECT_ROOT), _pythonw()), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Autostart] No se pudo escribir el .bat: {e}")
        return False
    return _reg_set(APP_NAME, f'"{BAT_PATH}"')


def disable_autostart() -> bool:
    """Quita Jarvis del arranque (deja el .bat, inofensivo)."""
    return _reg_delete(APP_NAME)
