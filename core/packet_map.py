"""
core/packet_map.py — Stark HUD: Telemetría de Red (Packet Map 3D).

Enumera las conexiones de red activas de ESTE equipo (sockets TCP/UDP con un
extremo remoto) y construye un grafo: un nodo central "ESTE EQUIPO" y nodos por
endpoint remoto (IP), con haces de luz por conexión. La GUI lo proyecta en 3D
(estilo sala de control de Stark Industries).

Es distinto del Radar de Red (que muestra los dispositivos presentes en la LAN):
aquí se ve hacia dónde se conecta tu máquina en tiempo real.

La construcción del grafo es pura y testeable (sobre una lista de conexiones);
psutil y la emisión a la GUI se aíslan. Un daemon emite 'packet_map_update'.
"""
import os
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PACKET_THREAD = None
stop_event = threading.Event()


def _classify_ip(ip: str) -> str:
    """Clasifica una IP remota en loopback / private / public (puro)."""
    if not ip:
        return "public"
    if ip.startswith("127.") or ip == "::1":
        return "loopback"
    if (ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("169.254.")
            or ip.startswith("fe80") or ip.startswith("fc") or ip.startswith("fd")):
        return "private"
    if ip.startswith("172."):
        try:
            second = int(ip.split(".")[1])
            if 16 <= second <= 31:
                return "private"
        except (ValueError, IndexError):
            pass
    return "public"


def build_packet_graph(connections) -> dict:
    """Construye el grafo {center, nodes, edges} a partir de una lista de
    conexiones [{raddr:(ip,port)|None, status, proc}] (puro).

    Agrega por IP remota: nº de conexiones, puertos y procesos implicados."""
    agg = {}
    total = 0
    for c in connections or []:
        raddr = c.get("raddr")
        if not raddr:
            continue  # sólo conexiones con extremo remoto
        ip, port = raddr[0], raddr[1]
        if not ip:
            continue
        total += 1
        node = agg.setdefault(ip, {
            "id": ip, "label": ip, "group": _classify_ip(ip),
            "count": 0, "ports": set(), "procs": set(), "statuses": set(),
        })
        node["count"] += 1
        if port:
            node["ports"].add(int(port))
        if c.get("proc"):
            node["procs"].add(c["proc"])
        if c.get("status"):
            node["statuses"].add(c["status"])

    nodes = []
    edges = []
    for ip in sorted(agg.keys()):
        n = agg[ip]
        nodes.append({
            "id": n["id"],
            "label": n["label"],
            "group": n["group"],
            "count": n["count"],
            "ports": sorted(n["ports"])[:8],
            "procs": sorted(n["procs"])[:4],
            "statuses": sorted(n["statuses"]),
        })
        edges.append({"target": ip, "weight": n["count"]})

    return {
        "center": "ESTE EQUIPO",
        "nodes": nodes,
        "edges": edges,
        "endpoint_count": len(nodes),
        "connection_count": total,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _proc_name(pid):
    if not pid:
        return None
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return None


def _read_connections():
    """Lee las conexiones inet activas vía psutil (best-effort)."""
    try:
        import psutil
    except Exception:
        return []
    out = []
    try:
        for c in psutil.net_connections(kind="inet"):
            if not c.raddr:
                continue
            out.append({
                "raddr": (c.raddr.ip, c.raddr.port),
                "laddr": (c.laddr.ip, c.laddr.port) if c.laddr else None,
                "status": c.status,
                "proc": _proc_name(c.pid),
            })
    except Exception as e:
        logger.warning(f"[PacketMap] No se pudieron leer las conexiones: {e}")
    return out


def get_packet_map() -> dict:
    """Snapshot del grafo de conexiones de red activas."""
    return build_packet_graph(_read_connections())


def _emit(event: str, payload=None):
    import sys
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        if payload is None:
            mod.socketio.emit(event)
        else:
            mod.socketio.emit(event, payload)
    except Exception:
        pass


def emit_packet_map() -> dict:
    report = get_packet_map()
    _emit("packet_map_update", report)
    return report


def open_packet_map():
    """Abre el Packet Map 3D en la GUI y envía un snapshot inmediato."""
    _emit("packet_open")
    emit_packet_map()


def close_packet_map():
    """Cierra el Packet Map 3D en la GUI."""
    _emit("packet_close")


def _packet_loop():
    if stop_event.wait(timeout=8):
        return
    while not stop_event.is_set():
        try:
            emit_packet_map()
        except Exception as e:
            logger.error(f"[PacketMap] Error en el bucle del daemon: {e}")
        interval = int(os.getenv("JARVIS_PACKET_MAP_INTERVAL", "6"))
        if stop_event.wait(timeout=interval):
            break


def start_packet_map_daemon():
    """Lanza el daemon del Packet Map. Idempotente. Activado por defecto (ligero);
    desactivable con JARVIS_PACKET_MAP_ENABLED=false."""
    global PACKET_THREAD
    if os.getenv("JARVIS_PACKET_MAP_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logging.info("[PacketMap] Desactivado en .env.")
        return
    if PACKET_THREAD is not None and PACKET_THREAD.is_alive():
        return
    stop_event.clear()
    PACKET_THREAD = threading.Thread(target=_packet_loop, name="PacketMapDaemon", daemon=True)
    PACKET_THREAD.start()
    logging.info("[PacketMap] Daemon de telemetría de red iniciado.")


def stop_packet_map_daemon():
    """Detiene el daemon del Packet Map."""
    stop_event.set()
