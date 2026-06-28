"""
core/access_control.py — Control de Acceso por rostro ("Identidad confirmada").

Convierte el reconocimiento facial (core/face_id) en un CANDADO: ante una acción
sensible (borrar, desactivar servicios, protocolos destructivos…), Jarvis
verifica con la cámara que quien la pide es alguien autorizado antes de
ejecutarla. *"Identidad confirmada, señor. Acceso concedido."* /
*"Acceso denegado: no le reconozco."*

La clasificación de comandos sensibles y la POLÍTICA de acceso son funciones
PURAS y testeables; la verificación facial (face_id) se aísla. Off por defecto
(gatea comandos). Por seguridad de uso, si el reconocimiento facial no está
disponible (OpenCV sin instalar) la política es configurable: por defecto
"fail-open" (deja pasar avisando) para no bloquear el sistema por accidente.
"""
import os
import logging
import unicodedata

logger = logging.getLogger(__name__)

# Acciones consideradas sensibles (subcadenas normalizadas, sin acentos).
DEFAULT_SENSITIVE = [
    "borra", "elimina", "formatea", "desactiva", "apaga el equipo", "apaga el sistema",
    "reinicia el sistema", "protocolo de limpieza", "clean slate", "borron y cuenta nueva",
    "protocolo mark", "mark dos", "wipe", "purga", "resetea", "destruye",
]


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ----------------------------------------------------------------------------
# Núcleo puro
# ----------------------------------------------------------------------------
def is_sensitive(command: str, keywords=None) -> bool:
    """¿El comando solicita una acción sensible que requiere autenticación? Puro."""
    text = _normalize(command)
    for kw in (keywords if keywords is not None else DEFAULT_SENSITIVE):
        if kw in text:
            return True
    return False


def decide_access(identity: str, available: bool, authorized, fail_open: bool = True):
    """Decide el acceso a partir de la identidad reconocida. Puro.

    Devuelve ('allow'|'deny', motivo). Si el reconocimiento no está disponible,
    `fail_open` decide si se permite (avisando) o se bloquea."""
    if not available:
        return ("allow", "sin verificación facial") if fail_open else ("deny", "sin verificación facial")
    auth = {_normalize(a) for a in (authorized or [])}
    if identity and identity != "desconocido" and _normalize(identity) in auth:
        return ("allow", identity)
    return ("deny", identity or "desconocido")


def access_phrase(decision: str, identity: str) -> str:
    """Frase de Jarvis según la decisión de acceso (puro)."""
    if decision == "allow":
        if identity and identity not in ("desconocido", "sin verificación facial"):
            return f"Identidad confirmada, {identity}. Acceso concedido."
        return "Acceso concedido, señor."
    return "Acceso denegado, señor. No autorizo esta acción a quien no reconozco."


def authorized_names() -> list:
    """Lista de identidades autorizadas (de JARVIS_ACCESS_AUTHORIZED, o 'señor')."""
    raw = os.getenv("JARVIS_ACCESS_AUTHORIZED", "señor")
    return [n.strip() for n in raw.split(",") if n.strip()]


def _enabled() -> bool:
    return os.getenv("JARVIS_ACCESS_CONTROL_ENABLED", "false").lower() in ("true", "1", "yes")


def _fail_open() -> bool:
    return os.getenv("JARVIS_ACCESS_FAIL_OPEN", "true").lower() in ("true", "1", "yes")


# ----------------------------------------------------------------------------
# Verificación (aislada) + guardia
# ----------------------------------------------------------------------------
def _verify_identity():
    """(identidad, disponible) usando el reconocimiento facial local."""
    try:
        from core.face_id import identify, is_available, MODEL_PATH
        available = is_available() and MODEL_PATH.exists()
        if not available:
            return "desconocido", False
        return identify(), True
    except Exception as e:
        logger.debug(f"[Access] No se pudo verificar identidad: {e}")
        return "desconocido", False


def maybe_block(command: str):
    """Devuelve una frase de denegación si el comando sensible no se autoriza, o None.

    None significa "deja pasar" (no sensible, control desactivado, o acceso
    concedido). Sólo bloquea cuando está activado, el comando es sensible y la
    política deniega."""
    if not _enabled() or not is_sensitive(command):
        return None
    identity, available = _verify_identity()
    decision, _reason = decide_access(identity, available, authorized_names(), _fail_open())
    if decision == "allow":
        return None
    return access_phrase("deny", identity)
