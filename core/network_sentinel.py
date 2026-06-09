import os
import re
import json
import socket
import logging
import threading
import time
import uuid
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KNOWN_DEVICES_FILE = Path("logs/known_devices.json")
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

def is_private_ip(ip: str) -> bool:
    """Retorna True si la IP es privada (RFC 1918), loopback o link-local."""
    try:
        parts = [int(p) for p in ip.split('.')]
        if len(parts) != 4:
            return False
        # 127.0.0.0/8 (Loopback)
        if parts[0] == 127:
            return True
        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and (16 <= parts[1] <= 31):
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True
        # 169.254.0.0/16 (Link-local)
        if parts[0] == 169 and parts[1] == 254:
            return True
        return False
    except Exception:
        return False

# Estado global en memoria del centinela
active_devices = []        # Lista de dispositivos activos detectados en el último escaneo
voiced_alerts = set()      # MACs para las cuales ya se emitió una alerta por voz en esta sesión
sentinel_thread = None
stop_event = threading.Event()
scan_lock = threading.Lock()

def get_host_mac():
    """Obtiene la dirección MAC del host local formateada."""
    try:
        mac_num = uuid.getnode()
        mac_str = ':'.join(f'{(mac_num >> i) & 0xff:02x}' for i in range(40, -8, -8))
        return mac_str
    except Exception:
        return "00:00:00:00:00:00"

