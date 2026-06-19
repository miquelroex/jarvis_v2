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

## Prioridad alta

* [x] Crear un router inteligente en Python antes de llamar al agente.
* [x] Mover los comandos rápidos fuera de `main.py` a `core/fast_commands.py`.
* [x] Mejorar `duckduckgo.py` como fallback para que devuelva 5 resultados.
* [x] Añadir una herramienta `tavily_research` para búsquedas más profundas.
* [x] Mejorar el prompt para que use mejor Tavily, Extract y los modelos delegados.
* [x] Añadir pruebas simples para comprobar que las tools cargan bien.
* [x] Añadir pruebas para los comandos rápidos sin IA.
* [x] Revisar que ninguna tool cara pueda ejecutarse sin confirmación.
* [x] Añadir pruebas de integración para router + comandos rápidos.

## Prioridad media

* [x] Crear carpeta `core/`.
* [x] Mover el prompt principal a `core/prompts.py`.
* [x] Mover la creación de modelos a `core/llm_factory.py`.
* [x] Mover el logging de modelos a `core/model_logging.py`.
* [x] Crear memoria persistente simple con SQLite.
* [x] Crear comandos tipo “recuerda que...” y “qué recuerdas de...”.
* [x] Actualizar `README.md` para que refleje el estado real de Jarvis.

## Prioridad baja

* [x] Mejorar la GUI para mostrar el modelo usado.
* [ ] Añadir panel de historial de llamadas a modelos.
* [ ] Añadir modo configuración desde la GUI.
* [ ] Añadir selección manual de modelo desde la GUI.
* [ ] Añadir más comandos rápidos sin IA.
* [x] Añadir voz más natural o configurable.

## No hacer todavía

* [ ] TwinClaw.
* [ ] Docker.
* [ ] Multiagentes complejos.
* [ ] Base vectorial/RAG avanzado.
* [ ] Automatizaciones peligrosas del sistema.
* [ ] Control profundo de Windows sin confirmaciones.

## Camino hacia un Jarvis Real (Autonomía e Integración)

