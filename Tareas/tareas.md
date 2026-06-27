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
* [x] Fix de `requirements.txt` (conflictos langchain/greenlet) + 10 tests de CI arreglados; CI verde.
* [x] Healthcheck de arranque (módulo + main + panel GUI) y versionado del esquema SQLite (migraciones).
* [x] Refactor de `main.py` por fases (bootstrap, arranque, calibración, bucle de escucha).
* [x] Keywords del router y alias de modelos movidos a config (`config/*.json`).
* [x] Fix de solape de voz (cola serializada) + latencia media de la IA en el dashboard.
* [x] Layout de la GUI en dos columnas (estilo Stark) + panel de Inbox interactivo.
* [x] GitHub CLI (`gh`) instalado y autenticado para consultar el CI directamente.

## Prioridad alta

* [x] **Panel de Configuración GUI:**
  - [x] Activar/desactivar servicios pesados de fondo.
  - [x] Cambiar STT (small/medium/large).
  - [x] Ver historial de llamadas a modelos.  
  - [x] Ver coste aproximado, tokens y proveedor usado.

* [x] **Comandos Rápidos sin IA concretos:**
  - [x] Comando rápido: resumen del día.
  - [x] Comando rápido: activar modo gaming.
  - [x] Comando rápido: apuntar tarea en bandeja de entrada (Inbox).
  - [x] Comando rápido: estado de servicios locales.
  - [x] Comando rápido: cambiar de modelo activo.

## Camino hacia un Jarvis Real (Módulos de Futuro)

