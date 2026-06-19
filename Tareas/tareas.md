# Jarvis v2 - Lista de mejoras

## Ya hecho
* [x] Subir el proyecto limpio a GitHub.
* [x] Configurar `.gitignore` para no subir `.env`, `.venv/`, logs ni archivos sensibles.
* [x] Cambiar el modelo principal para que sea configurable con `JARVIS_MODEL_DEFAULT`.
* [x] Poner DeepSeek como modelo principal barato.
* [x] Añadir Gemini por Google AI Studio.
* [x] Añadir delegación a modelos especializados.
* [x] Añadir Qwen para código.
* [x] Añadir Qwen Thinking para razonamiento.
* [x] Añadir MiniMax para tareas tipo agente.
* [x] Añadir Kimi como modo pro.
* [x] Añadir GPT como modelo manual.
* [x] Pedir confirmación antes de usar modelos caros.
* [x] Registrar en logs qué modelo se usa.
* [x] Ignorar `logs/` en Git.
* [x] Añadir comandos rápidos sin IA.
* [x] Añadir Tavily Search.
* [x] Añadir Tavily Extract para leer URLs concretas.
* [x] Crear un router inteligente en Python antes de llamar al agente.
* [x] Mover los comandos rápidos fuera de `main.py` a `core/fast_commands.py`.
* [x] Mejorar `duckduckgo.py` como fallback para que devuelva 5 resultados.
* [x] Añadir una herramienta `tavily_research` para búsquedas más profundas.
* [x] Mejorar el prompt para que use mejor Tavily, Extract y los modelos delegados.
* [x] Añadir pruebas simples para comprobar que las tools cargan bien.
* [x] Añadir pruebas para los comandos rápidos sin IA.
* [x] Revisar que ninguna tool cara pueda ejecutarse sin confirmación.
* [x] Añadir pruebas de integración para router + comandos rápidos.
* [x] Crear carpeta `core/`.
* [x] Mover el prompt principal a `core/prompts.py`.
* [x] Mover la creación de modelos a `core/llm_factory.py`.
* [x] Mover el logging de modelos a `core/model_logging.py`.
* [x] Crear memoria persistente simple con SQLite.
* [x] Crear comandos tipo “recuerda que...” y “qué recuerdas de...”.
* [x] Actualizar `README.md` para que refleje el estado real de Jarvis.
* [x] Mejorar la GUI para mostrar el modelo usado.
* [x] Añadir voz más natural o configurable.

## Completado recientemente
* [x] Integrar faster-whisper como STT para comandos locales.
* [x] Mantener API de Google Speech Recognition como wake word / fallback de voz.
* [x] Añadir pruebas unitarias y de integración para Whisper STT.
* [x] Añadir Daily Digest MVP (`daily_digest.py` de ejecución manual).
* [x] Añadir limpieza y rotación automática de logs y temporales (`log_maintenance.py`).
* [x] Desactivar por defecto los servicios en segundo plano más pesados (ahorro de recursos).
* [x] Corregir bug crítico de persistencia en `memory.clear()`.
* [x] Corregir vulnerabilidad de `JARVIS_SECRET_KEY` hardcodeado en la app Flask.
* [x] Suite de pruebas unitarias validada con éxito (201 tests correctos).

## Prioridad alta

* [ ] **Panel de Configuración GUI:**
  - [ ] Activar/desactivar servicios pesados de fondo.
  - [ ] Cambiar modelo manualmente.
  - [ ] Cambiar STT (small/medium/large).
  - [ ] Ver historial de llamadas a modelos.
  - [ ] Ver coste aproximado, tokens y proveedor usado.

* [ ] **Comandos Rápidos sin IA concretos:**
  - [ ] Comando rápido: resumen del día.
  - [ ] Comando rápido: activar modo gaming.
  - [ ] Comando rápido: apuntar tarea en bandeja de entrada (Inbox).
  - [ ] Comando rápido: estado de servicios locales.
  - [ ] Comando rápido: cambiar de modelo activo.

## Camino hacia un Jarvis Real (Módulos de Futuro)

### 🧠 Memoria y Contexto Persistente
* [x] Memoria persistente simple con SQLite.
* [ ] Mejorar memoria con búsqueda semántica (Embeddings locales y base vectorial ligera).
* [ ] RAG Local sobre recuerdos, conversaciones previas y archivos de código del proyecto.
* [ ] Grafo de Conocimiento del Proyecto (Architectural Knowledge Graph) para analizar dependencias locales.