* [ ] **Autonomía de Agente:**
  * [x] Crear un bucle de ejecución autónomo (ReAct / Plan-and-Solve) para tareas complejas de múltiples pasos.
  * [x] Soporte para tareas programadas y ejecución en segundo plano (ej. monitorizar páginas web, alertas horarias).
  * [ ] Framework de seguridad por niveles (Modo Seguro con confirmación vs. Modo Autónomo en carpetas seguras).
  * [x] Creación autónoma de herramientas (Dynamic Tool Creation) cuando detecte que falta una función para cumplir la petición.
  * [ ] Optimizador de Personalidad Autónomo (Meta-Prompting): Modificar y refactorizar autónomamente su propio system prompt en base a tus peticiones en caliente.
  * [x] Agente de Navegación Web Visual: Abrir navegadores en segundo plano, capturar pantallas de la página y analizarlas visualmente con Gemini para navegar de forma autónoma.
  * [x] Analizador de Eficiencia y Automatización de Tareas Repetitivas (Macro Agente): Monitorizar comandos y proponer automatizaciones personalizadas.
  * [x] Debate de Arquitectura de Código de Doble Agente (Twin-Agent Peer Review): Simular discusión entre dos agentes con personalidades opuestas para auditar el diseño de tu código.
  * [ ] Agente Probador Automático de Interfaces (QA Test Agent): Ejecutar navegadores automatizados headless (Playwright) para interactuar con tu web buscando bugs lógicos o visuales de forma autónoma.
  * [x] Selector Autónomo de Ofertas de Trabajo (Smart Recruiter): Monitorear portales de empleo y pre-redactar cartas de presentación personalizadas basadas en el stack tecnológico real de tus repositorios.
  * [x] Compañero Socrático de Depuración (Rubber Ducking Agent): Modo de asistencia donde Jarvis guía al usuario mediante preguntas lógicas en vez de dar la solución de código de inmediato.
  * [ ] Auto-Instalación y Auto-Reparación de Dependencias (Self-Healing Dependency Agent): Detectar errores de importación y dependencias rotas, instalando de forma autónoma el paquete correcto en el entorno.
  * [x] Centinela de Código en Caliente (Background Git Watcher & Test Runner): Escuchar en segundo plano el repositorio de código y ejecutar silenciosamente los tests del archivo modificado, alertando por voz/notificación si se rompen.
  * [ ] Diagnóstico y Auto-Encendido de Servicios de Desarrollo (Dev-Environment Auto-Healer): Detectar fallos de base de datos o puertos caídos en tu app local y arrancar de forma autónoma los servicios del sistema o Docker correspondientes.
  * [ ] Copiloto Proactivo de Refactorización de Deuda Técnica (Technical Debt Harvester): Analizar pasivamente la base de código en segundo plano, preparando diffs listos para aplicar con un solo clic desde la web.
  * [ ] Optimizador Autónomo de Alias y Atajos de Consola (Proactive Shell Shortcut Creator): Monitorizar los comandos introducidos a mano y crear automáticamente alias/shortcuts permanentes en el perfil de PowerShell o Bash/Zsh para comandos repetitivos.
  * [x] Generador y Validador Autónomo de Playgrounds de API (Auto-API Sandbox Generator): Detectar la creación de nuevas rutas/endpoints locales (FastAPI, Flask, Express) en segundo plano, generando un sandbox de pruebas interactivo en la web y validando respuestas autónomamente.
  * [ ] Arbitraje y Enrutamiento Inteligente de Modelos por Costo/Éxito (Autonomous Model Arbitrage): Evaluar el éxito de tareas y escalar autónomamente consultas complejas o correcciones a modelos premium (como DeepSeek R1/GPT-4o), usando modelos locales u optimizados para tareas triviales.
  * [ ] Centinela de Recursos y Limpieza Automática de Jarvis (Self-Maintenance Watchdog): Supervisar en segundo plano el consumo de memoria, procesos huérfanos y espacio temporal de logs de Jarvis, liberando recursos de forma periódica y autónoma.
  * [ ] Validador Autónomo de Pre-Commit (Local Auto-CI): Interceptar cambios locales listos para commit en Git, ejecutando silenciosamente en un sandbox local la suite de pruebas unitarias, linter y formateador, reportando su viabilidad antes de hacer push.
  * [ ] Auto-Optimizador de Consultas de Base de Datos (Autonomous DB Query Optimizer): Analizar pasivamente consultas SQL u ORM del proyecto, ejecutar comandos EXPLAIN contra la DB local e identificar cuellos de botella sugiriendo índices o refactorizaciones.
  * [ ] Auto-Diagnóstico y Validación Segura de `.env` (Secure Env Watchdog): Escanear en segundo plano el archivo .env, contrastarlo con las variables requeridas en el código y reportar discrepancias o claves placeholders vacías mediante un panel interactivo.
  * [ ] Auto-Mocking Inteligente de APIs de Terceros (Autonomous Test Mock Creator): Detectar llamadas HTTP reales salientes a APIs externas durante la ejecución de pruebas, generando adaptadores de mock automáticos para posibilitar tests 100% locales y offline.
  * [ ] Auto-Generador de Changelog Semántico (Git Autochangelog Synthesizer): Analizar de forma periódica el historial de commits y cambios de Git para generar y estructurar automáticamente el archivo CHANGELOG.md adaptado al tono del desarrollador.
  * [ ] Auto-Reversión ante Caídas de Servidor (Auto-Rollback Agent): Monitorizar en segundo plano logs locales o de staging y, en caso de fallos recurrentes 5xx o crasheos, revertir automáticamente al último commit estable de Git, reiniciando los servicios y enviando reporte por Telegram.
  * [ ] Optimizador Proactivo de Imágenes y Contenedores Docker (Auto-Docker & Asset Optimizer): Analizar configuraciones Dockerfile/docker-compose y archivos de recursos pesados (.png, .jpg), aplicando de forma autónoma compresión WebP y sugiriendo estructuras multi-etapa eficientes.
  * [x] Reparador Autónomo de Dependencias Vulnerables (Continuous Vulnerability Patcher): Ejecutar auditorías periódicas (npm/pip audit) en segundo plano, actualizando dependencias con vulnerabilidades (CVEs) a versiones seguras y validando mediante tests la ausencia de fallos antes de sugerir el parche en la GUI.
  * [x] Diagnóstico Autónomo de Integridad de Jarvis (Jarvis Integrity Sentinel): Ejecutar autodiagnósticos de integridad cada 20 minutos (sintaxis de código, importación de herramientas, variables de entorno y pruebas unitarias), reportando fallos en la GUI, voz y Telegram.

