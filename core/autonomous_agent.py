import os
import json
import re
import threading
import logging
from pathlib import Path
from core.llm_factory import get_llm
from tools.voice import speak
from gui.app import socketio

ACTIVE_PLAN_FILE = Path("logs/active_plan.json")

def generate_plan(goal: str) -> dict:
    """Invoca al LLM para estructurar un plan de pasos secuenciales para cumplir el objetivo."""
    llm = get_llm(temperature=0.1)
    prompt = f"""Eres el módulo de planificación del asistente Jarvis. Tu meta es estructurar un plan lógico y ordenado de pasos secuenciales (máximo 6 pasos) para que Jarvis ejecute de forma autónoma la siguiente solicitud del usuario:
Solicitud: "{goal}"

Debes devolver obligatoriamente tu respuesta como un JSON estrictamente estructurado con la estructura del ejemplo que tienes abajo. No agregues ninguna explicación, ni saludos, ni caracteres especiales fuera del bloque de código JSON:
{{
  "goal": "{goal}",
  "steps": [
    {{"id": 1, "description": "Paso 1: Buscar información sobre X en la web"}},
    {{"id": 2, "description": "Paso 2: Guardar los resultados en un reporte de texto"}}
  ]
}}
"""
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        
        # Limpiar posibles delimitadores markdown del JSON
        match = re.search(r"({.*})", text, re.DOTALL)
        if match:
            text = match.group(1)
            
        data = json.loads(text)
        
        # Inicializar estados de los pasos
        for step in data.get("steps", []):
            step["status"] = "pending"
            step["output"] = ""
            
        return data
    except Exception as e:
        logging.error(f"[Planner] Fallo al generar plan estructurado: {e}")
        # Plan de fallback en caso de error de parseo
        return {
            "goal": goal,
            "steps": [
                {"id": 1, "description": f"Ejecutar y resolver directamente: {goal}", "status": "pending", "output": ""}
            ]
        }

def start_autonomous_execution(goal: str):
    """Inicializa la planificación de la tarea y lanza su ejecución en segundo plano."""
    try:
        plan = generate_plan(goal)
        
        # Guardar en logs
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        ACTIVE_PLAN_FILE.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Avisar por voz y por websockets
        num_steps = len(plan["steps"])
        speak(f"Señor, he estructurado un plan de {num_steps} pasos para resolver la tarea de forma autónoma. Iniciando ejecución de inmediato.", disable_vad=True)
        
        # Enviar plan a la GUI
        socketio.emit('plan_update', plan)
        
        # Notificar por Telegram
        try:
            from core.telegram_bot import bot
            telegram_user_id = os.getenv("TELEGRAM_USER_ID")
            if bot and telegram_user_id:
                steps_txt = "\n".join([f"{s['id']}. {s['description']}" for s in plan['steps']])
                bot.send_message(
                    telegram_user_id,
                    f"🤖 <b>Jarvis Planificador</b>: He trazado un plan autónomo para:\n<i>{goal}</i>\n\n"
                    f"<b>Pasos a seguir:</b>\n{steps_txt}\n\n"
                    f"<i>Ejecutando en segundo plano...</i>",
                    parse_mode="HTML"
                )
        except Exception as te:
            logging.error(f"[Telegram] Error notificando plan: {te}")
            
        # Lanzar hilo secundario asíncrono
        thread = threading.Thread(target=_execute_plan_loop, args=(plan,), daemon=True)
        thread.start()
    except Exception as e:
        logging.error(f"[Planner] Error al arrancar la ejecución autónoma: {e}")

