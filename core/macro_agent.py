import os
import json
import logging
import time
from pathlib import Path
from core.llm_factory import get_llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
HISTORY_FILE = LOGS_DIR / "terminal_history.json"

def log_terminal_command(command: str) -> None:
    """Registra un comando ejecutado con éxito en el historial."""
    try:
        LOGS_DIR.mkdir(exist_ok=True)
        history = []
        if HISTORY_FILE.exists():
            try:
                history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
                
        # Limitar comando a string sin espacios iniciales/finales
        clean_cmd = command.strip()
        if not clean_cmd:
            return
            
        history.append({
            "command": clean_cmd,
            "timestamp": time.time()
        })
        
        # Mantener sólo los últimos 100 comandos
        history = history[-100:]
        
        HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logging.error(f"[Macro Agent] Error logging terminal command: {e}")

def analyze_repetitive_commands() -> dict:
    """
    Analiza de forma heurística el historial de comandos en busca de repeticiones y secuencias.
    """
    analysis = {
        "consecutive_repeats": {},
        "sequences": []
    }
    
    if not HISTORY_FILE.exists():
        return analysis
        
    try:
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return analysis
        
    commands = [h["command"] for h in history if "command" in h]
    if len(commands) < 2:
        return analysis
        
    # 1. Contar repeticiones consecutivas idénticas
    consec_count = 1
    last_cmd = commands[0]
    for cmd in commands[1:]:
        if cmd == last_cmd:
            consec_count += 1
        else:
            if consec_count >= 2:
                analysis["consecutive_repeats"][last_cmd] = analysis["consecutive_repeats"].get(last_cmd, 0) + consec_count
            consec_count = 1
            last_cmd = cmd
    if consec_count >= 2:
        analysis["consecutive_repeats"][last_cmd] = analysis["consecutive_repeats"].get(last_cmd, 0) + consec_count
        
    # 2. Buscar secuencias comunes de longitud 2 y 3 (sliding windows)
    seqs_of_2 = {}
    seqs_of_3 = {}
    
    for i in range(len(commands) - 1):
        pair = (commands[i], commands[i+1])
        # Omitir si son idénticas consecutivas (ya cubierto por el análisis anterior)
        if pair[0] == pair[1]:
            continue
        seqs_of_2[pair] = seqs_of_2.get(pair, 0) + 1
        
    for i in range(len(commands) - 2):
        triplet = (commands[i], commands[i+1], commands[i+2])
        if triplet[0] == triplet[1] or triplet[1] == triplet[2]:
            continue
        seqs_of_3[triplet] = seqs_of_3.get(triplet, 0) + 1
        
    # Filtrar secuencias que se repiten al menos 2 veces
    for seq, count in seqs_of_2.items():
        if count >= 2:
            analysis["sequences"].append({
                "sequence": list(seq),
                "count": count
            })
            
    for seq, count in seqs_of_3.items():
        if count >= 2:
            analysis["sequences"].append({
                "sequence": list(seq),
                "count": count
            })
            
    # Ordenar secuencias por frecuencia descendente
    analysis["sequences"].sort(key=lambda x: x["count"], reverse=True)
    return analysis

def generate_efficiency_report() -> str:
    """Genera un reporte completo de eficiencia y automatización consultando al LLM."""
    analysis = analyze_repetitive_commands()
    
    # Obtener el historial reciente para darle contexto al LLM
    recent_history = []
    if HISTORY_FILE.exists():
        try:
            recent_history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))[-40:]
            recent_history = [h["command"] for h in recent_history if "command" in h]
        except Exception:
            pass
            
    # Si no hay suficiente historial
    if not recent_history:
        return (
            "🟢 **Reporte del Analizador de Eficiencia de Jarvis**\n\n"
            "Señor, no dispongo de suficiente historial de comandos ejecutados con éxito para analizar. "
            "A medida que use la terminal (`run_terminal_command`), iré registrando su actividad y le sugeriré "
            "macros de automatización cuando detecte patrones repetitivos."
        )
        
    try:
        llm = get_llm()
        
        system_prompt = (
            "Eres el Macro Agente de Jarvis, un asistente de productividad que analiza el historial de comandos ejecutados por el desarrollador.\n"
            "Tu tarea es evaluar la eficiencia de su trabajo y proponer automatizaciones personalizadas (macros) en español.\n"
            "Pautas de respuesta:\n"
            "1. Presenta un breve análisis o diagnóstico del historial actual en un tono Stark (ingenioso y eficiente).\n"
            "2. Identifica si hay comandos repetidos o secuencias que podrían unificarse (como por ejemplo compilar y correr tests, o secuencias de git status/add/commit).\n"
            "3. Sugiere macros específicos que agrupen estas tareas recurrentes. Escribe el código exacto del script batch (.bat) propuesto para que el usuario pueda crearlo y ejecutarlo.\n"
            "4. Explica cómo puede crear el macro pidiéndote: 'crea el macro <nombre> con los comandos <cmd1>, <cmd2>...'\n"
            "5. Sé muy estructurado y usa formato Markdown claro."
        )
        
        user_prompt = (
            f"Historial de comandos exitosos recientes (últimos 40):\n{recent_history}\n\n"
            f"Análisis estadístico preliminar de repeticiones y secuencias:\n{json.dumps(analysis, indent=2)}\n\n"
            "Genera tu reporte de eficiencia y propuestas de macros de automatización en español:"
        )
        
        messages = [
            ("system", system_prompt),
            ("human", user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content if hasattr(response, 'content') else str(response)
        
        report = (
            "📊 **ANÁLISIS DE EFICIENCIA Y AUTOMATIZACIÓN DE JARVIS**\n\n"
            f"{content}"
        )
        return report
    except Exception as e:
        logging.error(f"[Macro Agent] Error generating LLM report: {e}")
        return f"❌ Error al consultar al Macro Agente para generar el reporte: {e}"