* [x] **Sentidos y Percepción (Visión y Contexto):**

  * [x] Integrar visión multimodal real (Gemini 1.5/2.0 o GPT-4o) para analizar las capturas de pantalla (reemplazando pytesseract).
  * [x] Crear herramienta para obtener la ventana activa de Windows (saber si el usuario está programando, navegando, etc.).
  * [ ] Detector de Sonidos del Entorno: Analizar el audio del micrófono en segundo plano para alertar al usuario de sonidos importantes (timbres, llantos, sirenas, etc.).
  * [ ] Análisis de Vídeo Continuo por Webcam (Live Visual Perception): Procesamiento de vídeo en tiempo real mediante OpenCV para detectar objetos y expresiones del usuario.
  * [ ] Grabación y Análisis de UI Dinámica (Visual Pair Programming): Capturar grabaciones cortas de pantalla para analizar transiciones, animaciones y flujos visuales interactivos con Gemini Pro, corrigiendo fallos de diseño en caliente.
  * [ ] Grabación Automática de Clips para Documentación (Auto-Walkthrough Clips): Grabar clips cortos de pantalla de forma autónoma al implementar interfaces visuales para incorporarlos como WebPs animados en la documentación.
  * [x] Alerta Proactiva de Caída de APIs de Terceros (API Status Sentinel): Monitorear el estado de APIs externas críticas (GitHub, OpenAI, Gemini) y alertar por voz en caso de degradación de servicio.

* [ ] **Control del Sistema y Ejecución:**

  * [x] Crear herramientas de búsqueda, lectura y escritura de archivos locales (con límites de seguridad).
  * [x] Crear herramienta para ejecutar comandos en la terminal (ejecutar tests, scripts, git) y capturar la salida para auto-corrección.
  * [ ] Integración con control de medios (pausar/reproducir Spotify o volumen del sistema).
  * [ ] Monitorización activa de la salud del sistema (temperatura de CPU, RAM, batería) con alertas por voz proactivas.
  * [ ] Copiloto de Refactorización y Auto-Linter: Analizar el proyecto, encontrar advertencias (PEP 8) o bugs, y mostrar una interfaz interactiva de cambios (git diff) en la web para aprobar con un solo clic.
  * [ ] Copias de Seguridad Autónomas Encriptadas: Comprimir directorios de trabajo, encriptar con cryptography y subirlos a almacenamiento seguro de forma programada.
  * [x] Auto-diagnóstico e Investigación de Errores (Error Auto-Fixer): Capturar excepciones de la terminal, buscar soluciones en internet y sugerir correcciones listas para aplicar.
  * [ ] Clasificador Inteligente de Archivos (Smart File Organizer): Monitorizar una carpeta de entrada, analizar archivos con visión multimodal y archivarlos organizadamente de forma automática.
  * [x] Escáner y Alerta de Privacidad Local (Privacy Guard): Analizar periódicamente el sistema para identificar claves API, credenciales expuestas o configuraciones inseguras y alertar de inmediato.
  * [ ] Sandbox de Ejecución Aislada para Scripts Desconocidos: Levantar entornos de ejecución seguros (contenedores/sandboxes locales) para ejecutar y evaluar scripts potencialmente peligrosos antes de integrarlos.
  * [ ] Generador Autónomo de Pruebas de Código (Auto-Test Pilot): Analizar tus archivos y funciones recién creados para generar y ejecutar de forma autónoma sus pruebas unitarias correspondientes.
  * [ ] Auditor Autónomo de Seguridad y Vulnerabilidades (Security Auditor): Escanear periódicamente el proyecto buscando dependencias obsoletas con CVEs conocidas y fallos comunes de OWASP, proponiendo parches de seguridad.
  * [ ] Generador de Pruebas de Carga y Rendimiento (Load Tester Agent): Escribir de forma autónoma scripts de pruebas de carga (Locust/wrk) para evaluar la concurrencia y latencia del servidor, sugiriendo mejoras de rendimiento.
  * [ ] Guardián contra la Duplicación de Código (Anti Copy-Paste Sentinel): Interceptar el portapapeles al copiar fragmentos largos y sugerir modularizarlos en funciones reutilizables.
  * [x] Auto-Generador de Pruebas a partir de Logs de Error (Log-to-Test Generator): Analizar archivos de logs de excepciones, recrear el escenario en local y generar automáticamente la prueba unitaria que falla.
  * [ ] Piloto Autónomo de Pruebas de Mutación (Mutation Testing Pilot): Alterar el código en segundo plano para verificar si tus pruebas unitarias detectan los errores, sugiriendo nuevos tests para mutantes sobrevivientes.
  * [ ] Sincronizador de Documentación en Vivo (Live Codebase Sync Doc): Analizar los cambios de código y actualizar automáticamente el README.md o diagramas de flujo de la documentación del proyecto.
  * [ ] Micro-Mutación en Memoria de Procesos (Dynamic In-Memory Mutation): Realizar alteraciones de bytecode en memoria durante los tests unitarios para verificar rápidamente la calidad de las pruebas sin modificar los archivos físicos.
  * [ ] Piloto de Pruebas de Estrés de Concurrencia (Concurrency Stress Pilot): Simular de forma autónoma condiciones de carrera, colisiones de hilos y deadlocks locales para evaluar y corregir código concurrente.
  * [ ] Detector de Anti-Patrones de Diseño (Anti-Pattern Guard): Analizar la base de código buscando malas prácticas estructurales (God Objects, acoplamiento temporal) y sugerir refactorizaciones a patrones de diseño.
  * [ ] Sandbox de Seguridad y Telemetría de Red (Network Traffic Sandbox): Interceptar y auditar el tráfico de red de los scripts ejecutados para detectar fugas de datos o telemetría de dependencias de terceros.

