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

### 🎬 Experiencia e Interfaz
* [ ] **Secuencia de Inicio "Suit Up"**: Al arrancar Jarvis, la GUI muestra una animación de cuenta atrás con telemetría apareciendo progresivamente (RAM, servicios, red, alertas) y voz formal en secuencia: *"Inicializando subsistemas... RAM nominal... Protocolos de seguridad activos... Bienvenido, señor."* Como el montaje del casco de Iron Man.
* [ ] **HUD Overlay Transparente (siempre visible)**: Ventana flotante semitransparente siempre encima de todo (topmost), estilo casco de Iron Man. Muestra en tiempo real: RAM/CPU del sistema, estado de servicios, hora, último comando procesado y alertas activas parpadeando en rojo. Visible mientras trabajas en el IDE. Implementable con PyQt5 o tkinter sin bordes.
* [ ] **Widgets HUD Flotantes y Translúcidos**: Ventanas flotantes de escritorio minúsculas, transparentes y sin bordes que aparecen brevemente en las esquinas de tu monitor para mostrar telemetría rápida o notificaciones, simulando los micro-paneles de datos del casco de Iron Man.
* [ ] **Sistema de Nivel de Amenaza DEFCON**: Jarvis tiene 4 niveles de alerta que cambian el color de toda la GUI en tiempo real — Verde (nominal), Amarillo (RAM elevada, test fallando, servicio caído), Rojo (RAM crítica, fallo de integridad, dispositivo extraño en red), Violeta (modo ultra-seguro activado). La esfera cambia de color y Jarvis adapta su tono de voz según el nivel.
* [ ] **Modo "Taller Stark" (Sincronización Multi-Pantalla)**: Utilizar WebSockets para transmitir el panel web o HUD secundario a una tablet o teléfono en tu escritorio, dejando tu monitor principal libre exclusivamente para codificar. *"Transmitiendo señal del panel táctil al dispositivo secundario. Enlace establecido."*
* [ ] **Protocolo "Blackout" (Modo Noche Inteligente)**: Monitorizar la hora y tus hábitos. Si pasa de la medianoche, Jarvis disminuye el volumen y adopta un tono de voz suave y susurrado, tiñe la interfaz de colores oscuros cálidos y te recuerda descansar. *(Voz suave)* *"Señor, es bastante tarde y su ritmo de tecleo ha disminuido. Sugiero suspender las operaciones."*
* [ ] **Stark Diagnostic HUD (Telemetría Inyectada en el Navegador)**: Jarvis inyecta automáticamente un script ligero en tus páginas web de desarrollo local, creando un mini HUD flotante y semitransparente directamente en el navegador que muestra logs y excepciones de Python en tiempo real. *"Inyectando telemetría de depuración en la sesión del navegador local, señor."*
* [ ] **Modo "Simulación Multidispositivo" (Responsive Mockup 3D)**: Introduces una URL local en la GUI y Jarvis renderiza en tiempo real la página web simulada en múltiples dispositivos al mismo tiempo (móvil, tablet, portátil, monitor ultra-wide) utilizando modelos 3D que rotan de manera holográfica en pantalla, permitiéndote comprobar el diseño responsive visualmente. *"Simulación de visualizadores multidispositivo iniciada. Renderizando maquetas en tiempo real, señor."*
* [ ] **Mapa de Calor de Hardware 3D (Stark Thermal Telemetry)**: Una representación tridimensional interactiva y translúcida de la placa base de tu ordenador en la interfaz web de Jarvis, que cambia de color (de azul a rojo) en tiempo real según la temperatura de los núcleos de tu procesador, la velocidad de los ventiladores y el voltaje de la batería. *"Telemetría térmica activa. Disipadores nominales operando a 2100 RPM."*
* [ ] **Modo "Sala de Hologramas" (Explorador Relacional 3D)**: En la interfaz web de Jarvis, puedes abrir una vista en 3D interactiva que proyecta tus bases de datos o la estructura de clases del proyecto como partículas y enlaces de luz flotantes. Puedes "agarrar" y arrastrar las tablas o clases para ver cómo se relacionan físicamente y explorar visualmente el diseño del sistema. *"Estructura relacional de la base de datos proyectada en el panel 3D, señor."*
* [ ] **Modo "Stark HUD - Telemetría de Red" (Packet Map 3D)**: Una visualización de tráfico de red interactiva en la GUI que muestra todas las llamadas HTTP/WS entrantes y salientes de tus aplicaciones locales en forma de haces de luz de colores que ya viajan en un mapa tridimensional de nodos interconectados (estilo sala de control de Stark Industries). *"Mapa de paquetes activo. Monitoreando latencia del canal y flujo de payloads entrantes."*
* [ ] **Dashboard de Salud de Jarvis (Self-Monitoring)**: widget en tiempo real en la GUI web que muestra tokens consumidos, coste estimado acumulado hoy, latencia media de las respuestas de IA y estado de los procesos/servicios en segundo plano.

