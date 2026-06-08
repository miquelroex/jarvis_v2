import os
import re
import json
import logging
import hashlib
import threading
import time
import fnmatch
from pathlib import Path
from core.api_sentinel import is_internet_available
from tools.voice import speak

# Configuración y Rutas
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
FINDINGS_FILE = LOGS_DIR / "privacy_findings.json"
IGNORED_FILE = LOGS_DIR / "ignored_secrets.json"

# Patrones Regex para búsqueda de Secretos
SECRET_PATTERNS = {
    "OpenRouter API Key": r"sk-or-v1-[a-zA-Z0-9]{64}",
    "OpenAI API Key": r"sk-(proj-)?[a-zA-Z0-9]{48}",
    "Google API Key": r"AIzaSy[a-zA-Z0-9\-_]{33}",
    "Tavily API Key": r"tvly-[a-zA-Z0-9\-]{32,64}",
    "Telegram Bot Token": r"[0-9]{8,10}:[a-zA-Z0-9\-_]{35}",
    "ElevenLabs API Key": r"sk_[a-zA-Z0-9]{48}",
    "SSH / Private PEM Key": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
    "Hardcoded Password / Secret": r"\b(password|client_secret|client_private_key|db_password|database_url)\s*=\s*['\"]([a-zA-Z0-9\-_!@#$%^&*()]{8,})['\"]"
}

# Hilos globales
MONITOR_THREAD = None
MONITOR_RUNNING = False
LATEST_FINDINGS = []

def load_ignored_hashes() -> set:
    """Carga los hashes de secretos que el usuario decidió ignorar."""
    if not IGNORED_FILE.exists():
        return set()
    try:
        data = json.loads(IGNORED_FILE.read_text(encoding="utf-8"))
        return set(data)
    except Exception:
        return set()

def save_ignored_hash(secret_hash: str) -> None:
    """Guarda un hash en la lista de ignorados."""
    hashes = load_ignored_hashes()
    hashes.add(secret_hash)
    LOGS_DIR.mkdir(exist_ok=True)
    try:
        IGNORED_FILE.write_text(json.dumps(list(hashes), indent=2), encoding="utf-8")
    except Exception as e:
        logging.error(f"[Privacy Guard] Error saving ignored hash: {e}")

def load_gitignore_patterns() -> list:
    """Carga los patrones del archivo .gitignore del proyecto."""
    patterns = []
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if gitignore_path.exists():
        try:
            content = gitignore_path.read_text(encoding="utf-8")
            patterns = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        except Exception:
            pass
    return patterns

def is_path_ignored(path_str: str, gitignore_patterns: list) -> bool:
    """Verifica si una ruta está ignorada por gitignore o carpetas del sistema."""
    normalized = path_str.replace("\\", "/").lower()
    
    # Exclusiones absolutas para optimizar escaneo y seguridad
    default_ignores = [
        "/.git/", "/.venv/", "/node_modules/", "/__pycache__/", "/logs/", 
        "/.tempmediastorage/", "/known_devices.json", "/ignored_secrets.json",
        "/privacy_findings.json", "/model_usage.log", ".png", ".jpg", ".webp",
        ".zip", ".tar.gz", ".pdf", ".mp4", ".mp3", ".wav", ".ico"
    ]
    
    for dig in default_ignores:
        if dig in normalized or normalized.endswith(dig):
            return True
            
    # Ignorar .env por defecto (es local y está excluido de git por diseño)
    if normalized.endswith("/.env") or normalized == ".env":
        return True
        
    for pattern in gitignore_patterns:
        pattern = pattern.strip().replace("\\", "/").lower()
        if not pattern or pattern.startswith("#"):
            continue
            
        clean_pat = pattern.lstrip("/")
        
        # Omitir barra al final si es directorio
        if clean_pat.endswith("/"):
            dir_pat = clean_pat
            if dir_pat in normalized or f"/{dir_pat}" in normalized:
                return True
        else:
            if "*" in clean_pat:
                if fnmatch.fnmatch(normalized, f"*{clean_pat}*"):
                    return True
            else:
                if clean_pat in normalized or normalized.endswith(clean_pat):
                    return True
                    
    return False

def is_false_positive(key_type: str, value: str) -> bool:
    """Descarta placeholders conocidos y asignaciones vacías/genéricas."""
    val_lower = value.lower()
    placeholders = [
        "your_", "placeholder", "mi_contraseña", "my_password", "db_pass",
        "xxxx", "123456", "password", "secret", "token", "default", "config",
        "llave", "llave_secreta", "ai_studio_key", "tavily_key", "contraseña",
        "google_key", "openai_key", "bot_token", "user_id"
    ]
    for pl in placeholders:
        if pl in val_lower:
            return True
            
    if key_type == "Hardcoded Password / Secret":
        if len(value) < 8:
            return True
        if "${" in value or "{{" in value or "%" in value:
            return True
            
    return False

def censor_secret(secret: str) -> str:
    """Censura la mayor parte del secreto para no exponerlo en logs ni UI."""
    if len(secret) <= 10:
        return "***"
    return f"{secret[:6]}...{secret[-4:]}"