* [ ] **Memoria y Contexto Persistente:**

  * [ ] Implementar la memoria semántica con SQLite para almacenar datos persistentes del usuario entre reinicios.
  * [ ] RAG Local ligero para responder preguntas sobre los archivos del proyecto o documentación descargada.
  * [ ] Integración con herramientas de productividad (Google Calendar, correos, tareas) para asistencia organizativa.
  * [ ] Simulación de Conciencia y Auto-Reflexión Asíncrona (Modo Sueño / Pasivo): Consolidar la memoria en inactividad, reorganizar datos y sugerir mejoras para la próxima sesión.
  * [ ] Grafo de Conocimiento del Proyecto (Architectural Knowledge Graph): Base de datos de grafos local que analiza dependencias del código para entender la arquitectura completa.
  * [ ] Bitácora del Tiempo y Scrollback de Actividad (Personal Time Machine): Registro histórico de actividad (pestañas, tests, ejecuciones) accesible por Jarvis para consultas retroactivas.
  * [ ] Generador de Informes de Productividad Semanal (Weekly Reflection): Recopilar autónomamente actividad de Git, tareas resueltas y logs para crear resúmenes de rendimiento estructurados los fines de semana.
  * [ ] Bitácora de Hitos y Motivador Diario (Developer Journal & Achievements): Registrar logros del día y dificultades en el desarrollo para presentar un diario motivacional interactivo en la web al final de la jornada.
  * [ ] Mimetismo de Estilo de Escritura (TONE Copywriter): Analizar tus mensajes y commits anteriores para redactar textos, correos y documentación imitando exactamente tu tono y estilo.
  * [ ] Buscador Semántico de tu Historial con Jarvis (Chat History RAG): Almacenar y buscar conceptualmente en tus conversaciones previas con Jarvis para recuperar fragmentos de código y decisiones pasadas.
  * [ ] Visualizador de tu Memoria Semántica (Semantic Memory Visualizer): Vista interactiva en 3D en la interfaz web de Jarvis que muestra y permite gestionar tus recuerdos estructurados en SQLite.
  * [ ] Enlazador de Documentación Oficial en Vivo (External Doc Sync RAG): Monitorear la documentación oficial de tus dependencias para advertir en la GUI sobre cambios destructivos que afecten a tu código.
  * [ ] Gestor de Contexto y Compilador de Memoria Automático (Cognitive Memory Compressor): Monitorizar la saturación del contexto del LLM y comprimir la conversación de manera autónoma, extrayendo conclusiones en logs/session_knowledge.json y vaciando el chat actual sin perder el hilo.

