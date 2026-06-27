import os
import webbrowser
import unicodedata
import re
from datetime import datetime

from tools.browser import open_website
from tools.launcher import open_windows_app
from tools.time import get_time
from tools.date import get_date

def normalize_text(text: str) -> str:
    """Normaliza el texto quitando acentos, convirtiendo a minúsculas y limpiando espacios."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text


def _record_anticipation(action: str):
    """Registra una acción para el motor de anticipación (best-effort)."""
    try:
        from core.anticipation import record_action
        record_action(action)
    except Exception:
        pass

def handle_fast_command(command: str):
    """
    Comprueba si el comando introducido coincide con una orden local rápida
    (abrir navegador, aplicaciones de Windows, preguntar la hora/fecha).
    Retorna la respuesta de Jarvis si se maneja localmente, o None si debe ir al agente.
    """
    text = normalize_text(command)

    # --- Comando rápido: Protocolo "Mayordomo" (prepara entorno + parte del día) ---
    if any(kw in text for kw in ["protocolo mayordomo", "modo mayordomo", "activa el protocolo mayordomo",
                                 "prepara mi estacion", "prepara mi entorno", "prepara el entorno",
                                 "prepara mi puesto", "buenos dias jarvis", "buenas jarvis prepara"]):
        import threading
        from core.butler import run_butler
        threading.Thread(target=run_butler, name="ButlerRun", daemon=True).start()
        return "De inmediato, señor. Preparando su estación de trabajo y el parte del día."

    # --- Comandos rápidos de Memoria Persistente ---
    from core.memory import save_memory, search_memories, delete_memory_by_content, get_all_memories

    # 1. Guardar recuerdos
    match_save_pref = None
    for pref in ["recuerda que ", "recuerda ", "guardar en memoria "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_save_pref = pref
            break
    if match_save_pref is not None:
        content_to_save = command[len(match_save_pref):].strip()
        if content_to_save:
            saved = save_memory(content_to_save, category="preference", source="fast_command")
            if saved:
                return f"Entendido, señor. He guardado en mi memoria: {content_to_save}."
            else:
                return f"Señor, ese recuerdo ya estaba registrado en mi memoria."
        return "Señor, ¿qué es lo que desea que recuerde?"

    # 2. Olvidar recuerdos
    match_delete_pref = None
    for pref in ["olvida que ", "olvida ", "borra de tu memoria "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_delete_pref = pref
            break
    if match_delete_pref is not None:
        content_to_delete = command[len(match_delete_pref):].strip()
        if content_to_delete:
            deleted = delete_memory_by_content(content_to_delete)
            if deleted:
                return f"Entendido, señor. He olvidado lo relacionado con: {content_to_delete}."
            else:
                return f"No he encontrado ningún recuerdo relacionado con '{content_to_delete}', señor."
        return "Señor, ¿qué recuerdo desea que olvide?"

    # 3. Consultar recuerdos
    # Consulta general
    if text == "que recuerdas" or text == "dime mis recuerdos":
        mems = get_all_memories(limit=20)
        if mems:
            formatted = "\n".join(f"- {m['content']}" for m in mems)
            return f"Esto es lo que recuerdo, señor:\n{formatted}"
        return "No tengo recuerdos guardados por ahora, señor."

    # Consulta específica
    match_query_pref = None
    for pref in ["que recuerdas de ", "que recuerdas sobre "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            match_query_pref = pref
            break
    if match_query_pref is not None:
        query_text = command[len(match_query_pref):].strip()
        if query_text:
            # Primero búsqueda semántica (por significado); si no hay, subcadena.
            matches = []
            try:
                from core.semantic_memory import semantic_search
                matches = semantic_search(query_text, top_k=5, min_score=0.5)
            except Exception:
                matches = []
            if not matches:
                matches = search_memories(query_text)
            if matches:
                formatted = "\n".join(f"- {m['content']}" for m in matches)
                return f"Recuerdo lo siguiente sobre '{query_text}', señor:\n{formatted}"
            return f"No tengo recuerdos relacionados con '{query_text}', señor."
        return "Señor, ¿de qué desea que haga memoria?"

    # --- Comando rápido: reindexar la memoria semántica ---
    reindex_keywords = [
        "reindexa la memoria", "reindexar la memoria", "indexa los recuerdos",
        "reindexa los recuerdos", "reindexar memoria"
    ]
    if any(kw in text for kw in reindex_keywords):
        from core.semantic_memory import backfill_embeddings
        n = backfill_embeddings()
        if n > 0:
            return f"Entendido, señor. He indexado {n} recuerdo(s) para la búsqueda semántica."
        return "Señor, no hay recuerdos pendientes de indexar, o la indexación no está disponible."


    # --- Comandos rápidos del Centinela de Pruebas ---
    from core.test_watcher import start_test_watcher, stop_test_watcher, is_watcher_running, get_watcher_status
    
    # Activar
    activate_keywords = [
        "activa el centinela de pruebas", "activar centinela de pruebas", 
        "iniciar centinela", "activa el watcher de tests", "iniciar watcher de tests"
    ]
    if any(kw in text for kw in activate_keywords):
        if is_watcher_running():
            return "Señor, el centinela de pruebas ya está activo en segundo plano."
        start_test_watcher(force=True)
        return "Entendido, señor. He activado el centinela de pruebas en segundo plano."
        
    # Desactivar
    deactivate_keywords = [
        "desactiva el centinela de pruebas", "desactivar centinela de pruebas", 
        "detener centinela", "desactiva el watcher de tests", "detener watcher de tests"
    ]
    if any(kw in text for kw in deactivate_keywords):
        if not is_watcher_running():
            return "Señor, el centinela de pruebas ya estaba inactivo."
        stop_test_watcher()
        return "Entendido, señor. He desactivado el centinela de pruebas."
        
    # Estado
    status_keywords = [
        "estado del centinela de pruebas", "estado del centinela", 
        "estado del watcher", "como estan los tests", "situacion de los tests"
    ]
    if any(kw in text for kw in status_keywords):
        status = get_watcher_status()
        running_str = "activo" if status["running"] else "inactivo"
        last_run = status["last_run"]
        
        resp = f"El centinela de pruebas se encuentra actualmente {running_str}, señor.\n"
        if last_run["last_run_time"]:
            time_str = datetime.fromtimestamp(last_run["last_run_time"]).strftime("%H:%M:%S")
            outcome = "exitoso" if last_run["last_success"] else "fallido"
            resp += f"Última comprobación: {time_str} ({last_run['last_test_module']}) -> Estado: {outcome}."
        else:
            resp += "Aún no se ha realizado ninguna comprobación de cambios."
        return resp


    # --- Comando rápido: estado de los servicios locales ---
    services_status_keywords = [
        "estado de los servicios", "estado de servicios",
        "estado de los servicios locales", "como estan los servicios",
        "que servicios estan activos", "informe de servicios"
    ]
    if any(kw in text for kw in services_status_keywords):
        from core.services import get_services_status
        status = get_services_status()
        running = [name for name, st in status.items() if st == "running"]
        stopped = [name for name, st in status.items() if st == "stopped"]
        disabled = [name for name, st in status.items() if st == "disabled"]

        def _pretty(name):
            return name.replace("_", " ")

        resp = (
            f"Señor, informe de servicios: {len(running)} activos, "
            f"{len(stopped)} detenidos y {len(disabled)} desactivados."
        )
        if running:
            resp += "\nActivos: " + ", ".join(_pretty(s) for s in running) + "."
        if stopped:
            resp += "\nDetenidos: " + ", ".join(_pretty(s) for s in stopped) + "."
        return resp


    # --- Comandos rápidos: control de audio del sistema ---
    # Reactivar sonido (comprobar antes que "silencio" porque lo contiene)
    if any(kw in text for kw in ["quita el silencio", "activa el sonido", "reactiva el sonido", "desmutea"]):
        from core.system_audio import set_mute
        set_mute(False)
        return "Sonido reactivado, señor."
    if any(kw in text for kw in ["silencia", "silencio", "mutea", "quita el sonido"]):
        from core.system_audio import set_mute
        set_mute(True)
        return "Silenciado, señor."
    # Fijar el volumen a un valor concreto
    if "volumen" in text and (" al " in text or " a " in text):
        match_vol = re.search(r"\b(\d{1,3})\b", text)
        if match_vol:
            from core.system_audio import set_volume
            v = set_volume(int(match_vol.group(1)))
            return (f"Volumen al {v} por ciento, señor." if v >= 0
                    else "Señor, no puedo controlar el volumen ahora mismo.")
    # Subir / bajar volumen
    if any(kw in text for kw in ["sube el volumen", "sube volumen", "mas volumen", "mas alto"]):
        from core.system_audio import change_volume
        v = change_volume(15)
        return (f"Volumen al {v} por ciento, señor." if v >= 0
                else "Señor, no puedo controlar el volumen ahora mismo.")
    if any(kw in text for kw in ["baja el volumen", "baja volumen", "menos volumen", "mas bajo"]):
        from core.system_audio import change_volume
        v = change_volume(-15)
        return (f"Volumen al {v} por ciento, señor." if v >= 0
                else "Señor, no puedo controlar el volumen ahora mismo.")
    # Consultar volumen
    if any(kw in text for kw in ["que volumen hay", "volumen actual", "cuanto volumen"]):
        from core.system_audio import get_volume
        v = get_volume()
        return (f"El volumen está al {v} por ciento, señor." if v >= 0
                else "Señor, no puedo leer el volumen ahora mismo.")
    # Multimedia (Spotify y reproductores): play/pausa, siguiente, anterior
    if any(kw in text for kw in ["siguiente cancion", "cancion siguiente", "siguiente tema", "pasa de cancion"]):
        from core.system_audio import media_action
        media_action("next")
        return "Siguiente, señor."
    if any(kw in text for kw in ["cancion anterior", "anterior cancion", "tema anterior", "cancion previa"]):
        from core.system_audio import media_action
        media_action("previous")
        return "Anterior, señor."
    if any(kw in text for kw in ["pausa la musica", "reproduce la musica", "reanuda la musica",
                                 "pausa la cancion", "pon la musica", "para la musica", "pausa musica"]):
        from core.system_audio import media_action
        media_action("play_pause")
        return "Hecho, señor."


    # --- Comandos rápidos: Mapa / Globo 3D del mundo ---
    # Volar a un lugar (comprobar prefijos antes que abrir/cerrar)
    map_fly_prefixes = [
        "llevame a ", "llevame al ", "llevame hasta ", "vuela a ", "vuela hasta ",
        "viaja a ", "muestrame en el mapa ", "ensename en el mapa "
    ]
    match_map_pref = None
    for pref in map_fly_prefixes:
        if text.startswith(normalize_text(pref)):
            match_map_pref = pref
            break
    if match_map_pref is not None:
        place = command[len(match_map_pref):].strip()
        if not place:
            return "Señor, ¿a qué lugar desea que le lleve?"
        from core.world_map import fly_to
        loc = fly_to(place)
        if loc:
            return f"Volando a {loc['name']}, señor."
        return f"Señor, no he podido localizar '{place}' en el mapa."
    # (excluir "mapa de calor"/"de red"/"de paquetes": son otras vistas, no el globo)
    _not_world = ("calor", "red", "paquete", "arquitectura")
    if not any(x in text for x in _not_world) and any(kw in text for kw in ["abre el mapa", "abre el globo", "muestra el mapa", "abrir el mapa", "abre el mundo"]):
        from core.world_map import open_map
        open_map()
        return "Abriendo el mapa mundial, señor."
    if not any(x in text for x in _not_world) and any(kw in text for kw in ["cierra el mapa", "cierra el globo", "oculta el mapa", "cerrar el mapa", "cierra el mundo"]):
        from core.world_map import close_map
        close_map()
        return "Mapa cerrado, señor."


    # --- Comando rápido: Protocolo Blackout (modo noche) ---
    if any(kw in text for kw in ["desactiva el modo noche", "desactivar el modo noche", "desactiva modo noche",
                                 "quita el modo noche", "modo dia", "modo día", "sal del modo noche",
                                 "desactiva el protocolo blackout", "fin del protocolo blackout"]):
        from core.night_mode import set_blackout
        set_blackout(False)
        return "Protocolo Blackout desactivado, señor. Restaurando iluminación normal."
    if any(kw in text for kw in ["activa el modo noche", "activar el modo noche", "modo noche", "modo nocturno",
                                 "protocolo blackout", "activa el protocolo blackout"]):
        from core.night_mode import set_blackout
        set_blackout(True)
        return "Protocolo Blackout activado, señor. Atenuando la interfaz."


    # --- Comando rápido: HUD Overlay flotante ---
    if any(kw in text for kw in ["cierra el hud", "oculta el hud", "cerrar el hud", "quita el hud",
                                 "cierra el overlay", "oculta el overlay"]):
        from core.hud_overlay import stop_hud_overlay
        stop_hud_overlay()
        return "HUD desactivado, señor."
    if any(kw in text for kw in ["abre el hud", "muestra el hud", "activa el hud", "abrir el hud",
                                 "abre el overlay", "muestra el overlay", "hud flotante"]):
        from core.hud_overlay import start_hud_overlay
        start_hud_overlay(force=True)
        return "HUD flotante desplegado, señor."


    # --- Comando rápido: mapa de calor térmico 3D ---
    if any(kw in text for kw in ["cierra la telemetria termica", "cierra el mapa de calor",
                                 "oculta el mapa de calor", "cierra la termica", "cerrar el mapa de calor"]):
        from core.thermal_telemetry import close_thermal
        close_thermal()
        return "Telemetría térmica cerrada, señor."
    if any(kw in text for kw in ["abre la telemetria termica", "telemetria termica", "mapa de calor",
                                 "abre el mapa de calor", "muestra el mapa de calor", "mapa termico",
                                 "temperatura del hardware", "telemetria del hardware"]):
        from core.thermal_telemetry import open_thermal
        open_thermal()
        return "Telemetría térmica activa, señor. Proyectando el mapa de calor del hardware."


    # --- Comando rápido: Protocolo "Mente Colmena" (consenso multi-modelo) ---
    hive_prefixes = ["mente colmena", "consulta a varios modelos", "pregunta a todos los modelos",
                     "consenso de modelos", "pregunta al enjambre", "consulta multiple",
                     "consulta al enjambre"]
    for pref in hive_prefixes:
        if text.startswith(normalize_text(pref)):
            question = command[len(pref):].lstrip(" ,:.¿?").strip()
            if not question:
                return "¿Qué desea que consulte a los núcleos de razonamiento, señor?"
            from core.hive_mind import consult
            return consult(question)


    # --- Comando rápido: Protocolo "Casa Llena" (multi-agente) ---
    hp_prefixes = ["protocolo casa llena", "casa llena", "reune al equipo", "reúne al equipo",
                   "despliega el equipo", "convoca al equipo", "que lo vea el equipo"]
    for pref in hp_prefixes:
        if text.startswith(normalize_text(pref)):
            objective = command[len(pref):].lstrip(" ,:.¿?").strip()
            if not objective:
                return "¿Cuál es el objetivo para el equipo, señor?"
            from core.house_party import run_house_party
            return run_house_party(objective)


    # --- Comando rápido: Protocolo Babel (traducción) ---
    if text.startswith("traduce") or text.startswith("traducir") or "como se dice" in text:
        from core.babel import parse_translate_command, translate
        target, payload = parse_translate_command(command)
        if not payload:
            return "¿Qué desea que traduzca, señor?"
        result = translate(payload, target)
        tr = result.get("translation")
        if not tr:
            return "No he podido traducir eso, señor."
        return f"En {result['target_language']}: {tr}"


    # --- Comando rápido: Arranque automático con Windows ---
    if any(kw in text for kw in ["desactiva el arranque automatico", "quita el arranque automatico",
                                 "no arranques con windows", "desactivar autoarranque",
                                 "quitar el arranque automatico"]):
        from core.autostart import disable_autostart
        return ("Arranque automático desactivado, señor." if disable_autostart()
                else "No he podido desactivar el arranque automático, señor.")
    if any(kw in text for kw in ["activa el arranque automatico", "arranca con windows",
                                 "arranca con el pc", "activar autoarranque", "activar el arranque automatico"]):
        from core.autostart import enable_autostart
        return ("Arranque automático activado, señor. Me presentaré al encender el equipo."
                if enable_autostart() else "No he podido activar el arranque automático, señor.")
    if any(kw in text for kw in ["arrancas con el pc", "esta activo el arranque automatico",
                                 "arranque automatico activo", "arrancas con windows"]):
        from core.autostart import is_autostart_enabled
        return ("Sí, señor; arrancaré con Windows." if is_autostart_enabled()
                else "No, señor; no estoy configurado para arrancar con Windows.")


    # --- Comando rápido: Resumen de GitHub ---
    if any(kw in text for kw in ["resumen de github", "parte de github", "estado de github",
                                 "como esta github", "que hay en github", "pull requests pendientes",
                                 "estado de los pull requests"]):
        from core.github_report import get_github_summary
        return get_github_summary()


    # --- Comando rápido: prueba del anunciador de notificaciones ---
    if any(kw in text for kw in ["notificacion de prueba", "simula una notificacion",
                                 "prueba de notificacion", "anuncio de prueba"]):
        from core.announcer import announce
        return announce("Sistema", kind="alert", priority="high", speak=False) or \
            "El anunciador está desactivado, señor."


    # --- Comando rápido: Evaluación de Amenaza Narrada ---
    if any(kw in text for kw in ["analisis de riesgo", "probabilidad de exito", "evaluacion de amenaza",
                                 "evalua la situacion", "evalua el riesgo", "evalua los riesgos"]):
        from core.threat_assessment import get_assessment
        return get_assessment()
    if text.startswith("evalua "):
        action = command[len("evalua "):].strip()
        from core.threat_assessment import get_assessment
        return get_assessment(action or None)


    # --- Comando rápido: Informe de Daños (Damage Report) ---
    if any(kw in text for kw in ["informe de danos", "parte de danos", "damage report",
                                 "estado de los sistemas", "diagnostico de sistemas",
                                 "como estan los sistemas", "informe de sistemas"]):
        from core.damage_report import get_damage_report
        return get_damage_report()


    # --- Comando rápido: "¿Esto es seguro?" (análisis de comandos) ---
    safety_prefixes = ["es seguro ejecutar ", "es seguro este comando ", "es seguro el comando ",
                       "es seguro ", "es peligroso ", "analiza el comando ", "analiza este comando ",
                       "puedo ejecutar ", "es arriesgado "]
    for pref in safety_prefixes:
        if text.startswith(normalize_text(pref)):
            cmd = command[len(pref):].strip().strip("'\"")
            if not cmd:
                return "¿Qué comando desea que analice, señor?"
            from core.command_safety import format_for_voice
            return format_for_voice(cmd)


    # --- Comando rápido: Medidor de Sarcasmo ---
    if "sarcasmo" in text or "socarron" in text or "modo formal" in text or "ponte serio" in text:
        from core.personality import get_sarcasm_level, set_sarcasm_level, adjust_sarcasm
        if any(kw in text for kw in ["cuanto", "que nivel", "nivel actual", "como esta", "que sarcasmo"]) and \
                not any(kw in text for kw in ["sube", "baja", "pon", "fija"]):
            return f"Mi medidor de sarcasmo está en {get_sarcasm_level()} sobre 10, señor."
        m = re.search(r"\b(10|\d)\b", text)
        if any(kw in text for kw in ["maximo sarcasmo", "sarcasmo maximo", "modo socarron", "modo descarado", "a tope"]):
            lvl = set_sarcasm_level(10)
        elif any(kw in text for kw in ["modo formal", "sin sarcasmo", "cero sarcasmo", "nada de sarcasmo", "ponte serio"]):
            lvl = set_sarcasm_level(0)
        elif any(kw in text for kw in ["sube", "mas sarcasmo", "aumenta", "incrementa"]):
            lvl = adjust_sarcasm(2)
        elif any(kw in text for kw in ["baja", "menos sarcasmo", "reduce", "disminuye"]):
            lvl = adjust_sarcasm(-2)
        elif m is not None:
            lvl = set_sarcasm_level(int(m.group(1)))
        else:
            return (f"Mi medidor de sarcasmo está en {get_sarcasm_level()} sobre 10, señor. "
                    "Puede decir 'sube el sarcasmo' o 'nivel de sarcasmo 7'.")
        return f"Medidor de sarcasmo ajustado a {lvl} sobre 10, señor."


    # --- Comando rápido: Protocolo "Mark II" (auto-mejora supervisada) ---
    mk_prefixes = ["protocolo mark dos", "protocolo mark ii", "mark dos", "automejorate",
                   "auto mejorate", "automejora", "auto mejora"]
    for pref in mk_prefixes:
        if text.startswith(normalize_text(pref)):
            rest = command[len(pref):].lstrip(" ,:.").strip()
            if not rest:
                return ("Indique el fichero y la mejora, señor. Por ejemplo: "
                        "'protocolo mark dos core/blackout.py: añade validación de la hora'.")
            if ":" in rest:
                target, instruction = rest.split(":", 1)
            else:
                bits = rest.split(None, 1)
                target, instruction = bits[0], (bits[1] if len(bits) > 1 else "")
            target, instruction = target.strip(), instruction.strip()
            if not instruction:
                return "¿Qué mejora desea para ese fichero, señor?"
            from core.drones import launch_drone
            from core.mark_ii import run_mark_ii

            def _markii_mission(t=target, i=instruction):
                res = run_mark_ii(t, i)
                try:
                    from tools.voice import speak
                    speak(res, disable_vad=True)
                except Exception:
                    pass
                return res

            launch_drone("mark_ii", label=f"Mark II: {target}", fn=_markii_mission)
            return (f"Protocolo Mark II en marcha sobre {target}, señor. Trabajaré en una rama "
                    "aislada, validaré con las pruebas y le avisaré con el resultado.")


    # --- Comando rápido: Iron Legion (drones) ---
    if any(kw in text for kw in ["estado de los drones", "estado del enjambre", "que drones",
                                 "drones activos", "como van los drones"]):
        from core.drones import format_drones
        return format_drones()
    if any(kw in text for kw in ["limpia los drones", "retira los drones", "recoge los drones",
                                 "limpiar drones"]):
        from core.drones import clear_finished
        n = clear_finished()
        return f"Retirados {n} drones del registro, señor."
    if any(kw in text for kw in ["lanza un dron", "despliega un dron", "envia un dron",
                                 "lanzar dron", "despliega dron", "manda un dron"]):
        from core.drones import register_builtin_missions, launch_drone, list_missions
        register_builtin_missions()
        mission = None
        if any(k in text for k in ["test", "prueba"]):
            mission = "tests"
        elif any(k in text for k in ["dependencia", "auditor"]):
            mission = "dependencias"
        elif any(k in text for k in ["limpieza", "limpiar", "mantenimiento", "logs"]):
            mission = "limpieza"
        if mission is None:
            opciones = ", ".join(list_missions().values())
            return f"¿Qué misión, señor? Disponibles: {opciones}."
        d = launch_drone(mission)
        return f"Dron {d['short']} desplegado, señor. Misión: {d['name']}. Le avisaré al completarse."


    # --- Comando rápido: Base de errores recurrentes ---
    if any(kw in text for kw in ["errores recurrentes", "base de errores", "cuantos errores he visto",
                                 "mis errores frecuentes", "errores frecuentes", "memoria de errores"]):
        from core.error_kb import get_summary
        return get_summary()


    # --- Comando rápido: Rastreador de Productividad ---
    if any(kw in text for kw in ["cuanto he trabajado", "cuanto he currado", "resumen de productividad",
                                 "en que he trabajado", "tiempo por proyecto", "productividad de hoy",
                                 "mi productividad"]):
        from core.productivity import get_today_summary
        return get_today_summary()


    # --- Comando rápido: Protocolo "Hijo Pródigo" (ponme al día) ---
    if any(kw in text for kw in ["ponme al dia", "ponme al corriente", "que me he perdido",
                                 "protocolo hijo prodigo", "que ha pasado mientras no estaba",
                                 "que ha pasado en mi ausencia", "resumen de ausencia", "que me perdi"]):
        from core.prodigal import get_catchup
        return get_catchup()


    # --- Comando rápido: Anticipación ---
    if any(kw in text for kw in ["anticipa", "que suelo hacer", "que hago normalmente",
                                 "que sueles sugerir", "que me sugieres ahora", "que toca ahora"]):
        from core.anticipation import get_suggestions, _phrase
        sugg = get_suggestions(top_k=3)
        if not sugg:
            return "Aún no tengo suficientes patrones para anticiparme, señor. Deme algo más de tiempo observando sus rutinas."
        opciones = ", ".join(_phrase(s["action"]) for s in sugg)
        return f"A esta hora suele: {opciones}, señor. ¿Desea que me adelante?"


    # --- Comando rápido: Insight Proactivo ("Señor, detecto un patrón") ---
    if any(kw in text for kw in ["detecto un patron", "detecta un patron", "detectas algun patron",
                                 "algun patron", "que patron has detectado", "analiza mis habitos",
                                 "analiza mis patrones", "mis patrones", "insight proactivo"]):
        from core.insights import get_insights_report
        return get_insights_report()


    # --- Comando rápido: Memoria de Sesión ("¿de qué hemos hablado?") ---
    if any(kw in text for kw in ["de que hemos hablado", "que hemos hablado",
                                 "de que hablabamos", "de que estabamos hablando",
                                 "resumen de la conversacion", "que temas hemos tratado"]):
        from core.session_memory import session_summary
        return session_summary()


    # --- Comando rápido: Reanudar Contexto ("¿en qué estaba?") ---
    if any(kw in text for kw in ["en que estaba", "en que andaba", "donde lo deje",
                                 "donde lo dejamos", "retomamos", "retomar contexto",
                                 "que estaba haciendo"]):
        from core.resume_context import get_resume_context
        return get_resume_context()


    # --- Comando rápido: Explícame este módulo ---
    if any(kw in text for kw in ["explicame el modulo", "explica el modulo",
                                 "explicame este modulo", "explica este modulo",
                                 "explicame el fichero", "como funciona el modulo",
                                 "que hace el modulo"]):
        from core.module_explainer import explain_module
        return explain_module(command)


    # --- Comando rápido: Vigilancia Proactiva del Mundo (cripto/sismos) ---
    # Se evalúa ANTES que el Puesto de Vigilancia para que "vigila el bitcoin" /
    # "avísame de terremotos" no los capture la vigilancia de ficheros/procesos.
    if any(kw in text for kw in ["deja de vigilar el mundo", "deja de vigilar el bitcoin",
                                 "deja de vigilar la cripto", "deja de vigilar los terremotos"]):
        from core.world_watch import remove_world_watches
        n = remove_world_watches()
        return (f"He retirado {n} vigilancia(s) del mundo, señor." if n
                else "No vigilaba nada del mundo, señor.")
    if any(kw in text for kw in ["que vigilas del mundo", "que estas vigilando del mundo"]):
        from core.world_watch import format_watch_list, list_watches
        return format_watch_list(list_watches())
    if "vigila" in text or "avisame" in text or "vigilame" in text:
        from core.world_watch import start_watch_command
        _world_res = start_watch_command(command)
        if _world_res:  # None si no es un tema del mundo -> sigue con el Puesto de Vigilancia
            return _world_res


    # --- Comando rápido: Puesto de Vigilancia ("Jarvis, vigila esto") ---
    if any(kw in text for kw in ["deja de vigilar", "para de vigilar", "deja de observar"]):
        from core.watchpost import remove_watch
        n = remove_watch(command.split("vigilar", 1)[-1] if "vigilar" in command else command)
        return (f"He retirado {n} vigilancia(s), señor." if n else
                "No tenía nada vigilado con esa descripción, señor.")
    if any(kw in text for kw in ["que estas vigilando", "que vigilas", "vigilancias activas",
                                 "que tienes vigilado"]):
        from core.watchpost import format_watch_list, list_watches
        return format_watch_list(list_watches())
    if any(kw in text for kw in ["vigila el", "vigila la", "vigila este", "vigila esto",
                                 "ponme a vigilar", "vigilar el", "mantente vigilando"]):
        from core.watchpost import start_watch_command
        return start_watch_command(command)


    # --- Comando rápido: Análisis con Retícula ("escanea esto") ---
    if any(kw in text for kw in ["escanea esto", "escanea la pantalla", "escanea el escritorio",
                                 "analisis con reticula", "analiza la pantalla con reticula",
                                 "escaneo de combate", "escanea la imagen"]):
        from core.reticle_scan import scan_screen
        return scan_screen()


    # --- Comando rápido: Informe de Situación (Cerebro de Estado Central) ---
    if any(kw in text for kw in ["informe de situacion", "cual es la situacion",
                                 "estado general", "estado global", "situacion general",
                                 "como esta todo", "dame el parte"]):
        from core.world_model import get_situation_report
        return get_situation_report()


    # --- Comando rápido: Telemetría de Herramientas (coraza universal) ---
    if any(kw in text for kw in ["informe de herramientas", "telemetria de herramientas",
                                 "estado de las tools", "telemetria de tools",
                                 "como van las herramientas", "salud de las herramientas"]):
        from core.tool_armor import get_tool_report
        return get_tool_report()


    # --- Comando rápido: Motor de Fusión de Fuentes ("lo sabe todo") ---
    _fusion_prefixes = ["fusiona ", "fusion de fuentes ", "analiza a fondo ",
                        "con todo lo que sabes ", "dame tu analisis sobre ",
                        "cruza tus fuentes sobre "]
    for _pref in _fusion_prefixes:
        if _pref in text:
            pregunta = text.split(_pref, 1)[1].strip()
            from core.fusion import fuse
            return fuse(pregunta)


    # --- Comando rápido: Datos del Mundo en Vivo ---
    # Bolsa primero: una acción concreta o mención al mercado (antes que cripto,
    # porque "cotización de" es genérico).
    from core.live_data import ticker_in_query as _ticker_in_query
    _stock_symbol = _ticker_in_query(command)
    if _stock_symbol or any(kw in text for kw in ["como va la bolsa", "como va el mercado",
                                                  "precio de la accion", "cotizacion de la bolsa"]):
        from core.live_data import get_stock
        out = get_stock(_stock_symbol or "^spx")
        if out:
            return f"Cotización, señor: {out}."
        return "No he podido consultar la cotización, señor."
    if any(kw in text for kw in ["precio del bitcoin", "precio de bitcoin",
                                 "precio de ethereum", "como va el bitcoin", "como va el cripto",
                                 "precio de la cripto", "cotizacion cripto"]):
        from core.live_data import get_crypto, coins_in_query
        out = get_crypto(coins_in_query(command))
        return f"Cotizaciones, señor: {out}." if out else "No he podido consultar las cotizaciones, señor."
    if any(kw in text for kw in ["ultimos terremotos", "ultimos sismos", "terremotos recientes",
                                 "sismos recientes", "ha habido terremotos", "actividad sismica"]):
        from core.live_data import get_earthquakes
        out = get_earthquakes()
        return f"{out}, señor." if out else "No hay datos de sismos significativos ahora mismo, señor."
    if any(kw in text for kw in ["noticias de tecnologia", "hacker news", "noticias tech",
                                 "que se cuece en tecnologia", "portada de hacker news"]):
        from core.live_data import get_tech_news
        out = get_tech_news()
        return f"{out}, señor." if out else "No he podido consultar las noticias, señor."


    # --- Comando rápido: Investigador Autónomo Profundo ---
    _research_prefixes = ["investiga a fondo ", "investigacion profunda sobre ",
                         "haz una investigacion sobre ", "haz una investigacion de ",
                         "investiga sobre ", "investiga "]
    for _pref in _research_prefixes:
        if _pref in text:
            tema = text.split(_pref, 1)[1].strip()
            from core.researcher import research
            return research(tema)


    # --- Comando rápido: Iniciativa Ejecutora (nivel de autonomía) ---
    if any(kw in text for kw in ["toma la iniciativa", "modo autonomo", "modo proactivo",
                                 "actua por tu cuenta", "autonomia total"]):
        os.environ["JARVIS_INITIATIVE_LEVEL"] = "act"
        from core.initiative import start_initiative_daemon
        start_initiative_daemon()
        return "Iniciativa ejecutora activada, señor. Actuaré por mi cuenta en lo de bajo riesgo y le avisaré del resto."
    if any(kw in text for kw in ["solo avisame", "modo aviso", "solo notifica", "no actues solo"]):
        os.environ["JARVIS_INITIATIVE_LEVEL"] = "notify"
        from core.initiative import start_initiative_daemon
        start_initiative_daemon()
        return "De acuerdo, señor. Le avisaré de los cambios, pero no actuaré sin su visto bueno."
    if any(kw in text for kw in ["desactiva la iniciativa", "deja de actuar por tu cuenta",
                                 "no tomes la iniciativa"]):
        os.environ["JARVIS_INITIATIVE_LEVEL"] = "off"
        from core.initiative import stop_initiative_daemon
        stop_initiative_daemon()
        return "Iniciativa desactivada, señor. Esperaré sus órdenes."


    # --- Comando rápido: Packet Map 3D (telemetría de red) ---
    if any(kw in text for kw in ["cierra el mapa de paquetes", "cierra la telemetria de red",
                                 "cierra el packet map", "oculta el mapa de red", "cierra el mapa de red"]):
        from core.packet_map import close_packet_map
        close_packet_map()
        return "Telemetría de red cerrada, señor."
    if any(kw in text for kw in ["mapa de paquetes", "packet map", "telemetria de red",
                                 "mapa de red", "conexiones de red", "trafico de red",
                                 "muestra la red", "telemetria de conexiones"]):
        from core.packet_map import open_packet_map
        open_packet_map()
        return "Telemetría de red activa, señor. Proyectando el mapa de paquetes."


    # --- Comando rápido: Sala de Hologramas (arquitectura 3D) ---
    if any(kw in text for kw in ["cierra la sala de hologramas", "cierra la holomesa", "cierra la arquitectura",
                                 "oculta la arquitectura", "cierra los hologramas"]):
        from core.architecture_graph import close_holograph
        close_holograph()
        return "Sala de hologramas cerrada, señor."
    if any(kw in text for kw in ["sala de hologramas", "abre la holomesa", "muestra la arquitectura",
                                 "mapa de arquitectura", "arquitectura del proyecto", "explorador de arquitectura",
                                 "proyecta la arquitectura"]):
        from core.architecture_graph import open_holograph
        open_holograph()
        return "Proyectando la arquitectura del proyecto, señor. Sala de hologramas activa."


    # --- Comando rápido: Protocolo de Enfoque "Verónica" ---
    if any(kw in text for kw in ["desactiva el protocolo veronica", "fin del protocolo veronica",
                                 "desactiva el modo enfoque", "termina el enfoque", "fin del enfoque",
                                 "sal del modo enfoque", "para el enfoque", "desactiva veronica"]):
        from core.focus_mode import stop_focus
        stop_focus()
        return "Protocolo Verónica desactivado, señor. Distractores restaurados."
    if any(kw in text for kw in ["activa el protocolo veronica", "protocolo veronica", "modo enfoque",
                                 "modo concentracion", "activa el modo enfoque", "activa veronica"]):
        from core.focus_mode import start_focus
        m = re.search(r"(\d+)\s*minuto", text)
        minutes = int(m.group(1)) if m else None
        eff = start_focus(minutes)
        return f"Protocolo Verónica iniciado, señor. Concentración durante {eff} minutos. Silenciando distractores."


    # --- Comando rápido: conciencia del proyecto activo ---
    if any(kw in text for kw in ["en que proyecto estoy", "estado del proyecto", "estado del repositorio",
                                 "estado de git", "en que rama estoy", "que rama es", "que proyecto es este"]):
        from core.project_awareness import get_active_project
        s = get_active_project()
        if not s["is_repo"]:
            return "Señor, no detecto ningún repositorio git activo."
        resp = f"Está en el proyecto {s['repo_name']}, señor"
        if s["branch"]:
            resp += f", rama {s['branch']}"
        resp += ". "
        if s["dirty_count"]:
            plural = "s" if s["dirty_count"] != 1 else ""
            resp += f"Tiene {s['dirty_count']} archivo{plural} con cambios sin confirmar."
        else:
            resp += "El repositorio está limpio."
        if s["last_commit"]:
            resp += f" Último commit: {s['last_commit']}."
        return resp


    # --- Comando rápido: salud de las dependencias ---
    dep_health_keywords = [
        "salud de las dependencias", "salud de dependencias",
        "estado de las dependencias", "estado de dependencias",
        "dependencias desactualizadas"
    ]
    if any(kw in text for kw in dep_health_keywords):
        import json as _json
        from core.dependency_health import REPORT_FILE
        if not REPORT_FILE.exists():
            return "Señor, aún no he realizado la auditoría de salud de dependencias."
        try:
            report = _json.loads(REPORT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return "Señor, no pude leer el informe de dependencias."
        n_out = len(report.get("outdated", []))
        n_stale = len(report.get("stale", []))
        if n_out == 0 and n_stale == 0:
            return "Señor, todas las dependencias están al día y con mantenimiento reciente."
        return (
            f"Señor, informe de dependencias: {n_out} desactualizada(s) y "
            f"{n_stale} sin mantenimiento reciente. Le sugiero revisarlas en el panel."
        )


    # --- Comando rápido: auditoría del entorno (.env Manager) ---
    env_audit_keywords = [
        "audita el entorno", "auditoria del entorno", "auditoria de entorno",
        "revisa el entorno", "revisa las variables de entorno",
        "audita las variables de entorno", "revisa la configuracion del entorno"
    ]
    if any(kw in text for kw in env_audit_keywords):
        from core.env_manager import audit_env
        try:
            r = audit_env()
        except Exception as e:
            return f"Lo siento, señor, no pude auditar el entorno: {e}"
        if r["status"] == "healthy":
            return "El entorno está en orden, señor. Todas las variables requeridas están configuradas."
        parts = ["Señor, auditoría del entorno:"]
        if r["missing_required"]:
            parts.append(
                f"Faltan {len(r['missing_required'])} variable(s) requerida(s): "
                f"{', '.join(r['missing_required'])}."
            )
        if r["empty"]:
            parts.append(
                f"{len(r['empty'])} referenciada(s) están vacías: {', '.join(r['empty'])}."
            )
        if r["unused"]:
            parts.append(
                f"{len(r['unused'])} en el punto env sin usar: {', '.join(r['unused'])}."
            )
        return " ".join(parts)


    # --- Comando rápido: resumen del día / nocturno (Daily Digest) ---
    digest_keywords = [
        "resumen del dia", "resumen de hoy", "que he hecho hoy",
        "dame el resumen del dia", "informe del dia", "resumen diario",
        "resumen nocturno", "como ha ido el dia"
    ]
    if any(kw in text for kw in digest_keywords):
        from core.daily_digest import generate_daily_digest
        try:
            return generate_daily_digest()
        except Exception as e:
            return f"Lo siento, señor, no pude generar el resumen del día: {e}"


    # --- Comando rápido: consultar el modelo activo ---
    current_model_keywords = [
        "que modelo estas usando", "que modelo usas", "modelo activo",
        "cual es el modelo actual", "que modelo tienes activo"
    ]
    if any(kw in text for kw in current_model_keywords):
        from core.agent_manager import get_active_model
        return f"Señor, el modelo activo actualmente es {get_active_model()}."

    # --- Comando rápido: cambiar de modelo activo ---
    change_model_prefixes = [
        "cambia al modelo ", "cambia a modelo ", "cambia de modelo a ",
        "usa el modelo ", "activa el modelo "
    ]
    match_model_pref = None
    for pref in change_model_prefixes:
        if text.startswith(normalize_text(pref)):
            match_model_pref = pref
            break
    if match_model_pref is not None:
        alias = text[len(normalize_text(match_model_pref)):].strip()
        from core.model_config import resolve_model_alias, available_aliases
        model_id = resolve_model_alias(alias)
        if not model_id:
            opciones = ", ".join(available_aliases())
            return (
                f"Señor, no reconozco el modelo '{alias}'. "
                f"Puede elegir entre: {opciones}."
            )
        try:
            from core.agent_manager import set_active_model
            set_active_model(model_id)
            return f"Entendido, señor. Modelo activo cambiado a {model_id}."
        except Exception as e:
            return f"Lo siento, señor, no pude cambiar el modelo: {e}"


    # --- Comandos rápidos: Bandeja de entrada (Inbox) ---
    # 1. Apuntar una nota
    inbox_add_prefixes = [
        "apunta en la bandeja ", "apunta en mi bandeja ", "anade a la bandeja ",
        "anota en la bandeja ", "guarda en la bandeja ", "apunta en bandeja de entrada "
    ]
    match_inbox_pref = None
    for pref in inbox_add_prefixes:
        if text.startswith(normalize_text(pref)):
            match_inbox_pref = pref
            break
    if match_inbox_pref is not None:
        note = command[len(match_inbox_pref):].strip()
        if not note:
            return "Señor, ¿qué desea que apunte en la bandeja?"
        from core.inbox import add_inbox_item
        if add_inbox_item(note):
            return f"Anotado en la bandeja, señor: {note}."
        return "Lo siento, señor, no pude guardar la nota en la bandeja."

    # 2. Consultar la bandeja
    inbox_list_keywords = [
        "que hay en mi bandeja", "que hay en la bandeja", "muestra mi bandeja",
        "muestrame la bandeja", "lista la bandeja", "que tengo en la bandeja"
    ]
    if any(kw in text for kw in inbox_list_keywords):
        from core.inbox import get_inbox_items
        items = get_inbox_items()
        if not items:
            return "Su bandeja de entrada está vacía, señor."
        formatted = "\n".join(f"  {idx}. {it['content']}" for idx, it in enumerate(items, 1))
        return f"Señor, tiene {len(items)} nota(s) en la bandeja:\n{formatted}"

    # 3. Vaciar la bandeja
    inbox_clear_keywords = [
        "vacia la bandeja", "limpia la bandeja", "vacia mi bandeja", "borra la bandeja"
    ]
    if any(kw in text for kw in inbox_clear_keywords):
        from core.inbox import clear_inbox
        removed = clear_inbox()
        if removed > 0:
            return f"Entendido, señor. He vaciado la bandeja ({removed} nota(s) eliminada(s))."
        return "Su bandeja ya estaba vacía, señor."


    # --- Comandos rápidos: Modo Gaming / Bajo Consumo ---
    # Desactivar primero, para que no colisione con la keyword "modo gaming".
    game_off_keywords = [
        "desactiva modo gaming", "desactivar modo gaming", "desactiva el modo gaming",
        "sal del modo gaming", "salir del modo gaming", "modo normal"
    ]
    if any(kw in text for kw in game_off_keywords):
        from core.game_mode import exit_game_mode
        result = exit_game_mode()
        if not result["was_active"]:
            return "Señor, el modo gaming no estaba activo."
        resumed = result["resumed"]
        if resumed:
            return f"Modo gaming desactivado, señor. He reanudado {len(resumed)} servicios en segundo plano."
        return "Modo gaming desactivado, señor."

    game_on_keywords = [
        "activa modo gaming", "activar modo gaming", "activa el modo gaming",
        "entra en modo gaming", "modo gaming", "modo de bajo consumo"
    ]
    if any(kw in text for kw in game_on_keywords):
        from core.game_mode import enter_game_mode
        result = enter_game_mode()
        if result["already_active"]:
            return "Señor, el modo gaming ya estaba activo."
        paused = result["paused"]
        if paused:
            pretty = ", ".join(p.replace("_", " ") for p in paused)
            return (
                f"Modo gaming activado, señor. He pausado {len(paused)} servicios "
                f"para liberar recursos: {pretty}."
            )
        return "Modo gaming activado, señor. No había servicios pesados que pausar."


    # --- Comandos rápidos del Planificador de Tareas ---
    # 1. Crear recordatorio
    match_reminder = re.search(r"\b(en|cada)\s+(\d+)\s+(segundo|segundos|seg|s|minuto|minutos|min|m|hora|horas|h)\b", text)
    if match_reminder and (text.startswith("recuerdame ") or text.startswith("recuerda ")):
        prefix_len = 11 if text.startswith("recuerdame ") else 9
        match_start = match_reminder.start()
        reminder_text = command[prefix_len:match_start].strip()
        
        # Limpiar conectores iniciales comunes ("que", "a", "de")
        reminder_norm = normalize_text(reminder_text)
        if reminder_norm.startswith("que "):
            reminder_text = reminder_text[4:].strip()
        elif reminder_norm.startswith("de "):
            reminder_text = reminder_text[3:].strip()
        elif reminder_norm.startswith("a "):
            reminder_text = reminder_text[2:].strip()
            
        qty = int(match_reminder.group(2))
        unit = match_reminder.group(3)
        multiplier = 1
        if "min" in unit or unit == "m":
            multiplier = 60
        elif "hor" in unit or unit == "h":
            multiplier = 3600
            
        delay_seconds = qty * multiplier
        is_periodic = (match_reminder.group(1) == "cada")
        interval_seconds = delay_seconds if is_periodic else 0
        
        if reminder_text:
            import uuid
            # Generar un ID único amigable para la tarea
            safe_text = re.sub(r"[^a-zA-Z0-9_]", "", normalize_text(reminder_text))[:20]
            task_name = f"reminder_{safe_text}_{uuid.uuid4().hex[:6]}"
            
            from core.scheduler import add_reminder
            success = add_reminder(task_name, reminder_text, delay_seconds, interval_seconds)
            if success:
                period_str = f"cada {qty} {unit}" if is_periodic else f"en {qty} {unit}"
                return f"Entendido, señor. He programado el recordatorio: '{reminder_text}' para ejecutarse {period_str}."
            else:
                return "Lo siento, señor. Hubo un problema al guardar el recordatorio."

    # 2. Listar recordatorios
    list_keywords = ["lista las tareas", "que recordatorios tienes", "dime mis tareas", "dime mis recordatorios", "ver recordatorios"]
    if any(kw in text for kw in list_keywords):
        from core.scheduler import get_active_tasks
        tasks = get_active_tasks()
        if not tasks:
            return "No tiene ningún recordatorio programado, señor."
            
        formatted = []
        for t in tasks:
            try:
                # next_run es una fecha en formato ISO UTC. La mostramos amigable.
                dt = datetime.fromisoformat(t["next_run"])
                # Local time formatting
                time_str = dt.astimezone().strftime("%d/%m/%Y a las %H:%M:%S")
            except Exception:
                time_str = t["next_run"]
                
            period_str = f" (Cada {t['interval_seconds']}s)" if t["interval_seconds"] > 0 else ""
            formatted.append(f"- '{t['target']}' (ID: {t['name']}) -> Próxima: {time_str}{period_str}")
        return "Señor, estas son las tareas programadas activas:\n" + "\n".join(formatted)

    # 3. Cancelar recordatorio
    cancel_pref = None
    for pref in ["cancela la tarea ", "elimina el recordatorio ", "olvida el recordatorio ", "borra el recordatorio ", "cancela el recordatorio "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            cancel_pref = pref
            break
    if cancel_pref is not None:
        task_query = command[len(cancel_pref):].strip()
        if task_query:
            from core.scheduler import cancel_task, get_active_tasks
            # Buscar por ID exacto primero
            deleted = cancel_task(task_query)
            if deleted:
                return f"Entendido, señor. He cancelado y eliminado la tarea programada '{task_query}'."
                
            # Si no coincide el ID exacto, buscar coincidencias en el ID o en el contenido (target)
            tasks = get_active_tasks()
            matched_tasks = [t for t in tasks if task_query.lower() in t["name"].lower() or task_query.lower() in t["target"].lower()]
            if len(matched_tasks) == 1:
                cancel_task(matched_tasks[0]["name"])
                return f"Entendido, señor. He cancelado el recordatorio '{matched_tasks[0]['target']}'."
            elif len(matched_tasks) > 1:
                return f"Señor, encontré múltiples recordatorios que coinciden con '{task_query}'. Por favor, especifique el ID exacto."
                
            return f"No encontré ningún recordatorio o tarea programada que coincida con '{task_query}', señor."
        return "Señor, ¿qué recordatorio desea que cancele?"

    # --- Comandos del Monitor de URLs (Fase 2) ---
    # 1. Crear monitor de URL
    match_monitor = re.search(r"\b(monitorea|vigila)\s+(\S+)\s+cada\s+(\d+)\s+(minuto|minutos|min|m|hora|horas|h)\b", text)
    if match_monitor:
        # Usar la posición del match para extraer la URL del comando original y preservar mayúsculas/minúsculas
        start, end = match_monitor.span(2)
        url_text = command[start:end].strip()
        if not url_text.startswith(("http://", "https://")):
            url_text = "https://" + url_text
            
        qty = int(match_monitor.group(3))
        unit = match_monitor.group(4)
        multiplier = 60
        if "hor" in unit or unit == "h":
            multiplier = 3600
        interval_seconds = qty * multiplier
        
        import uuid
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url_text)
            host_clean = re.sub(r"[^a-zA-Z0-9_]", "", parsed.netloc.replace(".", "_"))[:20]
        except Exception:
            host_clean = "site"
        task_name = f"monitor_{host_clean}_{uuid.uuid4().hex[:6]}"
        
        from core.scheduler import add_url_monitor
        res_msg = add_url_monitor(task_name, url_text, interval_seconds, allow_local_network=True)
        return res_msg

    # 2. Reactivar monitor de URL (limpiar alerta)
    reactivate_pref = None
    for pref in ["reactiva el monitoreo de ", "reactiva el monitor de ", "limpia la alerta de ", "reactivar monitoreo de "]:
        norm_pref = normalize_text(pref)
        if text.startswith(norm_pref):
            reactivate_pref = pref
            break
            
    if reactivate_pref is not None:
        target_query = command[len(reactivate_pref):].strip()
        if target_query:
            from core.scheduler import reactivate_url_monitor
            res = reactivate_url_monitor(target_query)
            if res.startswith("Éxito:"):
                return f"Entendido, señor. {res[7:]}"
            else:
                return f"Señor, {res}"
        return "Señor, ¿qué monitoreo de URL desea reactivar?"

    # --- Comandos locales estándar ---
    websites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "chatgpt": "https://chatgpt.com",
        "whatsapp": "https://web.whatsapp.com",
    }

    apps = {
        "calculadora": "calc",
        "bloc de notas": "notepad",
        "notepad": "notepad",
        "explorador": "explorer",
        "archivos": "explorer",
        "chrome": "chrome",
        "spotify": "spotify",
    }

    for name, url in websites.items():
        if f"abre {name}" in text or f"abrir {name}" in text:
            open_website.invoke({"url": url})
            _record_anticipation(f"web:{name}")
            return f"Abriendo {name}, señor."

    for name, executable in apps.items():
        if f"abre {name}" in text or f"abrir {name}" in text:
            open_windows_app.invoke({"app_executable": executable})
            _record_anticipation(f"app:{name}")
            return f"Abriendo {name}, señor."

    if "que hora es" in text or "dime la hora" in text:
        res = get_time.invoke({})
        # Extraer la hora en formato HH:MM
        match = re.search(r"(\d{2}:\d{2})", res)
        if match:
            return f"Son las {match.group(1)}, señor."
        now = datetime.now()
        return f"Son las {now.hour:02d}:{now.minute:02d}, señor."

    if "que dia es" in text or "fecha de hoy" in text or "que fecha es" in text:
        res = get_date.invoke({})
        return f"Hoy es {res}."

    # --- Comandos Rápidos del Asistente Git Inteligente ---
    # 1. Resumen de rama / branch
    branch_keywords = [
        "resumen de rama", "como esta mi rama", "estado de la rama", 
        "resumen de branch", "estado de branch", "resumen de git"
    ]
    if any(kw in text for kw in branch_keywords):
        from core.git_assistant import generate_branch_summary
        return generate_branch_summary()

    # 2. Generar mensaje de commit / proponer commit
    commit_keywords = [
        "genera commit", "haz commit", "crea un mensaje de commit", 
        "sugiere un commit", "genera un mensaje de commit", "crear commit",
        "crea mensaje de commit"
    ]
    if any(kw in text for kw in commit_keywords):
        from core.git_assistant import generate_commit_message
        commit_msg = generate_commit_message(staged=True)
        if commit_msg.startswith("No he detectado") or commit_msg.startswith("Error"):
            return commit_msg
        
        # Guardar en acciones pendientes para confirmación directa
        from core.pending_actions import save_pending_action
        save_pending_action("git_commit", {"message": commit_msg})
        
        return (
            f"Señor, he analizado los cambios en staging y le sugiero el siguiente mensaje de commit:\n\n"
            f"`{commit_msg}`\n\n"
            f"Para aplicarlo de inmediato, responda con 'confirma acción' o 'adelante'."
        )

    # 3. Generar changelog
    changelog_keywords = ["crea un changelog", "generar changelog", "crear changelog", "changelog de la rama"]
    if any(kw in text for kw in changelog_keywords):
        from core.git_assistant import generate_branch_changelog
        return generate_branch_changelog(compare_branch="main")

    return None
