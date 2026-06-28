"""
core/predictive.py — Mantenimiento Predictivo ("antes de que ocurra").

Jarvis muestrea periódicamente señales que crecen con el tiempo (uso de disco,
RAM) y EXTRAPOLA su tendencia para avisarte de un fallo ANTES de que pase: *"A
este ritmo, el disco se llena en 3 días, señor."*. Complementa el Informe de
Daños (estado actual) con una mirada al futuro.

El ajuste lineal, el tiempo hasta el umbral y el fraseo son funciones PURAS y
testeables sobre una lista de muestras; el muestreo (psutil/shutil), el registro
y el daemon se aíslan. Off por defecto.
"""
import os
import json
import time
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLES_FILE = Path("logs/predictive_samples.jsonl")
_lock = threading.Lock()

PREDICTIVE_THREAD = None
stop_event = threading.Event()
_last_warn = 0.0


# ----------------------------------------------------------------------------
# Núcleo puro (regresión lineal + extrapolación)
# ----------------------------------------------------------------------------
def linear_slope(points):
    """Pendiente por mínimos cuadrados de [(x, y), …]. None si no se puede. Puro."""
    pts = [(float(x), float(y)) for x, y in (points or [])]
    n = len(pts)
    if n < 2:
        return None
    sx = sum(x for x, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts)
    sxy = sum(x * y for x, y in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    return (n * sxy - sx * sy) / denom


def slope_per_day(samples, key):
    """Variación por DÍA de `key` a lo largo de las muestras (puro). None si no hay."""
    pts = []
    for s in samples or []:
        ts = s.get("ts")
        if ts is None or key not in s or s[key] is None:
            continue
        pts.append((ts / 86400.0, s[key]))
    return linear_slope(pts)


def days_to_threshold(current, threshold, per_day):
    """Días hasta que `current` alcance `threshold` al ritmo `per_day`. Puro.

    None si no sube (per_day <= 0). 0 si ya está en/por encima del umbral."""
    if per_day is None or per_day <= 0:
        return None
    if current >= threshold:
        return 0.0
    return (threshold - current) / per_day


def humanize_days(days) -> str:
    """Expresión natural de un horizonte en días (puro)."""
    if days is None:
        return "sin horizonte previsible"
    if days < 1:
        return "menos de un día"
    d = int(round(days))
    if d == 1:
        return "1 día"
    if d < 14:
        return f"{d} días"
    if d < 60:
        return f"unas {d // 7} semanas"
    return f"unos {d // 30} meses"


def predict_metric(samples, key, current, threshold):
    """Predicción de una métrica: {slope, days}. Puro."""
    slope = slope_per_day(samples, key)
    return {"slope": slope, "days": days_to_threshold(current, threshold, slope)}


def build_report(samples, current_disk, current_ram, dep_aging=0,
                 disk_threshold=92.0, ram_threshold=95.0, horizon_days=30) -> str:
    """Informe de mantenimiento predictivo (puro)."""
    if len(samples or []) < 3:
        return ("Aún no tengo suficiente histórico para predecir, señor. "
                "Déjeme observar las tendencias un poco más.")
    partes = []
    disk = predict_metric(samples, "disk", current_disk, disk_threshold)
    if disk["days"] is not None and disk["days"] <= horizon_days:
        partes.append(f"a este ritmo el disco se llenará en {humanize_days(disk['days'])}")
    elif disk["slope"] is not None and disk["slope"] > 0:
        partes.append("el disco crece despacio, sin riesgo a la vista")
    else:
        partes.append("el uso de disco es estable")

    ram = predict_metric(samples, "ram", current_ram, ram_threshold)
    if ram["days"] is not None and ram["days"] <= horizon_days:
        partes.append(f"la RAM tiende al límite en {humanize_days(ram['days'])}")

    if dep_aging:
        partes.append(f"{dep_aging} dependencia(s) envejeciendo")

    return "Mantenimiento predictivo, señor: " + "; ".join(partes) + "."


def critical_disk_warning(samples, current_disk, disk_threshold=92.0, horizon_days=7):
    """Aviso si el disco se llenará pronto, o None (puro). Para el daemon proactivo."""
    if len(samples or []) < 3:
        return None
    disk = predict_metric(samples, "disk", current_disk, disk_threshold)
    if disk["days"] is not None and 0 < disk["days"] <= horizon_days:
        return (f"Señor, a este ritmo el disco se llenará en {humanize_days(disk['days'])}. "
                "Convendría liberar espacio.")
    return None


# ----------------------------------------------------------------------------
# Muestreo / registro (aislado)
# ----------------------------------------------------------------------------
def _current_metrics() -> dict:
    """Snapshot actual de disco y RAM (%)."""
    out = {"ts": time.time()}
    try:
        import shutil
        total, used, _free = shutil.disk_usage(os.getenv("JARVIS_PREDICTIVE_DISK_PATH", "C:\\"))
        out["disk"] = round(used / total * 100, 2) if total else None
    except Exception as e:
        logger.debug(f"[Predictive] Sin lectura de disco: {e}")
    try:
        import psutil
        out["ram"] = round(psutil.virtual_memory().percent, 2)
    except Exception as e:
        logger.debug(f"[Predictive] Sin lectura de RAM: {e}")
    return out


def record_sample(metrics=None):
    """Registra una muestra de métricas (best-effort)."""
    metrics = metrics or _current_metrics()
    try:
        with _lock:
            SAMPLES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SAMPLES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[Predictive] No se pudo registrar la muestra: {e}")


def load_samples(limit=500):
    if not SAMPLES_FILE.exists():
        return []
    out = []
    try:
        with _lock:
            lines = SAMPLES_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"[Predictive] No se pudo leer el histórico: {e}")
    return out