def scan_workspace_privacy() -> list:
    """
    Escanea recursivamente el workspace buscando API Keys y secretos.
    Filtra por .gitignore y la lista blanca de ignorados.
    """
    findings = []
    ignored_hashes = load_ignored_hashes()
    gitignore_patterns = load_gitignore_patterns()
    
    if not PROJECT_ROOT.exists():
        return findings

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Modificar dirs in-place para que os.walk no entre en carpetas ignoradas
        dirs[:] = [d for d in dirs if not is_path_ignored(os.path.join(root, d), gitignore_patterns)]
        
        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(PROJECT_ROOT).as_posix()
            
            if is_path_ignored(rel_path, gitignore_patterns):
                continue
                
            try:
                # Leer con errors="ignore" para evitar fallos de decodificación binaria
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        for label, regex in SECRET_PATTERNS.items():
                            matches = re.finditer(regex, line)
                            for match in matches:
                                # Si es password hardcodeada, extraer el grupo capturado
                                if label == "Hardcoded Password / Secret":
                                    secret_val = match.group(2)
                                else:
                                    secret_val = match.group(0)
                                    
                                if is_false_positive(label, secret_val):
                                    continue
                                    
                                secret_hash = hashlib.sha256(secret_val.encode("utf-8")).hexdigest()
                                if secret_hash in ignored_hashes:
                                    continue
                                    
                                findings.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "type": label,
                                    "snippet": censor_secret(secret_val),
                                    "hash": secret_hash
                                })
            except Exception as e:
                # Fallback silencioso para archivos no legibles
                pass
                
    return findings

def get_privacy_status() -> dict:
    """Devuelve el estado de privacidad actual."""
    global LATEST_FINDINGS
    return {
        "status": "vulnerable" if LATEST_FINDINGS else "protected",
        "findings": LATEST_FINDINGS
    }

def start_privacy_monitor() -> None:
    """Arranca el hilo de monitoreo periódico de privacidad."""
    global MONITOR_THREAD, MONITOR_RUNNING, LATEST_FINDINGS
    
    if MONITOR_RUNNING:
        return
        
    MONITOR_RUNNING = True
    
    # Cargar hallazgos iniciales
    try:
        LATEST_FINDINGS = scan_workspace_privacy()
    except Exception as e:
        logging.error(f"[Privacy Guard] Error on initial scan: {e}")
        
    MONITOR_THREAD = threading.Thread(target=_monitor_loop, name="PrivacyMonitorThread", daemon=True)
    MONITOR_THREAD.start()
    logging.info("[Privacy Guard] Monitor thread started.")

def _monitor_loop() -> None:
    global LATEST_FINDINGS, MONITOR_RUNNING
    
    while MONITOR_RUNNING:
        try:
            interval = int(os.getenv("JARVIS_PRIVACY_SCAN_INTERVAL", "900"))
        except Exception:
            interval = 900
            
        time.sleep(interval)
        if not MONITOR_RUNNING:
            break
            
        try:
            current_findings = scan_workspace_privacy()
            
            # Identificar nuevos secretos que no estaban en la lista anterior
            old_hashes = {f["hash"] for f in LATEST_FINDINGS}
            new_leaks = [f for f in current_findings if f["hash"] not in old_hashes]
            
            LATEST_FINDINGS = current_findings
            
            # Propagar actualización a la GUI si hay Socket.IO activo
            try:
                from gui.app import socketio
                socketio.emit('privacy_update', get_privacy_status())
            except Exception:
                pass
                
            # Alertas proactivas para nuevos leaks
            if new_leaks:
                msg = f"Señor, he detectado una posible clave expuesta en el archivo {new_leaks[0]['file']}. Por favor, revise el panel de privacidad."
                speak(msg, disable_vad=True)
                
                # Alerta por Telegram
                try:
                    from core.telegram_bot import bot
                    telegram_user_id = os.getenv("TELEGRAM_USER_ID")
                    if bot and telegram_user_id:
                        import html
                        tel_msg = (
                            "⚠️ <b>[PRIVACY GUARD] Alerta de Privacidad</b>\n"
                            "Se ha detectado un secreto expuesto en el repositorio:\n"
                            f"• <b>Archivo:</b> <code>{html.escape(new_leaks[0]['file'])}</code>\n"
                            f"• <b>Línea:</b> {new_leaks[0]['line']}\n"
                            f"• <b>Tipo:</b> {html.escape(new_leaks[0]['type'])}\n"
                            f"• <b>Censurado:</b> <code>{html.escape(new_leaks[0]['snippet'])}</code>"
                        )
                        bot.send_message(telegram_user_id, tel_msg, parse_mode="HTML")
                except Exception as tg_err:
                    logging.error(f"[Privacy Guard] Error alertando vía Telegram: {tg_err}")
                    
        except Exception as e:
            logging.error(f"[Privacy Guard] Error in monitor loop check: {e}")

def stop_privacy_monitor() -> None:
    global MONITOR_RUNNING
    MONITOR_RUNNING = False