* [ ] **Voz e Interfaz (UI/UX):**

  * [x] Añadir interrupción de voz activa ("barge-in") para detener la reproducción de voz de Jarvis de inmediato al hablarle o pulsar una tecla.
  * [x] Completar refactorización en `tools/voice.py` para desacoplar por completo la lógica de voz de `main.py`.
  * [x] Mostrar consola de pensamiento del modelo, árbol de tareas en segundo plano y logs de modelos en el panel web.
  * [x] Intérprete de Código en la GUI (Estilo Claude Artifacts): Ejecutar e interpretar código Python, PHP, CSS y JSON de forma segura para generar gráficas, HTML/CSS interactivo, árboles de datos JSON o scripts, y mostrarlos en tiempo real en la web.
  * [ ] Detección de Estrés y Ánimo por Voz: Analizar el tono de voz al hablar para adaptar la personalidad, tono y respuestas de Jarvis en tiempo real.
  * [x] Esfera Holográfica 3D (Three.js/WebGL): Reemplazar las partículas 2D de la web por un render holográfico 3D reactivo en tiempo real al micrófono y altavoz.
  * [x] Detección Activa de Habla Local (Voice Activity Detection - VAD): Interrumpir la reproducción de voz automáticamente al detectar que el usuario empieza a hablar.
  * [ ] Modulación Dinámica de la GUI según Contexto y Estado: Cambiar colores, temas y animaciones de la interfaz web en tiempo real según el modelo o nivel de estrés/alerta.
  * [ ] Modulación Emocional Contextual de la Voz (Voice Tone Shifting): Adaptar el tono, ritmo y velocidad de la voz sintética según el resultado de las acciones de Jarvis (ej: tono de éxito vs. error/frustración).
  * [ ] Simulador de Clientes y Stakeholders para Ensayos (Stakeholder Simulator): Simular roleplays de videollamadas/chats con perfiles de negocio exigentes para ensayar explicaciones técnicas.
  * [ ] Mapa Mental Interactivo de Código 3D (Visual Concept Mind-Map): Renderizado 3D dinámico en la web de la arquitectura y dependencias de clases y funciones del proyecto.
  * [ ] Simulador de Entrevistas Técnicas en Vivo (LeetCode Interviewer): Simular entrevistas de código en tiempo real, evaluando tu sintaxis y explicaciones verbales mientras programas en tu IDE.
  * [ ] Entorno de Pruebas de APIs Interactivo y Dinámico (Live API Playground): Generar automáticamente un Swagger interactivo y futurista en la web para enviar peticiones y validar respuestas del servidor en vivo.
  * [ ] Simulador de Negociación de Tarifas y Presupuestos (Rate Negotiator): Entrenar tus habilidades comerciales y de presupuesto mediante conversaciones de voz interactivas donde Jarvis simula ser un cliente difícil.
  * [ ] Simulador de Conflictos de Git (Git Conflict Trainer): Generar de forma artificial ramas conflictivas en local para retarte a resolverlos y enseñarte buenas prácticas de merge/rebase.

* [ ] **Integración Móvil y Domótica (Control Remoto):**
  * [x] Crear un Bot de control remoto (Telegram) para interactuar con el PC de casa y delegar comandos en remoto.
  * [x] Configurar notificaciones push (ntfy.sh/Pushover) enviadas al móvil al concluir tareas autónomas largas.
  * [ ] Integración domótica (Home Assistant/Philips Hue) para control físico del entorno de la oficina.
  * [ ] Autodetector de Presencia (ARP Scan/Ping): Escanear la red local para detectar cuándo tu teléfono móvil se conecta al Wi-Fi o responde a un ping, saludándote por voz automáticamente.
  * [x] Centinela de Red Local: Monitorear silenciosamente la red Wi-Fi y alertar por voz o en la GUI si se detecta la conexión de un dispositivo extraño.
  * [ ] Interacción Remota por Voz sin Pantalla (Earbuds / Bluetooth): Canal bidireccional WebRTC de audio de baja latencia para controlar a Jarvis mediante auriculares o móvil fuera del monitor.
  * [x] Aprobación Remota por Dispositivo de Confianza (MFA Security Prompt): Enviar solicitudes de confirmación push a tu móvil con botones interactivos cuando Jarvis requiera validar acciones críticas en remoto.


## Ideas para el Futuro Lejano (Más adelante / Aún no)

* [ ] Rostro Holográfico 3D Reactivo por Fonemas (Lip-Sync Hologram): Renderizar un avatar 3D abstracto en Three.js que sincronice sus movimientos en tiempo real con los fonemas de la síntesis de voz (TTS) para una interfaz humanoide.


## 🚀 JARVIS Real — Ciencia Ficción y Futurismo

Ideas que harían que Jarvis se sienta como el asistente de Tony Stark de verdad. Ordenadas de mayor a menor factor "wow".

### 🎬 Experiencia e Interfaz

* [ ] **Secuencia de Inicio "Suit Up"**: Al arrancar Jarvis, la GUI muestra una animación de cuenta atrás con telemetría apareciendo progresivamente (RAM, servicios, red, alertas) y voz formal en secuencia: *"Inicializando subsistemas... RAM nominal... Protocolos de seguridad activos... Bienvenido, señor."* Como el montaje del casco de Iron Man.

* [ ] **HUD Overlay Transparente (siempre visible)**: Ventana flotante semitransparente siempre encima de todo (topmost), estilo casco de Iron Man. Muestra en tiempo real: RAM/CPU del sistema, estado de servicios, hora, último comando procesado y alertas activas parpadeando en rojo. Visible mientras trabajas en el IDE. Implementable con PyQt5 o tkinter sin bordes.