def load_known_devices():
    """Carga la lista de dispositivos de confianza."""
    if not KNOWN_DEVICES_FILE.exists():
        # Crear archivo inicial autorizando al host local
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        host_mac = get_host_mac()
        initial_data = {
            "known_macs": [host_mac],
            "device_names": {
                host_mac: "Servidor Jarvis (Este Equipo)"
            }
        }
        KNOWN_DEVICES_FILE.write_text(
            json.dumps(initial_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return initial_data

    try:
        return json.loads(KNOWN_DEVICES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logging.error(f"[Sentinel] Error al leer known_devices.json: {e}")
        return {"known_macs": [], "device_names": {}}

def save_known_devices(data):
    """Guarda la lista de dispositivos de confianza."""
    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        KNOWN_DEVICES_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logging.error(f"[Sentinel] Error al guardar known_devices.json: {e}")

def trust_device(mac, name):
    """Agrega un dispositivo a la lista de confianza."""
    mac = mac.strip().lower().replace("-", ":")
    data = load_known_devices()
    
    if mac not in data["known_macs"]:
        data["known_macs"].append(mac)
    data["device_names"][mac] = name
    
    save_known_devices(data)
    logging.info(f"[Sentinel] Dispositivo {mac} marcado como de confianza: {name}")
    
    # Quitar de alertas sonoras emitidas por si reconecta en el futuro
    voiced_alerts.discard(mac)
    
    # Recargar y emitir la actualización a la GUI
    run_quick_scan()

def get_subnet_prefix():
    """Detecta la IP local del adaptador activo y extrae el prefijo de red (ej: 192.168.1.)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Intentamos conectar a una IP externa (no envía datos realmente)
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    
    if ip == '127.0.0.1':
        return None, None
        
    parts = ip.split('.')
    prefix = f"{parts[0]}.{parts[1]}.{parts[2]}."
    return ip, prefix

def _ping_ip(ip):
    """Envía un único paquete ICMP de ping de forma silenciosa."""
    try:
        if os.name == 'nt':
            cmd = ["ping", "-n", "1", "-w", "80", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]
            
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )
    except Exception:
        pass

def run_ping_sweep(prefix):
    """Escanea la subred en paralelo con pings cortos para poblar la caché ARP."""
    ips = [f"{prefix}{i}" for i in range(1, 255)]
    try:
        workers = int(os.getenv("JARVIS_NETWORK_SCAN_WORKERS", "20"))
    except (ValueError, TypeError):
        workers = 20
    # Limitar a un máximo absoluto de 25 para no saturar el sistema
    workers = max(1, min(workers, 25))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        executor.map(_ping_ip, ips)

def parse_arp_output():
    """Ejecuta el comando arp y extrae las direcciones IP y MAC."""
    devices = []
    try:
        # Probar arp -a
        cmd = ["arp", "-a"]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            encoding="oem" if os.name == 'nt' else 'utf-8',
            errors='ignore'
        )
        output = res.stdout
    except Exception as e:
        logging.error(f"[Sentinel] Fallo al ejecutar arp -a: {e}")
        return devices

    lines = output.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        # Buscar patrones de IP y MAC en la línea
        ip_match = re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', line_clean)
        mac_match = re.search(r'(([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})', line_clean)
        
        if ip_match and mac_match:
            ip = ip_match.group(0)
            mac = mac_match.group(0).replace("-", ":").lower()
            
            # Evitar broadcast/multicast comunes
            if ip.endswith(".255") or ip.startswith("224.") or ip.startswith("239.") or mac == "ff:ff:ff:ff:ff:ff":
                continue
                
            devices.append({"ip": ip, "mac": mac})
            
    return devices

def emit_network_update(devices_list):
    """Envía la lista completa de dispositivos a la GUI mediante websockets."""
    try:
        from gui.app import socketio
        socketio.emit('network_devices_update', devices_list)
    except Exception as e:
        logging.warning(f"[Sentinel] No se pudo emitir actualización de Socket.IO: {e}")

def notify_new_strange_devices(devices):
    """Envía alertas locales por voz y notifica al bot de Telegram para una lista de dispositivos."""
    if not devices:
        return

    # 1. Alerta por voz local (asíncrona) sin VAD para evitar cortes de audio
    from tools.voice import speak
    if len(devices) == 1:
        ip = devices[0]["ip"]
        speak(f"Advertencia: Dispositivo desconocido detectado en la red. Dirección IP: {ip}.", disable_vad=True)
    else:
        ips_str = ", ".join(d["ip"] for d in devices[:-1]) + f" y {devices[-1]['ip']}"
        speak(f"Advertencia: Se han detectado {len(devices)} dispositivos desconocidos en la red. Direcciones IP: {ips_str}.", disable_vad=True)
    
    # 2. Alerta por Telegram (si está configurado) para cada dispositivo detectado
    from core.telegram_bot import bot as tg_bot
    telegram_user = os.getenv("TELEGRAM_USER_ID")
    if tg_bot and telegram_user:
        for dev in devices:
            ip = dev["ip"]
            mac = dev["mac"]
            try:
                msg = (
                    f"⚠️ *Alerta Centinela de Red*:\n\n"
                    f"Se ha detectado un dispositivo desconocido conectado a tu red Wi-Fi.\n\n"
                    f"📍 *IP*: `{ip}`\n"
                    f"🔑 *MAC*: `{mac}`\n\n"
                    f"Para confiar en este dispositivo, responde con:\n"
                    f"`/trust {mac} Nombre_del_Dispositivo`"
                )
                tg_bot.send_message(telegram_user, msg, parse_mode="Markdown")
                logging.info(f"[Sentinel] Alerta de seguridad enviada a Telegram para MAC: {mac}")
            except Exception as e:
                logging.error(f"[Sentinel] Error al enviar alerta de Telegram para MAC {mac}: {e}")

def scan_network():
    """
    Realiza un barrido completo de red y actualiza la lista de dispositivos.
    Este componente es de solo lectura (pasivo): utiliza pings cortos y la tabla ARP local.
    """
    global active_devices
    
    with scan_lock:
        local_ip, prefix = get_subnet_prefix()
        if not prefix or not local_ip:
            logging.warning("[Sentinel] No se detectó red local activa (IP de bucle/offline).")
            return []
            
        # Limitar estrictamente el escaneo a subredes privadas locales para evitar barridos en IPs públicas
        if not is_private_ip(local_ip):
            logging.warning(f"[Sentinel] La dirección IP local '{local_ip}' no pertenece a un rango privado de red. Abortando escaneo por seguridad.")
            return []
            
        logging.info(f"[Sentinel] Iniciando sweep en subred local privada {prefix}0/24...")
        run_ping_sweep(prefix)
        
        logging.info("[Sentinel] Analizando tabla ARP (modo solo lectura)...")
        raw_devices = parse_arp_output()
        
        # Cargar dispositivos conocidos
        known_data = load_known_devices()
        known_macs = known_data.get("known_macs", [])
        device_names = known_data.get("device_names", {})
        
        # Filtrar dispositivos duplicados y restringir a la subred activa
        seen_macs = set()
        scanned_devices = []
        new_strange_devices = []
        
        for dev in raw_devices:
            ip = dev["ip"]
            mac = dev["mac"]
            
            # Filtro de subred e interfaces locales
            if not ip.startswith(prefix) or ip == local_ip:
                continue
                
            if mac in seen_macs:
                continue
            seen_macs.add(mac)
            
            is_known = mac in known_macs
            name = device_names.get(mac, "Dispositivo Desconocido")
            
            scanned_devices.append({
                "ip": ip,
                "mac": mac,
                "known": is_known,
                "name": name
            })
            
            # Si es un dispositivo extraño no alertado aún
            if not is_known and mac not in voiced_alerts:
                voiced_alerts.add(mac)
                new_strange_devices.append({"ip": ip, "mac": mac})
                
        if new_strange_devices:
            # Notificar asíncronamente
            threading.Thread(
                target=notify_new_strange_devices,
                args=(new_strange_devices,),
                daemon=True
            ).start()
                
        active_devices = scanned_devices
        
        # Registrar dispositivos en logs principales
        logging.info(f"[Sentinel] Escaneo completado. {len(active_devices)} dispositivos activos en subred.")
        known_devs = [d for d in active_devices if d["known"]]
        unknown_devs = [d for d in active_devices if not d["known"]]
        
        logging.info(f"[Sentinel] Dispositivos CONOCIDOS activos ({len(known_devs)}):")
        for d in known_devs:
            logging.info(f"  - IP: {d['ip']}, MAC: {d['mac']}, Nombre: {d['name']}")
            
        logging.info(f"[Sentinel] Dispositivos DESCONOCIDOS activos ({len(unknown_devs)}):")
        for d in unknown_devs:
            logging.info(f"  - IP: {d['ip']}, MAC: {d['mac']}")
            
        # Registrar y guardar en logs/last_network_scan.json
        try:
            last_scan_file = Path("logs/last_network_scan.json")
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            last_scan_file.write_text(
                json.dumps(active_devices, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logging.error(f"[Sentinel] Error al escribir logs/last_network_scan.json: {e}")
            
        return active_devices

def run_quick_scan():
    """Ejecuta un escaneo rápido y actualiza la GUI inmediatamente."""
    def task():
        devices = scan_network()
        emit_network_update(devices)
    threading.Thread(target=task, daemon=True).start()

def network_sentinel_loop():
    """Bucle principal periódico del Centinela de Red."""
    interval = int(os.getenv("JARVIS_SENTINEL_INTERVAL", "300"))
    if interval < 60:
        logging.warning(f"[Sentinel] El intervalo configurado {interval}s es demasiado bajo. Usando 60 segundos por seguridad.")
        interval = 60
        
    # Pequeño retraso al iniciar el servidor para no ralentizar el arranque principal
    if stop_event.wait(timeout=5):
        return
        
    while not stop_event.is_set():
        if os.getenv("JARVIS_SENTINEL_ENABLED", "True").lower() == "true":
            try:
                devices = scan_network()
                emit_network_update(devices)
            except Exception as e:
                logging.error(f"[Sentinel] Error en bucle del centinela: {e}")
        if stop_event.wait(timeout=interval):
            break

def start_network_sentinel():
    """Arranca el hilo secundario del Centinela de Red. Es idempotente."""
    global sentinel_thread
    enabled = os.getenv("JARVIS_SENTINEL_ENABLED", "True").lower() == "true"
    if not enabled:
        logging.info("[Sentinel] Centinela de Red Local desactivado en .env.")
        return
        
    if sentinel_thread is not None and sentinel_thread.is_alive():
        logging.info("[Sentinel] Centinela de Red Local ya en ejecución.")
        return
        
    logging.info("[Sentinel] Inicializando Centinela de Red Local...")
    stop_event.clear()
    sentinel_thread = threading.Thread(
        target=network_sentinel_loop,
        name="NetworkSentinelThread",
        daemon=True
    )
    sentinel_thread.start()

def stop_network_sentinel():
    """Detiene el centinela de red local de forma limpia."""
    logging.info("[Sentinel] Deteniendo centinela de red...")
    stop_event.set()
