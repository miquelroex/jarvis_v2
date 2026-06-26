"""
core/damage_report.py — "Informe de Daños" (Damage Report) estilo traje Stark.

Traduce el estado real del sistema (CPU, RAM, temperatura, servicios, nivel de
amenaza) a la jerga de subsistemas de un traje de Iron Man, con un veredicto
final. Reutiliza self_monitor y thermal_telemetry.

build_damage_report es puro y testeable; la recolección de métricas se aísla.
"""
import logging

logger = logging.getLogger(__name__)

_THREAT_ES = {"green": "verde", "amber": "ámbar", "red": "rojo", "violet": "violeta"}


def _status_word(pct, warn=75, crit=90) -> str:
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return "desconocido"
    if pct >= crit:
        return "crítico"
    if pct >= warn:
        return "elevado"
    return "nominal"


def _temp_word(temp) -> str:
    try:
        temp = float(temp)
    except (TypeError, ValueError):
        return "nominales"
    if temp >= 85:
        return "críticos"
    if temp >= 70:
        return "elevados"
    return "nominales"


def build_damage_report(m: dict) -> str:
    """Construye el informe de daños a partir de las métricas (puro)."""
    cpu = m.get("cpu", 0)
    ram = m.get("ram", 0)
    temp = m.get("temp")
    running = m.get("services_running", 0)
    down = m.get("services_down", 0)
    threat = (m.get("threat") or "green").lower()

    lines = ["Informe de daños, señor."]
    lines.append(f"Núcleo de procesamiento al {cpu}%, estado {_status_word(cpu)}.")
    lines.append(f"Reservas de memoria al {ram}%, estado {_status_word(ram)}.")
    if temp is not None:
        lines.append(f"Sistema de refrigeración a {temp} grados; disipadores {_temp_word(temp)}.")
    else:
        lines.append("Telemetría térmica no disponible.")
    if down:
        plural = "s" if down != 1 else ""
        lines.append(f"Atención: {down} subsistema{plural} fuera de línea de {running + down}.")
    else:
        lines.append(f"{running} subsistemas operativos, todos en línea.")
    if threat != "green":
        lines.append(f"Nivel de amenaza en {_THREAT_ES.get(threat, threat)}.")

    def _num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    critical = (_num(cpu) >= 90 or _num(ram) >= 90 or down > 0
                or threat in ("red", "violet") or (temp is not None and _num(temp) >= 85))
    warning = (_num(cpu) >= 75 or _num(ram) >= 75 or threat == "amber"
               or (temp is not None and _num(temp) >= 70))

    if critical:
        lines.append("Recomiendo intervención inmediata, señor.")
    elif warning:
        lines.append("Operando bajo carga, pero dentro de tolerancias, señor.")
    else:
        lines.append("Todos los sistemas nominales, señor.")
    return " ".join(lines)


def _gather_metrics() -> dict:
    """Recolecta métricas reales de self_monitor y thermal (best-effort)."""
    m = {"cpu": 0, "ram": 0, "temp": None, "services_running": 0, "services_down": 0, "threat": "green"}
    try:
        from core.self_monitor import get_health_dashboard
        d = get_health_dashboard()
        sysm = d.get("system", {}) or {}
        svc = d.get("services", {}) or {}
        m["cpu"] = sysm.get("cpu_percent", 0)
        m["ram"] = sysm.get("system_ram_percent", 0)
        m["services_running"] = svc.get("running", 0)
        m["services_down"] = svc.get("stopped", 0)
        m["threat"] = d.get("threat_level", "green")
    except Exception as e:
        logger.warning(f"[DamageReport] No se pudo leer el dashboard: {e}")
    try:
        from core.thermal_telemetry import get_thermal_snapshot
        m["temp"] = get_thermal_snapshot().get("cpu_temp")
    except Exception:
        m["temp"] = None
    return m


def get_damage_report() -> str:
    """Informe de daños con las métricas reales del sistema."""
    return build_damage_report(_gather_metrics())
