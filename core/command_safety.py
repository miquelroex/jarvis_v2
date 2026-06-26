"""
core/command_safety.py — "¿Esto es seguro?" (análisis previo de comandos).

Antes de ejecutar un comando o script, Jarvis lo analiza y clasifica su riesgo
(seguro / precaución / peligro), explicando POR QUÉ: borrados masivos, formateo
de discos, descargar-y-ejecutar (curl|bash), desactivar antivirus/firewall,
operaciones git destructivas, elevación de privilegios, etc.

Análisis por reglas, puro y muy testeable.
"""
import re

SAFE = "safe"
CAUTION = "caution"
DANGER = "danger"
_ORDER = {SAFE: 0, CAUTION: 1, DANGER: 2}

# (patrón regex, nivel, motivo). Se evalúan todos; gana el nivel más alto.
_RULES = [
    # ── PELIGRO ─────────────────────────────────────────────
    (r"rm\s+-[a-z]*r[a-z]*f|rm\s+-[a-z]*f[a-z]*r", DANGER, "borrado recursivo y forzado de ficheros (rm -rf)"),
    (r"remove-item\b.*(-recurse|-force).*(-force|-recurse)", DANGER, "borrado recursivo y forzado (Remove-Item -Recurse -Force)"),
    (r"\bdel\s+/[a-z\s/]*[sf]\b|rmdir\s+/s|\brd\s+/s", DANGER, "borrado masivo de directorios"),
    (r"rm\s+-rf\s+(/|~|\*|\$home|/\*)", DANGER, "intento de borrar el sistema o el home completo"),
    (r"\bformat\b\s+[a-z]:|mkfs|diskpart|cipher\s+/w", DANGER, "formateo o borrado seguro de disco"),
    (r"dd\s+if=.*of=/dev/|>\s*/dev/sd", DANGER, "escritura directa a un dispositivo de disco"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", DANGER, "fork bomb (agota el sistema)"),
    (r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh", DANGER, "descargar y ejecutar un script remoto (curl|bash)"),
    (r"(iwr|invoke-webrequest|curl)\b[^|]*\|\s*(iex|invoke-expression)", DANGER, "descargar y ejecutar código remoto (IWR|IEX)"),
    (r"\b(iex|invoke-expression)\b|powershell\s+.*-e(nc|ncodedcommand)?\s+[a-z0-9+/=]{16,}", DANGER, "ejecución de código dinámico/ofuscado"),
    (r"set-mppreference\s+.*-disable|disable-windowsoptionalfeature.*defender", DANGER, "desactivar el antivirus (Defender)"),
    (r"netsh\s+advfirewall\s+set\s+.*\b(off|disable)", DANGER, "desactivar el firewall"),
    (r"reg\s+delete|remove-item\s+.*hk(lm|cu):", DANGER, "borrado en el registro de Windows"),
    # ── PRECAUCIÓN ──────────────────────────────────────────
    (r"\bsudo\b|runas\b|start-process\s+.*-verb\s+runas", CAUTION, "elevación de privilegios"),
    (r"set-executionpolicy\s+(unrestricted|bypass)", CAUTION, "rebajar la política de ejecución de PowerShell"),
    (r"git\s+push\s+.*--force|git\s+push\s+-f\b", CAUTION, "git push forzado (reescribe el remoto)"),
    (r"git\s+reset\s+--hard|git\s+clean\s+-[a-z]*f[a-z]*d|git\s+clean\s+-[a-z]*d[a-z]*f", CAUTION, "operación git que descarta cambios locales"),
    (r"chmod\s+(-r\s+)?777|chown\s+-r|icacls\s+.*\bgrant\b.*everyone", CAUTION, "cambio amplio de permisos"),
    (r"\b(shutdown|reboot|restart-computer|stop-computer)\b", CAUTION, "apagado o reinicio del sistema"),
    (r"taskkill\s+/f|kill\s+-9|stop-process\s+-force", CAUTION, "terminación forzada de procesos"),
    (r"\bnc\b\s+-l|ncat\s+.*-e|/bin/sh\s+-i", CAUTION, "posible shell de red / conexión inversa"),
    (r"pip\s+install\s+.*--break-system-packages", CAUTION, "instalación que puede romper el entorno del sistema"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), level, reason) for pat, level, reason in _RULES]


def analyze_command(command: str) -> dict:
    """Analiza un comando y devuelve {level, reasons, summary} (puro)."""
    cmd = (command or "").strip()
    if not cmd:
        return {"level": SAFE, "reasons": [], "summary": "Comando vacío, señor."}

    level = SAFE
    reasons = []
    for rx, rlevel, reason in _COMPILED:
        if rx.search(cmd):
            if reason not in reasons:
                reasons.append(reason)
            if _ORDER[rlevel] > _ORDER[level]:
                level = rlevel

    if level == DANGER:
        summary = "PELIGROSO"
    elif level == CAUTION:
        summary = "requiere precaución"
    else:
        summary = "sin riesgos evidentes"
    return {"level": level, "reasons": reasons, "summary": summary}


def is_dangerous(command: str) -> bool:
    return analyze_command(command)["level"] == DANGER


def format_for_voice(command: str) -> str:
    """Frase estilo Jarvis con el veredicto de seguridad."""
    a = analyze_command(command)
    motivos = "; ".join(a["reasons"][:2])
    if a["level"] == DANGER:
        return (f"⚠️ Señor, ese comando es PELIGROSO: {motivos}. "
                "Desaconsejo encarecidamente ejecutarlo.")
    if a["level"] == CAUTION:
        return f"Señor, ese comando requiere precaución: {motivos}. ¿Desea continuar?"
    return "Parece seguro, señor. No detecto riesgos evidentes en ese comando."