def _execute_plan_loop(plan: dict):
    from core.agent_manager import get_executor
    from gui.app import update_state
    
    steps = plan.get("steps", [])
    
    # Colocar a Jarvis en modo pensamiento activo
    update_state("thinking", transcript=f"Ejecutando tarea autónoma: {plan['goal']}")
    
    for step in steps:
        step["status"] = "in_progress"
        ACTIVE_PLAN_FILE.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        socketio.emit('plan_update', plan)
        
        logging.info(f"[Autónomo] Ejecutando Paso {step['id']}: {step['description']}")
        
        prompt_paso = f"""Estás resolviendo de forma autónoma el paso {step['id']} del plan general.
Paso a resolver: "{step['description']}"
Meta final del plan: "{plan['goal']}"

Por favor, utiliza las herramientas del sistema (búsqueda, lectura/escritura de archivos, comandos de consola) necesarias para completar este paso específico.
Al concluir este paso, responde con un informe descriptivo y conciso en español de los resultados que obtuviste.
"""
        try:
            # Invocar al executor usando callbacks
            from core.agent_callbacks import JarvisAgentCallbacks
            response = get_executor().invoke(
                {"input": prompt_paso},
                {"callbacks": [JarvisAgentCallbacks()]}
            )
            step["output"] = response.get("output", "Paso finalizado sin salida detallada.")
            step["status"] = "completed"
        except Exception as e:
            logging.error(f"[Autónomo] Fallo en Paso {step['id']}: {e}")
            step["status"] = "failed"
            step["error"] = str(e)
            step["output"] = f"Error: {str(e)}"
            
        # Actualizar persistencia y GUI
        ACTIVE_PLAN_FILE.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        socketio.emit('plan_update', plan)
        
        # Informar progreso a Telegram
        try:
            from core.telegram_bot import bot
            telegram_user_id = os.getenv("TELEGRAM_USER_ID")
            if bot and telegram_user_id:
                status_icon = "✅" if step["status"] == "completed" else "❌"
                bot.send_message(
                    telegram_user_id,
                    f"{status_icon} <b>Paso {step['id']} finalizado</b>: {step['description']}\n\n"
                    f"<b>Resultados:</b>\n{step['output'][:1000]}",
                    parse_mode="HTML"
                )
        except Exception:
            pass

    # Limpieza
    if ACTIVE_PLAN_FILE.exists():
        try:
            ACTIVE_PLAN_FILE.unlink()
        except Exception:
            pass
            
    # Emitir plan finalizado
    socketio.emit('plan_update', {"goal": plan["goal"], "steps": steps, "completed": True})
    
    # Generar informe de síntesis final con el LLM
    try:
        llm = get_llm()
        sintesis_prompt = f"""Has finalizado con éxito todos los pasos de la tarea autónoma: "{plan['goal']}".
Detalles de la ejecución y salidas de los pasos:
{json.dumps(steps, ensure_ascii=False, indent=2)}

Por favor, escribe un informe resumen formal e inteligente en español de cara al usuario sobre el resultado final de la tarea, indicando que todo ha concluido con éxito. Dirígete a él como "señor" y sé conciso (3-4 frases máximo).
"""
        res_summary = llm.invoke(sintesis_prompt).content
    except Exception:
        res_summary = f"Señor, he completado todos los pasos de la tarea '{plan['goal']}' con éxito."

    # Enviar notificación push al móvil
    try:
        from core.notifier import send_push_notification
        has_failed = any(step.get("status") == "failed" for step in steps)
        status_txt = "FALLIDA ❌" if has_failed else "COMPLETADA ✅"
        title = f"🤖 Jarvis: Tarea {status_txt}"
        
        # Resumen del plan
        total_steps = len(steps)
        completed_steps = sum(1 for step in steps if step.get("status") == "completed")
        msg = f"Objetivo: {plan['goal']}\nProgreso: {completed_steps}/{total_steps} pasos completados.\n\nSintesis: {res_summary}"
        
        priority = "high" if has_failed else "default"
        tags = ["warning", "heavy_multiplication_x"] if has_failed else ["white_check_mark", "robot"]
        
        send_push_notification(title=title, message=msg, priority=priority, tags=tags)
    except Exception as ne:
        logging.error(f"[Autónomo] Error al disparar notificación push: {ne}")

    # Responder y hablar
    update_state("speaking", response=res_summary)
    speak(res_summary, disable_vad=True)
    update_state("idle")