### 🎬 Experiencia e Interfaz
* [x] **Secuencia de Inicio "Suit Up"**: Al arrancar Jarvis, la GUI muestra una animación de cuenta atrás con telemetría apareciendo progresivamente (RAM, servicios, red, alertas) y voz formal en secuencia: *"Inicializando subsistemas... RAM nominal... Protocolos de seguridad activos... Bienvenido, señor."* Como el montaje del casco de Iron Man.
* [x] **HUD Overlay Transparente (siempre visible)**: Ventana flotante semitransparente siempre encima de todo (topmost), estilo casco de Iron Man. Muestra en tiempo real: RAM/CPU del sistema, estado de servicios, hora, último comando procesado y alertas activas parpadeando en rojo. Visible mientras trabajas en el IDE. Implementable con PyQt5 o tkinter sin bordes. ✅ tkinter sin bordes (sin deps nuevas), topmost + alpha + arrastrable, telemetría vía self_monitor, borde rojo parpadeante en alerta, comandos de voz "abre/cierra el HUD".
* [ ] **Widgets HUD Flotantes y Translúcidos**: Ventanas flotantes de escritorio minúsculas, transparentes y sin bordes que aparecen brevemente en las esquinas de tu monitor para mostrar telemetría rápida o notificaciones, simulando los micro-paneles de datos del casco de Iron Man.
* [x] **Sistema de Nivel de Amenaza DEFCON**: Jarvis tiene 4 niveles de alerta que cambian el color de toda la GUI en tiempo real — Verde (nominal), Amarillo (RAM elevada, test fallando, servicio caído), Rojo (RAM crítica, fallo de integridad, dispositivo extraño en red), Violeta (modo ultra-seguro activado). La esfera cambia de color y Jarvis adapta su tono de voz según el nivel.
* [ ] **Modo "Taller Stark" (Sincronización Multi-Pantalla)**: Utilizar WebSockets para transmitir el panel web o HUD secundario a una tablet o teléfono en tu escritorio, dejando tu monitor principal libre exclusivamente para codificar. *"Transmitiendo señal del panel táctil al dispositivo secundario. Enlace establecido."*
* [x] **Protocolo "Blackout" (Modo Noche Inteligente)**: Monitorizar la hora y tus hábitos. Si pasa de la medianoche, Jarvis disminuye el volumen y adopta un tono de voz suave y susurrado, tiñe la interfaz de colores oscuros cálidos y te recuerda descansar. *(Voz suave)* *"Señor, es bastante tarde y su ritmo de tecleo ha disminuido. Sugiero suspender las operaciones."* ✅ Daemon de franja nocturna + tinte cálido GUI + aviso suave 1×/noche + bajada de volumen opcional + comandos de voz. (Pendiente opcional: tono de voz susurrado).
* [ ] **Stark Diagnostic HUD (Telemetría Inyectada en el Navegador)**: Jarvis inyecta automáticamente un script ligero en tus páginas web de desarrollo local, creando un mini HUD flotante y semitransparente directamente en el navegador que muestra logs y excepciones de Python en tiempo real. *"Inyectando telemetría de depuración en la sesión del navegador local, señor."*
* [ ] **Modo "Simulación Multidispositivo" (Responsive Mockup 3D)**: Introduces una URL local en la GUI y Jarvis renderiza en tiempo real la página web simulada en múltiples dispositivos al mismo tiempo (móvil, tablet, portátil, monitor ultra-wide) utilizando modelos 3D que rotan de manera holográfica en pantalla, permitiéndote comprobar el diseño responsive visualmente. *"Simulación de visualizadores multidispositivo iniciada. Renderizando maquetas en tiempo real, señor."*
* [x] **Mapa de Calor de Hardware 3D (Stark Thermal Telemetry)**: Una representación tridimensional interactiva y translúcida de la placa base de tu ordenador en la interfaz web de Jarvis, que cambia de color (de azul a rojo) en tiempo real según la temperatura de los núcleos de tu procesador, la velocidad de los ventiladores y el voltaje de la batería. *"Telemetría térmica activa. Disipadores nominales operando a 2100 RPM."* ✅ Grid 3D three.js de carga real por núcleo (azul→rojo, altura por carga) + CPU/RAM/temp/batería; overlay por voz ("abre el mapa de calor"). Nota: temp/RPM reales no accesibles en este Windows sin admin → la señal es la carga por núcleo (real).
* [x] **Modo "Sala de Hologramas" (Explorador Relacional 3D)**: En la interfaz web de Jarvis, puedes abrir una vista en 3D interactiva que proyecta tus bases de datos o la estructura de clases del proyecto como partículas y enlaces de luz flotantes. Puedes "agarrar" y arrastrar las tablas o clases para ver cómo se relacionan físicamente y explorar visualmente el diseño del sistema. *"Estructura relacional de la base de datos proyectada en el panel 3D, señor."* ✅ Análisis AST del grafo de dependencias de módulos (core/tools/gui) → constelación 3D three.js (nodos por grupo/tamaño, aristas de import), arrastrar/zoom, voz "sala de hologramas".
* [x] **Modo "Stark HUD - Telemetría de Red" (Packet Map 3D)**: Una visualización de tráfico de red interactiva en la GUI que muestra todas las llamadas HTTP/WS entrantes y salientes de tus aplicaciones locales en forma de haces de luz de colores que ya viajan en un mapa tridimensional de nodos interconectados (estilo sala de control de Stark Industries). *"Mapa de paquetes activo. Monitoreando latencia del canal y flujo de payloads entrantes."* ✅ Grafo 3D three.js: nodo central "ESTE EQUIPO" + endpoints remotos (psutil.net_connections) como nodos por IP (color público/privado/local, tamaño por nº de conexiones) con haces de luz pulsantes. Servicio #23, voz "mapa de paquetes"/"telemetría de red".
* [x] **Dashboard de Salud de Jarvis (Self-Monitoring)**: widget en tiempo real en la GUI web que muestra tokens consumidos, coste estimado acumulado hoy, latencia media de las respuestas de IA y estado de los procesos/servicios en segundo plano.
* [x] **Reactor ARC de Recursos**: anillo de energía 3D/canvas estilo reactor en la GUI que late con la carga del sistema — anillo exterior = CPU, anillo medio = RAM, segmentos tipo repulsor y núcleo pulsante; color azul→ámbar→rojo según carga/temperatura. ✅ Canvas reactivo a health_dashboard_update (CPU/RAM) y thermal_update (temp), sin backend nuevo.
* [x] **Boot Holográfico "Sistema en Línea"**: secuencia de arranque cinematográfica DENTRO de la GUI web: módulos que reportan "ONLINE", barra de progreso, estado final, voz formal. ✅ YA EXISTÍA como el overlay Suit Up de la GUI (#suitup-overlay): fases CORE/MEMORY/SERVICES/NETWORK con telemetría real, progreso y skip; disparado por backend (suitup_start/phase) en --awake.
* [x] **Subtítulos en vivo del HUD**: lo que Jarvis dice aparece como texto holográfico flotante en la GUI, sincronizado con su voz. ✅ Barra de subtítulos #hud-subtitles con efecto máquina de escribir, enganchada al evento de estado 'speaking'.

* [x] **Stream de Pensamiento ("Trabajando, señor")**: en tareas largas, Jarvis narra en voz y/o en el HUD lo que va haciendo paso a paso. *"Compilando… ejecutando diagnóstico… casi listo, señor."* Da sensación de que trabaja contigo en tiempo real. ✅ core/narration.py: narrate() emite al HUD (evento thought_stream) y por voz opcional; enganchado a Mark II, Mente Colmena y Casa Llena. Elemento #thought-stream en la GUI con fade. 9 tests.
* [ ] **Pantalla de Reposo Ambiental (Idle HUD)**: cuando llevas un rato sin interactuar, la GUI entra en un modo ambiente con reloj holográfico, clima, ticker de noticias y telemetría girando suavemente — la mansión de Stark en calma. Vuelve al modo normal al detectar actividad.
* [x] **Anuncios Dramáticos de Notificaciones**: Jarvis locuta las notificaciones entrantes con la cadencia de las películas. *"Señor, una llamada entrante de…"* / *"Mensaje prioritario de…"* ✅ core/announcer.py: frases dramáticas por tipo/prioridad (message/call/device/alert) + banner #notification-banner en la GUI (voz opcional); enganchado a mensajes entrantes de Telegram. 12 tests, 92% mutation score. (Leer toasts del SO queda fuera: requiere WinRT/permisos no disponibles).
* [x] **Arranque Épico con el PC**: al encender Windows (arranque automático), Jarvis te recibe con su secuencia de inicialización y un saludo según la hora, antes incluso de abrir nada. *"Sistemas en línea. Buenos días, señor."* ✅ core/autostart.py: registra/quita el autoarranque vía .bat lanzador + HKCU\\Run (reversible, sin admin); voz "activa/desactiva el arranque automático". El saludo épico ya existía (--awake + generate_wake_greeting). 10 tests, 88% mutation score.
* [x] **Informe de Daños (Damage Report)**: estado del sistema en jerga de traje Stark (CPU/RAM/temperatura/servicios/amenaza traducidos a subsistemas, con veredicto). *"Núcleo de procesamiento al 12%, nominal. Reservas de memoria al 40%. Disipadores nominales. Todos los sistemas nominales, señor."* ✅ core/damage_report.py, voz "informe de daños"; 90% mutation score.

### 👁️ Percepción Proactiva
* [x] **JARVIS Proactivo Visual — "Te estoy mirando, señor"**: Daemon que cada 2-3 minutos captura la pantalla, la analiza con Gemini Vision y, si detecta algo relevante (debuggeando un error, llevas mucho tiempo en la misma pestaña, hay un mensaje urgente sin leer), interrumpe con voz sin que se lo pidas. *"Señor, observo que lleva 40 minutos analizando ese stack trace. ¿Desea que elija evaluar el error?"*
* [x] **Monitor de Portapapeles Inteligente**: Daemon que monitoriza el portapapeles en segundo plano. Al copiar un error de Python → ofrece solucionarlo. Una URL → ofrece resumirla. Código → ofrece explicarlo. Sin que le preguntes. *"Señor, detecto que acaba de copiar un traceback. ¿Desea que lo analice?"*
* [ ] **Detección de Presencia por Webcam (Computer Vision)**: Detectar si el usuario está frente al monitor usando la webcam. Si te vas 10 minutos, Jarvis entra en modo low-power y dice *"Parece que se ha ausentado, señor. Pausando escucha activa."* Al volver, te saluda.
* [x] **Protocolo de Enfoque "Verónica"**: Al dar la orden de voz *"Jarvis, activa el protocolo Verónica"*, silencia las notificaciones de Windows, cambia la interfaz web a un esquema de color ámbar cálido de alto contraste, y muestra un temporizador de productividad tipo cuenta atrás en el HUD. *"Protocolo Verónica iniciado. Silenciando distractores externos."* ✅ Silencia toast de Windows (registro reversible) + tinte ámbar GUI + temporizador de cuenta atrás (Pomodoro configurable, "modo enfoque 50 minutos") que auto-finaliza y restaura.
* [x] **Protocolo "Babel" (Traducción Simultánea por Voz)**: Escuchar audio en inglés u otro idioma en tiempo real (de llamadas o vídeos) y ofrecerte una traducción por síntesis de voz al oído o mediante subtítulos discretos en el HUD flotante. *"Traducción en tiempo real activa. Canalizando audio traducido al auricular secundario."* ✅ Traducción por LLM con detección de idioma destino, por voz ("traduce al inglés ...") y por Telegram (/translate), respondiendo con la voz de Jarvis. (Pendiente opcional: modo continuo escuchando audio del sistema en tiempo real).

* [x] **"Escanea esto" (Análisis con Retícula)**: capturas de pantalla/webcam → Jarvis dibuja retículas/cajas de seguimiento sobre lo detectado (texto, ventanas, objetos) y lo narra. *"Identificado: traceback de Python. Analizando…"* HUD de combate de Stark aplicado a tu escritorio. ✅ core/reticle_scan.py: captura (mss) → Gemini Vision con bounding boxes → parse_detections/to_reticles/build_narration puros → overlay tkinter transparente a pantalla completa que dibuja cajas con esquinas en L sobre el escritorio real (errores en rojo), narración por voz + HUD web (reusa narrate). Voz "escanea esto". 22 tests, 52% mutation (el resto son funciones de I/O aisladas mss/genai/tkinter que no corren en CI).
* [x] **Evaluación de Amenaza Narrada**: ante una decisión o acción, Jarvis verbaliza un análisis con probabilidades. *"Analizando… probabilidad de éxito 87%. Riesgo: moderado, señor."* Cálculo heurístico simple sobre el contexto (tests, RAM, complejidad del cambio). ✅ core/threat_assessment.py: heurística sobre RAM/tests fallando/DEFCON/cambios sin confirmar/peligrosidad del comando; voz "análisis de riesgo" / "evalúa &lt;acción&gt;". 12 tests, 88% mutation score.
* [x] **"Señor, detecto un patrón"**: insight proactivo. Jarvis analiza tus logs/hábitos (productividad, errores, anticipación) y, cuando encuentra algo significativo, te lo comenta sin que se lo pidas. *"Señor, observo que sus tests fallan más los lunes por la mañana. ¿Casualidad?"* ✅ core/insights.py: detectores puros sobre los hábitos registrados (anticipación) + base de errores — concentración por día de la semana, pico de actividad horaria, secuencias recurrentes A→B (candidatas a rutina) y errores reincidentes. Daemon #26 (off por defecto), 1 insight/día, HUD flotante 💡 + voz opcional. Voz "¿detectas algún patrón?". 33 tests, 77% mutation score.
* [ ] **Detección de Bucle de Frustración**: si repites el mismo comando que falla varias veces seguidas (o el mismo error reaparece), Jarvis interviene con tacto. *"Permítame, señor; parece atascado. ¿Le echo una mano?"*
* [x] **"Jarvis, vigila esto"**: pones un fichero, proceso, puerto o valor bajo vigilancia y Jarvis te avisa en cuanto cambie. *"Señor, el fichero que vigilaba acaba de modificarse."* ✅ core/watchpost.py (Puesto de Vigilancia, servicio #27): vigila fichero (mtime/size/existencia), proceso (psutil) o puerto (socket); parseo de petición, comparación de estados y frases puros; daemon de sondeo bajo demanda que avisa por voz + banner HUD 👁. Voz "vigila el fichero/proceso/puerto X", "deja de vigilar X", "¿qué estás vigilando?". 32 tests, 81% mutation score.
* [ ] **"Segunda Opinión"**: antes de un commit/push importante, un modelo distinto revisa el diff y da pegas (bugs potenciales, fugas, malas prácticas) antes de confirmar. *"Permítame una observación antes de confirmar, señor: esa función no maneja el caso nulo."*
* [ ] **Explicador de Diffs**: le pides "¿qué cambié?" y Jarvis te narra en lenguaje natural qué hace el diff actual (intención y efecto), no sólo el git diff crudo. *"Ha refactorizado la lógica de reintentos y añadido caché, señor. Sin cambios de comportamiento aparentes."*
* [ ] **"Te Conozco" (Perfil de Hábitos Persistente)**: aprende tus comandos/apps favoritos y crea atajos personalizados sin que se lo pidas, agrupando rutinas frecuentes. *"He notado que siempre abre estos tres. Los he agrupado en 'arranque de trabajo', señor."*
* [ ] **Saludo Contextual al Arrancar**: en vez de un saludo fijo, Jarvis abre según la hora, el clima, tu agenda y cómo acabó la última sesión. *"Buenos días, señor. 7:42, lloviznando. Tiene una reunión a las 9 y dejó el build en rojo anoche."*

### 🧠 Memoria y Contexto Persistente
* [x] Memoria persistente simple con SQLite.
* [x] Mejorar memoria con búsqueda semántica (embeddings de Google + coseno sobre SQLite).
* [ ] RAG Local sobre recuerdos, conversaciones previas y archivos de código del proyecto.
* [x] Grafo de Conocimiento del Proyecto (Architectural Knowledge Graph) para analizar dependencias locales. ✅ Cubierto por la "Sala de Hologramas" (core/architecture_graph.py): grafo AST de dependencias entre módulos, visualizado en 3D.
* [x] Cambio de Contexto por Proyecto (Project Awareness): detección dinámica del repositorio git activo para ajustar el contexto del prompt de Jarvis y responder con telemetría del repositorio (rama, commit, estado) de forma automática. ✅ core/project_awareness.py: detecta el repo activo (rama/commit/cambios), lo inyecta en el system prompt y responde por voz ("estado del proyecto").
* [x] **Protocolo "Mente Colmena" (Consenso Multi-Modelo)**: para preguntas complejas, Jarvis consulta a varios modelos en paralelo (p. ej. DeepSeek, Gemini, Qwen) y sintetiza una respuesta de consenso, señalando explícitamente en qué coinciden y en qué discrepan. *"He consultado a tres núcleos de razonamiento, señor. Consenso en la estrategia; discrepancia menor en la implementación. Le presento la síntesis."* ✅ core/hive_mind.py: consulta en paralelo (ThreadPoolExecutor) a JARVIS_HIVE_MODELS (o los configurados) y un modelo árbitro sintetiza el consenso; voz "mente colmena <pregunta>". Fallback a respuestas en bruto si la síntesis falla.

* [x] **Memoria de Sesión con Callbacks**: Jarvis recuerda lo que se ha dicho en los últimos minutos de la conversación y lo enlaza de forma natural. *"Como mencionó antes, señor, sobre el módulo de red…"* Da continuidad y sensación de que sigue el hilo. ✅ core/session_memory.py: buffer rotativo en memoria de turnos + detección pura de callbacks temáticos (tópicos significativos sin stopwords, ventana temporal, anti-repetición). Integrado en conversation.get_response (registra turnos; enriquece respuestas del agente con el callback). Voz "¿de qué hemos hablado?". 20 tests, 90% mutation score.
* [x] **"¿En qué estaba?" (Reanudar Contexto)**: al volver, Jarvis retoma tu última sesión de trabajo — el archivo, la rama y el bug/tarea en el que andabas (de project awareness + productividad + git). *"Retomamos donde lo dejó, señor: el módulo de red, función de escaneo."* ✅ core/resume_context.py: cruza project_awareness (rama/commit), los ficheros a medias de git status y la actividad principal de productivity; build_resume puro compone la frase. Voz "¿en qué estaba?" / "¿dónde lo dejé?". 16 tests, 91% mutation score.
* [x] **"Explícame este módulo"**: Jarvis lee una parte de tu propio repositorio (un fichero/módulo) y te explica cómo funciona, sus responsabilidades y cómo encaja con el resto. *"Permítame guiarle por ese módulo, señor."* ✅ core/module_explainer.py: resuelve el módulo por nombre (puro), extrae su estructura por AST (docstring/imports/clases/funciones) y genera un resumen estructural útil SIN LLM; si hay modelo de código lo enriquece. Voz "explícame el módulo X". 14 tests, 72% mutation score.

### 🤖 Autonomía y Agentes
* [x] **Drones con Personalidad (Dum-E / U / Butterfingers)**: los drones de Iron Legion tienen nombres y carácter propios; alguno torpe que se disculpa al fallar y otro perfeccionista. *"Dron U, misión completada con elegancia, señor."* / *"Dum-E ha vuelto a fallar… le pido disculpas en su nombre."* ✅ core/drone_character.py: asigna personalidad por ID de dron (U/Dum-E/Butterfingers), incluye una capa de "tristeza" cuando Dum-E falla (mantiene el ID tras cada misión, solo cambia en nuevo dron). Voz: "triste" de Dum-E al fallar, elegante/orgulloso de U al acertar.
* [x] **Protocolo "Mark II" (Auto-mejora)**: Jarvis propone mejoras a su propio código en una rama sandbox aislada, las implementa, las valida con la suite de tests y, sólo si pasan, te deja un commit/PR local para que lo revises y apruebes. Nunca toca `main` sin tu visto bueno. *"Me he tomado la libertad de optimizar mi rutina de arranque, señor. Cambios aislados en una rama; pruebas en verde. ¿Desea revisar el diff?"* ✅ core/mark_ii.py: reescribe UN fichero (modelo de código) en rama aislada markII/*, corre los tests y commitea solo si pasan (si no, descarta y borra la rama); salvaguardas: allowlist de carpetas, árbol limpio obligatorio, sin push/merge, vuelve a tu rama. Corre como dron (background). Voz "protocolo mark dos <fichero>: <mejora>".
* [x] **"Iron Legion" (Enjambre de Drones)**: lanzas tareas largas en segundo plano que corren como "drones" autónomos, cada uno con su estado en vivo en el HUD (en curso / completado / fallido) y aviso por voz al terminar. Panel de control para ver, cancelar o relanzar drones. *"Dron 03 ha completado la auditoría, señor. Dos drones siguen operativos."* ✅ core/drones.py: registro de drones en hilos con estado vivo, misiones integradas (tests/dependencias/limpieza), aviso por voz al terminar (tono según éxito/fallo), panel "Iron Legion" en la GUI (socket drones_update) y voz "lanza un dron de tests"/"estado de los drones"/"limpia los drones". Base para Casa Llena y Mark II.
* [x] **Protocolo "Casa Llena" (House Party)**: ante una orden compleja, Jarvis despliega varios sub-agentes especializados a la vez (uno investiga, otro codifica, otro prueba) que trabajan en paralelo y reportan a un coordinador que te entrega el resultado unificado. ✅ core/house_party.py: roles (investigación/ingeniería/control) con su modelo, ejecución en paralelo (ThreadPoolExecutor) y un coordinador que sintetiza; voz "casa llena <objetivo>". Prompts puros/testeados, fallback a aportaciones en bruto.
* [x] **Protocolo "Mayordomo" ("Buenos días, señor")**: con un comando matutino, Jarvis prepara tu entorno de trabajo (abre el IDE, el repo del día, la terminal, música) y te da el parte: clima, agenda, estado de builds y pendientes. *"Buenos días, señor. He preparado su estación de trabajo. Tres tareas pendientes y cielo despejado."* ✅ core/butler.py: abre apps/URLs (JARVIS_BUTLER_APPS/URLS) + reutiliza el briefing matutino (clima/git/recordatorios); voz "buenos días Jarvis"/"protocolo mayordomo".
* [x] **Anticipación ("Me he tomado la libertad…")**: Jarvis aprende tus patrones de uso (qué apps/repos abres a ciertas horas, qué comandos encadenas) y se adelanta — precargando recursos o sugiriendo la siguiente acción antes de que la pidas. ✅ Motor de predicción por contexto horario/día (logs/anticipation_log.jsonl), registro de aperturas de app/web, daemon que sugiere por voz 1×/día/acción (off por defecto), comando "¿qué suelo hacer ahora?". Servicio #24.
* [ ] **Protocolo "Centinela Nocturno"**: mientras no estás (de noche o ausencia prolongada), Jarvis ejecuta tareas de mantenimiento autónomas (suite de tests, limpieza de temporales, backups, auditorías de dependencias/seguridad) y te deja un informe consolidado para cuando vuelvas. *"Buenos días, señor. Durante la noche ejecuté 214 pruebas; todas en verde. Liberé 1,2 GB y apliqué dos parches menores."*
* [x] **Protocolo "Hijo Pródigo"**: al volver tras una ausencia larga, Jarvis te resume qué ha ocurrido (commits, alertas, dispositivos en red, mensajes) como un mayordomo poniéndote al día. ✅ core/prodigal.py: parte desde el último check-in (commits nuevos, git dirty, dispositivos, notas pendientes, nivel de amenaza); voz "ponme al día" / "qué me he perdido". (Pendiente opcional: auto-disparo al detectar regreso por presencia).

### 🎙️ Voz e Interfaz (UI/UX)
* [x] Barge-in por tecla (interrupción manual).
* [x] Barge-in automático mediante VAD (Voice Activity Detection local).
* [x] Esfera Holográfica 3D (WebGL/Three.js) reactiva a la voz en la GUI.
* [x] Intérprete de código interactivo en la web (HTML, CSS, JSON, gráficos).
* [x] Voice Tone Shifting: adaptar tono, velocidad y estilo de voz de la síntesis según contexto (éxito, error, alerta). ✅ core/voice_tone.py (perfiles neutral/alert/calm/success/humor; rate/pitch en Edge-TTS y voice_settings en ElevenLabs; detección automática del tono por texto).
* [x] **"Medidor de Sarcasmo" configurable**: un dial (0-10) que ajusta cuánta ironía británica gasta Jarvis, inyectado dinámicamente en el system prompt — de mayordomo impecablemente formal a compañero socarrón. Cambiable por voz ("sube el sarcasmo") y desde la GUI. *"Como guste, señor. Aunque dudo que el incremento de mi ironía mejore la compilación."* ✅ core/personality.py (nivel persistido + directiva por tramo inyectada en el prompt), voz "sube/baja el sarcasmo"/"nivel de sarcasmo N"/"modo formal/socarrón" + slider en el panel de ajustes (sincronizado por socket).
* [x] **Reacciones con Alma (micro-emociones)**: Jarvis intercala micro-respuestas con carga emocional contenida según el evento — alivio cuando un test pasa tras una racha de fallos, urgencia medida en una alerta crítica, orgullo seco cuando algo sale impecable, fastidio elegante ante un error tonto. Da la sensación de que "le importa". ✅ core/reactions.py (biblioteca por evento + tono de voz adaptativo; alivio mayor según racha de fallos), enganchado al test watcher (pass↔fail con racha) + directiva de emoción inyectada en el prompt.

* [ ] **Guardián con Gravedad**: ante una acción arriesgada (borrados, comandos peligrosos, operaciones irreversibles), Jarvis confirma con solemnidad de película antes de proceder. *"Le recuerdo que esto infringe varios de mis protocolos de seguridad, señor. ¿Procedo igualmente?"*
* [x] **Modo Conversación Continua (manos libres)**: tras despertar a Jarvis, mantiene la escucha activa unos segundos para que encadenes órdenes y charles sin repetir la palabra clave. *"Le escucho, señor."* ✅ El modo conversación ya existía (di "Jarvis" a secas); añadido que **siga conversacional tras CUALQUIER comando** (JARVIS_CONTINUOUS_MODE) con ventana configurable. core/conversation_flow.py, 100% mutation score.
* [ ] **Modo Mentor**: Jarvis explica el *porqué* de cada sugerencia y decisión, de forma didáctica, para que aprendas en lugar de solo obedecer. Conmutable por voz ("activa el modo mentor").
* [ ] **"Deshaz eso" (Undo de Jarvis)**: revierte la última acción que hizo Jarvis — cierra lo que abrió, deshace un cambio reciente, restaura el estado anterior. *"Revertido, señor."*

### 🖥️ Control de Windows
* [x] Control de volumen general del sistema y reproducción multimedia/Spotify.
* [x] Modo Gaming / Modo Bajo Consumo del PC. ✅ core/game_mode.py + comando de voz ("activar modo gaming").
* [x] Modo Estudio / Focus (Protocolo "Verónica" y "Capa de Sigilo" para silenciar distractores de Windows). ✅ Cubierto por el Protocolo "Verónica" (core/focus_mode.py): silencia notificaciones de Windows + tinte ámbar + temporizador. (Pendiente opcional: "Capa de Sigilo" extra).
* [ ] Modo Clean Slate: cerrar de forma ordenada apps no esenciales, vaciar temporales y liberar RAM.
* [x] Smart Lock: Bloqueo/desbloqueo automático del sistema por intensidad de señal Bluetooth de móvil/watch. ✅ Daemon BLE (bleak) que vigila MAC/nombre + RSSI; bloquea Windows al alejarte (debounce de N escaneos) y te da la bienvenida al volver. (Desbloqueo limitado a saludo: Windows no permite desbloquear por software).

### 🛜 Red y Presencia
* [x] Network Sentinel: detectar dispositivos desconocidos en la red local.
* [x] Presencia por móvil: ARP Scan/Ping para saludar por voz al entrar en el Wi-Fi de casa.
* [x] Radar visual interactivo de dispositivos de la red local en la GUI.
* [x] Telemetría de tráfico de red y sockets abiertos de aplicaciones locales. ✅ Cubierto por el Packet Map 3D (core/packet_map.py): enumera las conexiones inet activas (psutil.net_connections) y las proyecta en 3D.
* [ ] Auditoría avanzada de peticiones externas de scripts (Sandbox de red).
* [ ] **Geocerca por Móvil (ubicación de Telegram)**: compartes tu ubicación por Telegram y, al entrar en una geocerca (p. ej. cerca de casa), Jarvis prepara tu estación antes de que te sientes. *"Está llegando a casa, señor. Preparando su entorno."*

### 🧪 Testing y Calidad
* [x] Test Watcher silencioso en background.
* [x] Log-to-Test Generator.
* [ ] **Detector de Dependencias Muertas**: encuentra imports sin usar en el código y paquetes de `requirements.txt` que ya no se importan, y ofrece limpiarlos con confirmación. *"He detectado 4 dependencias huérfanas, señor. ¿Las retiro?"*
* [ ] **Asistente de Migración**: detecta APIs y dependencias deprecadas (avisos de deprecation, versiones obsoletas) y propone los reemplazos modernos con el cambio sugerido. *"La función que usa quedará obsoleta en la próxima versión, señor. Le propongo la alternativa."*
* [ ] **"¿Por qué falla esto?" (Depuración Guiada)**: depuración interactiva de un test o función concreta — Jarvis recorre el traceback frame a frame, explica qué pasa en cada uno y dónde está la causa raíz. *"El fallo nace tres frames más arriba, señor: la variable llega vacía."*
* [ ] **Detector de Código Duplicado**: encuentra bloques repetidos en el código y sugiere extraerlos a una función/clase común. *"He encontrado lógica duplicada en tres módulos, señor. ¿La refactorizo?"*
* [ ] **Asistente de Naming**: propone nombres claros y consistentes para variables, funciones, ramas y mensajes de commit, siguiendo las convenciones del proyecto.
* [ ] Auto-Test Pilot: generar tests unitarios de forma autónoma basados en el código.
* [ ] QA Test Agent: tests visuales e interactivos E2E usando Playwright en headless.
* [ ] Local Auto-CI: ejecución de tests, formateador y linter en sandbox pre-commit.
* [ ] Load Tester: simulador de rendimiento de red y usuarios concurrentes locales en el servidor.
* [x] Mutation Testing: inyección de mutantes en memoria para validar la calidad de las pruebas. ✅ scripts/mutation_check.py: mini mutation-tester por AST (Windows/3.13) que invierte comparaciones/booleanos/and-or y mide el % de mutantes que matan los tests. Usado para endurecer night_mode (56→68%) y productivity (58→67%). + tests property-based con Hypothesis.
* [ ] Concurrency Stress Pilot: simulación de condiciones de carrera, hilos y deadlocks locales.
* [x] Asistente Git Inteligente: generación automática de mensajes de commit (Conventional Commits), changelogs y resúmenes de branch por voz.
* [x] Auto-Documentador de Código: generación de docstrings PEP 257 y documentación de endpoints Flask con revisión interactiva antes de aplicar.

### 🛡️ Seguridad y Autenticación
* [x] Reparador Autónomo de dependencias vulnerables.
* [x] **"¿Esto es seguro?" (Análisis previo a ejecutar)**: antes de ejecutar un comando o script, Jarvis lo analiza y te advierte de lo peligroso (borrados masivos, rm -rf, escrituras a rutas críticas, descargas y ejecución, etc.). *"Ese comando borraría 2.300 ficheros, señor. ¿Está seguro?"* ✅ core/command_safety.py: analizador graduado por reglas (seguro/precaución/peligro) con motivos; voz "¿es seguro <comando>?". 100% mutation score.
* [ ] **Detector de Copia-Pega Peligroso**: si pegas en la terminal un comando sacado de internet, Jarvis lo intercepta desde el portapapeles y lo analiza antes de que lo ejecutes (curl|bash, comandos ofuscados, rutas del sistema). *"Ese fragmento que acaba de copiar descarga y ejecuta un script remoto, señor. Recomiendo prudencia."*
* [ ] Security Auditor avanzado (OWASP, secretos en código, permisos y hardening local).
* [x] Panel de vulnerabilidades en la GUI con historial de auditorías y parches. ✅ Panel #vulnerability-findings-list en la GUI con dependencias vulnerables y aplicación de parches (socket apply_patch), más el panel de salud de dependencias. (Pendiente opcional: historial persistente de auditorías).
* [ ] Autenticación segura por Huella de Voz.
* [ ] Radar de Ciberdefensa Activa: vigilar puertos locales e intentos de escaneo externos (con mapa 3D).
* [x] Auditoría Proactiva de Dependencias (Dependency Health Check): análisis periódico de dependencias mediante pip list/PyPI metadata para advertir proactivamente sobre librerías desactualizadas o abandonadas antes de que supongan un problema.

### 📊 Informes y Diario
* [x] Daily Digest manual.
* [x] Daily Digest programado de forma automática por scheduler.
* [x] Briefing matutino de voz (tiempo, commits pendientes, tareas de hoy).
* [x] Resumen nocturno y de operaciones ("¿Qué he hecho hoy?").
* [x] Base de conocimiento de errores recurrentes. ✅ core/error_kb.py: firma normalizada del error (ignora rutas/números/direcciones), cuenta ocurrencias y guarda la solución; enganchado al auto-fixer (registra el error y antepone la solución previa si ya se vio); voz "errores recurrentes".
* [x] Rastreador de Productividad por Proyecto: daemon que registra ventana activa y repo git asociado para medir tiempo real dedicado a cada proyecto. ✅ core/productivity.py: muestrea la ventana activa (clasifica proyecto/navegador/terminal/comunicación) e imputa tiempo por día ignorando AFK; voz "¿cuánto he trabajado hoy?". Servicio #25, off por defecto (privacidad).
* [x] Canal de Notificaciones Externas (Telegram/Discord): bot para enviar alertas configurables al móvil (test fallido, dispositivo en red, build completado). ✅ Lado Telegram operativo: el bot envía alertas (intrusos en red, MFA, briefings/digests). (Pendiente opcional: Discord y panel de configuración de alertas).
* [x] Chat conversacional completo por Telegram: hablar con Jarvis por texto y por **notas de voz** (STT Whisper sobre el .ogg) y que conteste con su **voz** (TTS a fichero, audio). Cerebro común `core/conversation.py`, toggle `/voicereply`. ✅
* [ ] Scheduler de Tareas Programadas (Cron de Jarvis): infraestructura centralizada basada en APScheduler para programar tareas con hora/frecuencia (Daily Digest, briefings, etc.) desde un JSON de configuración.

* [ ] **"He preparado una presentación"**: Jarvis genera un mini-dashboard/slide a partir de tus datos (productividad, git, uso de IA, salud del sistema) y lo proyecta en la GUI como un panel resumen visual. *"Le he preparado un resumen ejecutivo, señor."*
* [ ] **Línea de Tiempo Holográfica del Día**: repasa tu jornada (del rastreador de productividad) como un holograma navegable — bloques de tiempo por proyecto/actividad que puedes recorrer. *"Su jornada, señor: 3 horas en Jarvis, una hora de investigación, y un sospechoso intervalo en YouTube."*
* [x] **Resumen de GitHub por Voz**: usando `gh`, Jarvis te da el parte del repo sin abrir el navegador — PRs/issues pendientes de revisar, CI en rojo, releases nuevas. *"Tiene 3 PRs pendientes de revisión y el pipeline de main está en verde, señor."* ✅ core/github_report.py (gh pr/issue list + run list); voz "resumen de github". 17 tests, 78% mutation score. Probado real contra el repo.
* [ ] **Resumen de Cambios Remotos**: tras un `git fetch`, Jarvis te dice qué ha cambiado en el remoto desde tu último pull (commits nuevos, por quién, ramas) antes de que integres. *"En el remoto hay 4 commits nuevos desde su último pull, señor."*
* [ ] **Bitácora de Decisiones (ADR)**: Jarvis registra cada decisión de arquitectura con su contexto, las opciones consideradas y la alternativa elegida (Architecture Decision Records), consultable después. *"Anotado en la bitácora, señor: se optó por SQLite frente a Postgres por simplicidad de despliegue."*
* [ ] **"Resúmeme este vídeo/artículo"**: le das una URL (artículo o vídeo de YouTube, vía transcripción) y Jarvis te entrega el resumen por voz o texto, con los puntos clave. *"Le resumo el vídeo en tres ideas, señor."*
* [ ] **Estimador de Tiempo de Tareas**: a partir de tu historial de productividad, Jarvis predice cuánto tardarás en una tarea similar. *"Calculo unas dos horas para esto, señor, según su ritmo habitual."*

### 📂 Gestión de Archivos y Tareas (Jarvis Inbox)
* [x] Jarvis Inbox para notas rápidas, ideas y recordatorios por voz o texto.
* [ ] Downloads Inbox (bandeja de descargas física monitoreada).
* [ ] Clasificador de archivos inteligente con confirmación interactiva en la GUI.
* [x] Gestor de Entornos (.env Manager): escaneo de variables referenciadas en código vs. presentes en `.env`, detección de faltantes y vacías.
* [ ] Biblioteca de Snippets y Plantillas (Code Pattern Library): almacenamiento SQLite de fragmentos de código repetitivos (decoradores Flask, setups de test, SQLite setup) y su inyección interactiva a través del portapapeles.

### 📱 Futuro Wow
* [x] Rostro Holográfico 3D reactivo por fonemas (Lip-Sync). ✅ Núcleo holográfico: la esfera central pulsa con la amplitud real del audio (envolvente RMS calculada en backend vía pygame.get_raw()+numpy y transmitida por socket; fallback sintético en la GUI). Lip-sync por energía.
* [ ] Copiloto interactivo por gestos (MediaPipe + Webcam).
* [ ] **Avatar Holográfico con Cara (JARVIS Face)**: rostro/máscara holográfica 3D estilo interfaz de JARVIS en la GUI que mueve la boca/rasgos sincronizados con la amplitud del audio TTS (ya emitida por socket). Versión "con cara" del lip-sync por energía que ya existe en la esfera.

### 🖥️ App de Escritorio Nativa
* [ ] App de escritorio local ligera utilizando `pywebview`:
  - Mantener Flask y SocketIO por debajo.
  - Evitar abrir el navegador por defecto.
  - Icono en bandeja de sistema y arranque opcional con Windows.
  - Evaluar Electron/Tauri a futuro si pywebview se queda corto.

### 🎬 El Gran Salto: nivel JARVIS de las películas
Las capacidades que de verdad separan a un buen asistente del JARVIS de Tony Stark. Son grandes y transversales; cada una daría un salto enorme de "sensación JARVIS".

**🏠 Control del mundo físico** (el mayor salto — hoy Jarvis vive dentro del PC)
* [ ] **Integración domótica real**: control de luces, enchufes, climatización y sensores vía Home Assistant / MQTT / Zigbee. *"Atenúo las luces y subo la temperatura, señor."* Es lo que más "magia" daría.
* [ ] **Control de dispositivos**: móvil, TV, audio multi-habitación (Chromecast/Spotify Connect/ADB). *"Pongo música en el salón, señor."*

**👁️ Visión continua y comprensión espacial** (hoy sólo hay capturas puntuales)
* [ ] **Webcam en tiempo real**: seguimiento, reconocimiento facial (saber quién entra), detección de presencia. *"Bienvenido, señor."* / *"Hay alguien más en la sala."*
* [ ] **Memoria visual**: recuerda objetos/escenas vistas. *"¿Dónde dejé las llaves?" → "Sobre la mesa, señor, hace veinte minutos."*

**🎙️ Voz verdaderamente full-duplex** (hoy es turno-a-turno)
* [ ] **Streaming bidireccional con barge-in real**: Jarvis escucha mientras habla, le interrumpes con naturalidad, latencia mínima, sin botones ni esperas. Conversación de verdad.

**🤖 Proactividad con iniciativa ejecutora** (hoy sugiere; el de las pelis decide y hace)
* [x] **Agencia ejecutora bajo políticas de confianza**: Jarvis no sólo sugiere, sino que *ejecuta* acciones de bajo riesgo por su cuenta y te informa. *"Me he tomado la libertad de hacerlo, señor."* Con niveles de autonomía configurables y barandillas. ✅ core/initiative.py (Iniciativa Ejecutora, servicio #28): sobre world_model, compara snapshots y detecta iniciativas puras (RAM crítica, escalada de amenaza, intruso en red, servicio caído, demasiados cambios sin confirmar); política de confianza pura (off/notify/act) que decide announce/execute/ask/skip; sólo autoejecuta acciones SAFE registradas (liberar memoria + drone de limpieza), nada destructivo; cooldown anti-repetición. Voz "toma la iniciativa"/"sólo avísame"/"desactiva la iniciativa". 23 tests, 85% mutation score.

**🧠 Modelo de mundo persistente** (hoy hay piezas sueltas)
* [x] **Cerebro de estado central**: un único modelo de mundo vivo que unifique el estado de los 27 servicios (sistema, red, proyecto, amenazas, hábitos, vigilancias) y sobre el que Jarvis razone de forma global, en vez de consultar cada pieza por separado. ✅ core/world_model.py: snapshot() unifica sistema/servicios/amenaza/proyecto/productividad/red/vigilancias/uso de IA (recolección aislada + caché TTL); build_facts/build_context_block/build_situation_report/overall_status puros. El bloque de estado se inyecta en el prompt del agente (conciencia situacional cada turno, prompts.py) y alimenta el comando de voz "informe de situación". 22 tests, 88% mutation score. Base para la proactividad ejecutora y el motor de fusión.

**🌐 Acceso al mundo en vivo** (hoy consulta puntual; falta tiempo real y fusión)
* [ ] **APIs de datos en vivo (legal)**: noticias, finanzas (bolsa/cripto), vuelos, tráfico, sismos, clima detallado — con webhooks/streams en lugar de consultas puntuales. *"Señor, la acción que vigilaba acaba de caer un 4%."*
* [x] **Motor de Fusión de Fuentes** (lo más "JARVIS"): ante una pregunta, cruza varias APIs + tu contexto y entrega **una respuesta sintetizada con criterio**, no resultados crudos. El equivalente de hive_mind pero con datos del mundo, no con modelos. ✅ core/fusion.py: consulta en paralelo (ThreadPoolExecutor) varias fuentes reales (web vía Tavily→DuckDuckGo, clima OpenWeatherMap, estado interno del world_model) y un modelo sintetiza una respuesta cruzando lo que dicen; selección/prompt/formateo puros, recolección y síntesis aisladas, cada fuente degrada con gracia, fallback a fuentes en bruto si no hay modelo. Voz "fusiona/analiza a fondo/con todo lo que sabes &lt;pregunta&gt;". 17 tests, 83% mutation score.
* [x] **Investigador autónomo profundo**: "investiga X" → navega, lee, contrasta fuentes y entrega un informe. (Base ya disponible: house_party + visual_browser.) ✅ core/researcher.py: descompone la pregunta en sub-preguntas (LLM, parse_plan puro), investiga cada una en paralelo (reusa la fuente web del motor de fusión), contrasta y sintetiza un informe estructurado (resumen + puntos clave + conclusión); parse_plan/build_*_prompt/format_findings_block/build_raw_report/has_findings puros, modelo y web aislados, fallback a hallazgos en bruto sin LLM. Voz "investiga &lt;tema&gt;" / "investiga a fondo &lt;tema&gt;". 18 tests, 90% mutation score.
* [ ] **Vigilancia de temas en internet**: como watchpost pero apuntando al mundo — vigila temas/personas/mercados y avisa de cambios. *"Novedades sobre el tema que seguía, señor."*

**🎨 Manipulación 3D conversacional** (hoy hay visualizaciones, no manipulación generativa)
* [ ] **Diseño holográfico por voz**: "renderiza esto, gíralo, quítale esta parte" — crear y manipular objetos/diagramas 3D hablando, como cuando Tony diseña el traje. (Tienes la base visual con world_map y architecture_graph.)

> ⚠️ Fuera de alcance a propósito (ficción/ilegal): vigilancia de personas, hackeo de sistemas ajenos, acceso a CCTV/satélites de terceros. El JARVIS real lo hace; el nuestro respeta el límite legal y ético.