### 🎙️ Voz e Interfaz (UI/UX)
* [x] Barge-in por tecla (interrupción manual).
* [x] Barge-in automático mediante VAD (Voice Activity Detection local).
* [x] Esfera Holográfica 3D (WebGL/Three.js) reactiva a la voz en la GUI.
* [x] Intérprete de código interactivo en la web (HTML, CSS, JSON, gráficos).
* [ ] Detección de Estrés y Ánimo por Voz al hablar para adaptar las respuestas en caliente.
* [ ] Voice Tone Shifting: adaptar tono, velocidad y estilo de voz de la síntesis según contexto (éxito, error, alerta).
* [ ] Crear voz original estilo asistente británico futurista configurable (diseño en ElevenLabs Voice Library/Voice Design).

### 🖥️ Control de Windows
* [ ] Control de volumen general del sistema y reproducción multimedia/Spotify.
* [ ] Modo Gaming / Modo Bajo Consumo del PC.
* [ ] Modo Estudio / Focus (Protocolo "Verónica" y "Capa de Sigilo" para silenciar distractores de Windows).
* [ ] Modo Clean Slate: cerrar de forma ordenada apps no esenciales, vaciar temporales y liberar RAM.
* [ ] Smart Lock: Bloqueo/desbloqueo automático del sistema por intensidad de señal Bluetooth de móvil/watch.
* [ ] Protocolo de Contingencia: Comando crítico de guardado rápido de buffers y apagado/suspensión en 2 segundos.

### 🛜 Red y Presencia
* [x] Network Sentinel: detectar dispositivos desconocidos en la red local.
* [ ] Presencia por móvil: ARP Scan/Ping para saludar por voz al entrar en el Wi-Fi de casa.
* [ ] Radar visual interactivo de dispositivos de la red local en la GUI.
* [ ] Telemetría de tráfico de red y sockets abiertos de aplicaciones locales.
* [ ] Auditoría avanzada de peticiones externas de scripts (Sandbox de red).

### 🧪 Testing y Calidad
* [x] Test Watcher silencioso en background.
* [x] Log-to-Test Generator.
* [ ] Auto-Test Pilot: generar tests unitarios de forma autónoma basados en el código.
* [ ] QA Test Agent: tests visuales e interactivos E2E usando Playwright en headless.
* [ ] Local Auto-CI: ejecución de tests, formateador y linter en sandbox pre-commit.
* [ ] Load Tester: simulador de rendimiento de red y usuarios concurrentes locales en el servidor.
* [ ] Mutation Testing: inyección de mutantes en memoria para validar la calidad de las pruebas.
* [ ] Concurrency Stress Pilot: simulación de condiciones de carrera, hilos y deadlocks locales.

### 🛡️ Seguridad y Autenticación
* [x] Reparador Autónomo de dependencias vulnerables.
* [ ] Security Auditor avanzado (OWASP, secretos en código, permisos y hardening local).
* [ ] Panel de vulnerabilidades en la GUI con historial de auditorías y parches.
* [ ] Autenticación segura por Huella de Voz.
* [ ] Modo "Simulador de Vuelo": ejecución de scripts desconocidos en contenedores Docker aislados.
* [ ] Radar de Ciberdefensa Activa: vigilar puertos locales e intentos de escaneo externos (con mapa 3D).

### 📊 Informes y Diario
* [x] Daily Digest manual.
* [ ] Daily Digest programado de forma automática por scheduler.
* [ ] Briefing matutino de voz (tiempo, commits pendientes, tareas de hoy).
* [ ] Resumen nocturno y de operaciones ("¿Qué he hecho hoy?").
* [ ] Weekly Reflection: recopilación semanal estructurada del progreso de desarrollo.
* [ ] Developer Journal: diario de hitos motivacionales interactivo en la GUI.
* [ ] Base de conocimiento de errores recurrentes.

### 📂 Gestión de Archivos y Tareas (Jarvis Inbox)
* [ ] Jarvis Inbox para notas rápidas, ideas y recordatorios por voz o texto.
* [ ] Downloads Inbox (bandeja de descargas física monitoreada).
* [ ] Clasificador de archivos inteligente con confirmación interactiva en la GUI.

### 📱 Futuro Wow
* [ ] Modo "Sala de Hologramas": exploración en 3D interactiva de clases y bases de datos.
* [ ] Rostro Holográfico 3D reactivo por fonemas (Lip-Sync).
* [ ] Copiloto interactivo por gestos (MediaPipe + Webcam).

### 🖥️ App de Escritorio Nativa
* [ ] App de escritorio local ligera utilizando `pywebview`:
  - Mantener Flask y SocketIO por debajo.
  - Evitar abrir el navegador por defecto.
  - Icono en bandeja de sistema y arranque opcional con Windows.
  - Evaluar Electron/Tauri a futuro si pywebview se queda corto.