* [ ] **Widgets HUD Flotantes y Translúcidos**: Ventanas flotantes de escritorio minúsculas, transparentes y sin bordes que aparecen brevemente en las esquinas de tu monitor para mostrar telemetría rápida o notificaciones, simulando los micro-paneles de datos del casco de Iron Man.

* [ ] **Sistema de Nivel de Amenaza DEFCON**: Jarvis tiene 4 niveles de alerta que cambian el color de toda la GUI en tiempo real — Verde (nominal), Amarillo (RAM elevada, test fallando, servicio caído), Rojo (RAM crítica, fallo de integridad, dispositivo extraño en red), Violeta (modo ultra-seguro activado). La esfera cambia de color y Jarvis adapta su tono de voz según el nivel.

* [ ] **Diagnóstico de "Integridad de Armadura" (Hardware Check)**: Jarvis monitoriza no solo la RAM y CPU, sino la temperatura real de los componentes (tarjeta gráfica, procesador) y la salud del almacenamiento. Si el equipo se calienta demasiado al jugar o compilar, te da una alerta formal. *"Señor, detecto que el núcleo de la GPU está alcanzando los 82 grados. Recomiendo reducir la carga."*

* [ ] **Modo "Taller Stark" (Sincronización Multi-Pantalla)**: Utilizar WebSockets para transmitir el panel web o HUD secundario a una tablet o teléfono en tu escritorio, dejando tu monitor principal libre exclusivamente para codificar. *"Transmitiendo señal del panel táctil al dispositivo secundario. Enlace establecido."*

* [ ] **Protocolo "Blackout" (Modo Noche Inteligente)**: Monitorizar la hora y tus hábitos. Si pasa de la medianoche, Jarvis disminuye el volumen y adopta un tono de voz suave y susurrado, tiñe la interfaz de colores oscuros cálidos y te recuerda descansar. *(Voz suave)* *"Señor, es bastante tarde y su ritmo de tecleo ha disminuido. Sugiero suspender las operaciones."*

* [ ] **Stark Diagnostic HUD (Telemetría Inyectada en el Navegador)**: Jarvis inyecta automáticamente un script ligero en tus páginas web de desarrollo local, creando un mini HUD flotante y semitransparente directamente en el navegador que muestra logs y excepciones de Python en tiempo real. *"Inyectando telemetría de depuración en la sesión del navegador local, señor."*

### 👁️ Percepción Proactiva

* [ ] **JARVIS Proactivo Visual — "Te estoy mirando, señor"**: Daemon que cada 2-3 minutos captura la pantalla, la analiza con Gemini Vision y, si detecta algo relevante (debuggeando un error, llevas mucho tiempo en la misma pestaña, hay un mensaje urgente sin leer), interrumpe con voz sin que se lo pidas. *"Señor, observo que lleva 40 minutos analizando ese stack trace. ¿Desea que evalúe el error?"* Literalmente lo que hace JARVIS en el taller de Tony.

* [ ] **Monitor de Portapapeles Inteligente**: Daemon que monitoriza el portapapeles en segundo plano. Al copiar un error de Python → ofrece solucionarlo. Una URL → ofrece resumirla. Código → ofrece explicarlo. Sin que le preguntes. *"Señor, detecto que acaba de copiar un traceback. ¿Desea que lo analice?"*

* [ ] **Detector de Estrés y Ánimo por Voz**: Analizar el tono, ritmo y energía de la voz al hablar para detectar cansancio o frustración y que Jarvis adapta su respuesta: más conciso si detecta prisa, más pausado y empático si detecta estrés.

* [ ] **Detección de Presencia por Webcam (Computer Vision)**: Detectar si el usuario está frente al monitor usando la webcam. Si te vas 10 minutos, Jarvis entra en modo low-power y dice *"Parece que se ha ausentado, señor. Pausando escucha activa."* Al volver, te saluda.

* [ ] **Protocolo de Enfoque "Verónica"**: Al dar la orden de voz *"Jarvis, activa el protocolo Verónica"*, silencia las notificaciones de Windows, cambia la interfaz web a un esquema de color ámbar cálido de alto contraste, y muestra un temporizador de productividad tipo cuenta atrás en el HUD. *"Protocolo Verónica iniciado. Silenciando distractores externos."*

* [ ] **Protocolo "Mantis" (Aislamiento Acústico Inteligente)**: Si Jarvis detecta ruido de fondo molesto en tu micrófono (ventilador, ladridos, obras), inicializa automáticamente filtros de ruido basados en IA en el canal de audio local. *"He detectado interferencias acústicas de fondo, señor. He inicializado el protocolo Mantis para aislar su voz."*