### 👁️ Percepción Proactiva
* [ ] **JARVIS Proactivo Visual — "Te estoy mirando, señor"**: Daemon que cada 2-3 minutos captura la pantalla, la analiza con Gemini Vision y, si detecta algo relevante (debuggeando un error, llevas mucho tiempo en la misma pestaña, hay un mensaje urgente sin leer), interrumpe con voz sin que se lo pidas. *"Señor, observo que lleva 40 minutos analizando ese stack trace. ¿Desea que elija evaluar el error?"*
* [ ] **Monitor de Portapapeles Inteligente**: Daemon que monitoriza el portapapeles en segundo plano. Al copiar un error de Python → ofrece solucionarlo. Una URL → ofrece resumirla. Código → ofrece explicarlo. Sin que le preguntes. *"Señor, detecto que acaba de copiar un traceback. ¿Desea que lo analice?"*
* [ ] **Detección de Presencia por Webcam (Computer Vision)**: Detectar si el usuario está frente al monitor usando la webcam. Si te vas 10 minutos, Jarvis entra en modo low-power y dice *"Parece que se ha ausentado, señor. Pausando escucha activa."* Al volver, te saluda.
* [ ] **Protocolo de Enfoque "Verónica"**: Al dar la orden de voz *"Jarvis, activa el protocolo Verónica"*, silencia las notificaciones de Windows, cambia la interfaz web a un esquema de color ámbar cálido de alto contraste, y muestra un temporizador de productividad tipo cuenta atrás en el HUD. *"Protocolo Verónica iniciado. Silenciando distractores externos."*
* [ ] **Protocolo "Babel" (Traducción Simultánea por Voz)**: Escuchar audio en inglés u otro idioma en tiempo real (de llamadas o vídeos) y ofrecerte una traducción por síntesis de voz al oído o mediante subtítulos discretos en el HUD flotante. *"Traducción en tiempo real activa. Canalizando audio traducido al auricular secundario."*

### 🧠 Memoria y Contexto Persistente
* [x] Memoria persistente simple con SQLite.
* [ ] Mejorar memoria con búsqueda semántica (Embeddings locales y base vectorial ligera).
* [ ] RAG Local sobre recuerdos, conversaciones previas y archivos de código del proyecto.
* [ ] Grafo de Conocimiento del Proyecto (Architectural Knowledge Graph) para analizar dependencias locales.
* [ ] Cambio de Contexto por Proyecto (Project Awareness): detección dinámica del repositorio git activo para ajustar el contexto del prompt de Jarvis y responder con telemetría del repositorio (rama, commit, estado) de forma automática.

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
* [ ] Asistente Git Inteligente: generación automática de mensajes de commit (Conventional Commits), changelogs y resúmenes de branch por voz.
* [ ] Auto-Documentador de Código: generación de docstrings PEP 257 y documentación de endpoints Flask con revisión interactiva antes de aplicar.

### 🛡️ Seguridad y Autenticación
* [x] Reparador Autónomo de dependencias vulnerables.
* [ ] Security Auditor avanzado (OWASP, secretos en código, permisos y hardening local).
* [ ] Panel de vulnerabilidades en la GUI con historial de auditorías y parches.
* [ ] Autenticación segura por Huella de Voz.
* [ ] Modo "Simulador de Vuelo": ejecución de scripts desconocidos en contenedores Docker aislados.
* [ ] Radar de Ciberdefensa Activa: vigilar puertos locales e intentos de escaneo externos (con mapa 3D).
* [ ] Auditoría Proactiva de Dependencias (Dependency Health Check): análisis periódico de dependencias mediante pip list/PyPI metadata para advertir proactivamente sobre librerías desactualizadas o abandonadas antes de que supongan un problema.

### 📊 Informes y Diario
* [x] Daily Digest manual.
* [ ] Daily Digest programado de forma automática por scheduler.
* [ ] Briefing matutino de voz (tiempo, commits pendientes, tareas de hoy).
* [ ] Resumen nocturno y de operaciones ("¿Qué he hecho hoy?").
* [ ] Weekly Reflection: recopilación semanal estructurada del progreso de desarrollo.
* [ ] Developer Journal: diario de hitos motivacionales interactivo en la GUI.
* [ ] Base de conocimiento de errores recurrentes.
* [ ] Rastreador de Productividad por Proyecto: daemon que registra ventana activa y repo git asociado para medir tiempo real dedicado a cada proyecto.
* [ ] Canal de Notificaciones Externas (Telegram/Discord): bot para enviar alertas configurables al móvil (test fallido, dispositivo en red, build completado).
* [ ] Scheduler de Tareas Programadas (Cron de Jarvis): infraestructura centralizada basada en APScheduler para programar tareas con hora/frecuencia (Daily Digest, briefings, etc.) desde un JSON de configuración.

### 📂 Gestión de Archivos y Tareas (Jarvis Inbox)
* [ ] Jarvis Inbox para notas rápidas, ideas y recordatorios por voz o texto.
* [ ] Downloads Inbox (bandeja de descargas física monitoreada).
* [ ] Clasificador de archivos inteligente con confirmación interactiva en la GUI.
* [ ] Gestor de Entornos (.env Manager): escaneo de variables referenciadas en código vs. presentes en `.env`, detección de faltantes y vacías.
* [ ] Biblioteca de Snippets y Plantillas (Code Pattern Library): almacenamiento SQLite de fragmentos de código repetitivos (decoradores Flask, setups de test, SQLite setup) y su inyección interactiva a través del portapapeles.

### 📱 Futuro Wow
* [ ] Rostro Holográfico 3D reactivo por fonemas (Lip-Sync).
* [ ] Copiloto interactivo por gestos (MediaPipe + Webcam).

### 🖥️ App de Escritorio Nativa
* [ ] App de escritorio local ligera utilizando `pywebview`:
  - Mantener Flask y SocketIO por debajo.
  - Evitar abrir el navegador por defecto.
  - Icono en bandeja de sistema y arranque opcional con Windows.
  - Evaluar Electron/Tauri a futuro si pywebview se queda corto.