def _dep_aging_count() -> int:
    try:
        from core.dependency_health import REPORT_FILE
        if REPORT_FILE.exists():
            data = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
            items = data.get("dependencies", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                return sum(1 for d in items if isinstance(d, dict) and d.get("outdated"))
    except Exception:
        pass
    return 0


def get_report() -> str:
    """Informe predictivo bajo demanda."""
    cur = _current_metrics()
    return build_report(load_samples(), cur.get("disk", 0), cur.get("ram", 0), _dep_aging_count())


# ----------------------------------------------------------------------------
# Daemon (muestreo + aviso proactivo)
# ----------------------------------------------------------------------------
def _notify(message: str):
    try:
        from core.narration import narrate
        narrate(message, speak=os.getenv("JARVIS_PREDICTIVE_VOICE", "false").lower()
                in ("true", "1", "yes"), tone="alert")
    except Exception:
        pass


def run_once():
    """Muestrea, registra y avisa si hay un fallo de disco previsible (con cooldown)."""
    global _last_warn
    cur = _current_metrics()
    record_sample(cur)
    warn = critical_disk_warning(load_samples(), cur.get("disk", 0))
    if warn and time.time() - _last_warn > float(os.getenv("JARVIS_PREDICTIVE_COOLDOWN", "86400")):
        _last_warn = time.time()
        _notify(warn)


def _predictive_loop():
    if stop_event.wait(timeout=60):
        return
    while not stop_event.is_set():
        try:
            run_once()
        except Exception as e:
            logger.error(f"[Predictive] Error en el bucle: {e}")
        interval = int(os.getenv("JARVIS_PREDICTIVE_INTERVAL", "3600"))
        if stop_event.wait(timeout=interval):
            break


def start_predictive_daemon():
    """Lanza el mantenimiento predictivo. Off por defecto (JARVIS_PREDICTIVE_ENABLED)."""
    global PREDICTIVE_THREAD
    if os.getenv("JARVIS_PREDICTIVE_ENABLED", "false").lower() not in ("true", "1", "yes"):
        logging.info("[Predictive] Desactivado en .env.")
        return
    if PREDICTIVE_THREAD is not None and PREDICTIVE_THREAD.is_alive():
        return
    stop_event.clear()
    PREDICTIVE_THREAD = threading.Thread(target=_predictive_loop, name="PredictiveDaemon", daemon=True)
    PREDICTIVE_THREAD.start()
    logging.info("[Predictive] Mantenimiento predictivo iniciado.")


def stop_predictive_daemon():
    """Detiene el mantenimiento predictivo."""
    stop_event.set()