* [ ] **Protocolo "Babel" (Traducción Simultánea por Voz)**: Escuchar audio en inglés u otro idioma en tiempo real (de llamadas o vídeos) y ofrecerte una traducción por síntesis de voz al oído o mediante subtítulos discretos en el HUD flotante. *"Traducción en tiempo real activa. Canalizando audio traducido al auricular secundario."*

### 🔐 Seguridad y Autenticación

* [ ] **Autenticación por Huella de Voz (Voice Print Security)**: Al arrancar, Jarvis pide una frase de contraseña. Compara el patrón vocal con un perfil guardado. Si no coincide, entra en modo vigilante y bloquea comandos sensibles. *"No reconozco su perfil vocal, señor. Acceso a protocolos avanzados denegado."*

* [ ] **Modo Paranoia (Escudo Total)**: Comando de voz que activa un perfil donde Jarvis deniega TODA ejecución de código, escritura de archivos y comandos de terminal sin doble confirmación vocal. Para dejar el PC sin supervisión.

* [ ] **Escaneo de Dispositivos "Radar Local" (Radar Holográfico)**: Una sección interactiva en la GUI con forma de radar táctico circular que rastrea y mapea visualmente los dispositivos de tu red local. Los equipos autorizados aparecen en cian, mientras que cualquier dispositivo desconocido parpadea en rojo con una advertencia por voz de Jarvis. *"Alerta de proximidad de red. Se ha detectado una firma no registrada en el cuadrante local."*

* [ ] **Sentry Mode (Vigilancia Física por Webcam)**: Al alejarte del PC, Jarvis activa la cámara. Si detecta movimiento frente al monitor, bloquea el sistema operativo, captura una foto del intruso y te la envía a Telegram. *"Protocolo Sentry activo. Monitoreando el perímetro físico de la consola, señor."*

* [ ] **Protocolo de Contingencia (Cierre de Emergencia)**: Un comando de voz crítico que, al ser pronunciado, minimiza todo el trabajo activo, borra el portapapeles, cifra archivos temporales y apaga o suspende el sistema en menos de 2 segundos. *"Entendido, señor. Protocolo de contingencia iniciado. Apagando todos los subsistemas."*

* [ ] **Modo "Simulador de Vuelo" (Sandbox Seguro)**: Ejecutar cualquier script o archivo desconocido dentro de un contenedor Docker temporal y ligero para analizar su comportamiento en red y disco antes de permitir su ejecución real en tu máquina. *"Iniciando simulacion del archivo en entorno virtual aislado. Monitoreando llamadas al sistema, señor."*

* [ ] **Radar de Ciberdefensa Activa ("Jarvis, ¿quién me escanea?")**: Jarvis monitoriza pasivamente los sockets de red abierta y los registros de eventos de Windows. Si detecta intentos fallados de conexión SSH o escaneos de puertos en tu IP local o pública, la GUI web muestra la localización de la IP atacante en un mapa mundial interactivo en 3D. *"Señor, hemos registrado un intento de escaneo de puertos desde una IP localizada en Frankfurt. He procedido a banear la dirección en el cortafuegos."*

### 🧠 Inteligencia Autónoma

* [ ] **Briefing Matutino Autónomo**: Cada día a la hora configurada, Jarvis te envía por Telegram (o lee por voz al arrancar) un informe de inteligencia: commits pendientes del día anterior, recordatorios de hoy, estado de servicios monitorizados, novedades en tus APIs favoritas y el tiempo. Sin que lo pidas.

* [ ] **Optimizador Autónomo de su Propio Prompt (Meta-Prompting)**: Jarvis analiza tus patrones de uso durante una semana (qué comandos usas más, qué corriges, qué rechazas) y propone ajustes a su propio `SYSTEM_PROMPT`. *"Señor, he observado que corrige mi nivel de detalle frecuentemente. Propongo ajustar el protocolo de verbosidad."*

* [ ] **Grafo de Conocimiento del Proyecto (Architectural Knowledge Graph)**: Base de datos de grafos local que analiza dependencias del código del proyecto para que Jarvis entienda la arquitectura completa y pueda responder preguntas como *"¿Dónde se gestiona la autenticación de Telegram?"* sin enviar todo el código al LLM.

* [ ] **Protocolo "House Party" (Orquestación Multi-Agente)**: Permitir a Jarvis desplegar agentes de software paralelos y especializados (ej. un redactor de tests, un documentador y un refactorizador) para trabajar cooperativamente. La GUI mostrará el progreso animado de cada agente simulando el despliegue de diferentes armaduras de Iron Man. *"Iniciando protocolo House Party. He desplegado las unidades Mark I, II y III para la refactorización paralela del repositorio."*

* [ ] **Protocolo "Clean Slate" (Borrón y Cuenta Nueva)**: Para limpiar la carga del PC. Jarvis cierra de forma ordenada programas y navegadores no esenciales, vacía temporales, libera memoria RAM y reinicia los servicios de base de datos o desarrollo local principales. *"Ejecutando protocolo Clean Slate, señor. Despejando el área de trabajo y liberando recursos."*

* [ ] **Modo "Piloto Automático" (Asistente de Tareas Largas)**: Delegar tareas automatizadas complejas y largas a Jarvis en segundo plano (como ejecutar una suite de testing de extremo a extremo). El HUD pasa a un modo de progreso holográfico visual simplificado. *"Estableciendo piloto automático para la compilación de la suite. Relájese, señor, yo me encargo del análisis."*

* [ ] **Depuración Guiada por Voz ("Jarvis, ¿dónde falla?")**: En lugar de leer logs interminables, puedes preguntar verbalmente por el error actual y Jarvis analizará el traceback, logs de desarrollo y bases de datos para explicarte la causa exacta y las opciones por voz. *"Señor, el servidor devolvió un error 500 porque la variable de conexión de la base de datos está vacía. ¿Desea que la configure?"*

* [ ] **Modo "Capa de Sigilo" (Stealth Mode / Panic Button)**: Al activar este modo, Jarvis minimiza aplicaciones distractoras, maximiza herramientas de desarrollo de prioridad, desactiva notificaciones sociales y selecciona una playlist silenciosa o de ruido blanco para máxima concentración. *"Activando modo de sigilo. Suite de desarrollo maximizada y notificaciones suspendidas."*

* [ ] **Resumen Proactivo de Operaciones ("Jarvis, ¿qué he hecho hoy?")**: Al apagar el equipo, Jarvis recopila tu historial de Git local, ventanas de desarrollo y logs para darte un resumen hablado sumamente interactivo del progreso del día. *"Señor, hoy ha completado la integración de 3 APIs y corregido 2 fallos de concurrencia. Buen progreso operativo."*

* [ ] **Plan de Misión Interactivo (Arquitectura Visual Autónoma)**: Al describir verbalmente un proyecto, Jarvis genera de forma autónoma diagramas de flujo interactivos y esquemas de base de datos en 3D en la GUI web para su validación visual antes de escribir código. *"Hoja de ruta estructurada. He proyectado la arquitectura del sistema y el flujo de base de datos en su panel, señor."*

* [ ] **Protocolo "Back-in-Time" (Viaje en el Tiempo de Código)**: Al preguntarle a Jarvis *"Jarvis, ¿cómo era esta función ayer por la tarde?"*, Jarvis escanea los reflogs de Git, stash y commits locales para extraer la evolución cronológica exacta de un fragmento de código específico y mostrártelo de forma interactiva en la GUI con un deslizador temporal, reproduciendo el cambio paso a paso. *"Reconstruyendo la evolución temporal de la función. Historial de las últimas 24 horas cargado en el panel, señor."*

### 🎙️ Voz Avanzada

* [ ] **Clonar la Voz de JARVIS (Paul Bettany) con ElevenLabs Voice Cloning**: Subir 1-2 minutos de audio limpio de Paul Bettany a ElevenLabs Instant Voice Cloning y usar ese voice_id. Con el modelo `eleven_multilingual_v2` ya implementado, el resultado en español debería ser extraordinario.

* [ ] **Modulación Emocional de la Voz (Voice Tone Shifting)**: Adaptar velocidad, tono y estabilidad de la síntesis según el resultado: voz más grave y pausada para alertas críticas, más ligera para respuestas informales, urgente y sin florituras para emergencias.

### 🖥️ App de Escritorio Nativa

* [ ] **App de Escritorio (Electron/Tauri) con GUI Web Embebida**: Empaquetar Jarvis como una aplicación de escritorio nativa para Windows que arranque el servidor Flask en background y muestre la GUI web actual (`localhost:5000`) dentro de un `BrowserWindow` de Electron o un WebView de Tauri — sin necesidad de abrir el navegador. Ventajas: icono en la barra de tareas, acceso directo en el escritorio, arranque automático con Windows, ventana sin bordes con control total del frame, acceso a APIs nativas del OS (notificaciones del sistema, bandeja, etc.) y posibilidad de añadir el HUD Overlay directamente en la app. La GUI web existente no necesitaría modificarse.



