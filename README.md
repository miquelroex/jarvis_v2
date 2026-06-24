# 🧠 Jarvis v2 – Asistente de Voz y Agente de IA Avanzado

**Jarvis v2** es un asistente de voz inteligente, interactivo y altamente optimizado inspirado en el asistente personal de Tony Stark. 

Está diseñado sobre una arquitectura híbrida en Python que combina un **enrutador rápido (Smart Router)** local, un **agente de toma de decisiones LangChain** y un conjunto de **modelos especializados** accesibles mediante OpenRouter (DeepSeek, Qwen Coder, Qwen Thinking, MiniMax, Kimi, GPT) y Google AI Studio (Gemini).

---

## 🚀 Características Clave

*   🗣 **Activación por Voz**: Despierta con la palabra clave **"Jarvis"** o mediante el comando por voz *"despierta"* en modo vigilante.
*   🧭 **Enrutamiento Inteligente (Smart Router)**: Detecta y deriva peticiones síncronas locales o derivaciones de código/razonamiento en Python antes de llamar al agente general de LangChain, optimizando latencia y costes de API.
*   🧠 **Arquitectura Híbrida de LLMs**:
    *   **Modelo Principal**: DeepSeek V4 Pro (razonamiento avanzado y workflows largos).
    *   **Código**: Qwen Coder (resolución de programación y scripts premium).
    *   **Razonamiento**: Qwen 3.7 Plus (análisis lógico y matemático rápido y preciso).
    *   **Agente/Acciones**: MiniMax (tareas de múltiples pasos).
    *   **Premium**: Kimi (Modo Pro) y GPT (requieren confirmación explícita por seguridad de costes).
    *   **Google**: Gemini 3.5 Flash integrado de forma nativa.
*   🔧 **Conjunto de Herramientas de Sistema y Búsqueda**:
    *   `tavily_research`: Investigación profunda que realiza búsquedas web, descarga páginas en Markdown y genera informes estructurados con citas.
    *   `tavily_search` / `tavily_extract_url`: Búsqueda convencional y extracción de contenido de enlaces proporcionados.
    *   `duckduckgo_search`: Fallback secundario de búsqueda con 5 resultados detallados.
    *   `capture_screenshot` / `read_latest_screenshot`: Captura de pantalla y extracción visual de texto mediante OCR (pytesseract).
    *   `open_windows_app` / `open_website`: Lanzamiento de aplicaciones del PC (calculadora, explorador, spotify) y apertura de URLs en navegador.
*   🎨 **Interfaz Gráfica (GUI) en Tiempo Real**: Servidor Flask + Socket.IO incorporado para visualizar el estado cognitivo de Jarvis (idle, escuchando, pensando, hablando) mediante un lienzo animado en `http://localhost:5000`.
*   ⚙️ **Panel de Configuración Lateral**: Control directo desde la GUI para activar/desactivar servicios de fondo en tiempo real y cambiar dinámicamente el tamaño del modelo de transcripción Whisper (descargándolo automáticamente de la RAM al desactivarse).
*   📊 **Historial, Tokens y Dashboard de Costes**: Monitorización precisa de llamadas a LLMs. Registra tokens (prompt/completion), coste estimado en USD del día (con tasas actualizadas de DeepSeek, Gemini, Claude, GPT) y proveedor utilizado, visible en un panel lateral acumulativo hoy y en cada línea del historial de logs en tiempo real.
*   🎬 **Secuencia de Inicio "Suit Up"**: Animación cinematográfica interactiva de cuenta atrás estilo casco de Iron Man al iniciar en modo `--awake`. Muestra telemetría real del sistema en 5 fases secuenciales (CORE, MEMORY, SERVICES, NETWORK, FINAL STATUS). Soporta bypass instantáneo asíncrono con la tecla `ESC` o clic en pantalla.
*   📋 **Monitor de Portapapeles Inteligente**: Daemon en segundo plano de solo lectura que analiza de forma segura tracebacks de Python, código y URLs copiados en el portapapeles (textos <200KB). Muestra una tarjeta emergente Toast HUD en la GUI y te alerta por voz si estás ocioso, permitiendo confirmaciones verbales rápidas (*"sí"* / *"adelante"*) para corregir el error o resumir el sitio.
*   💾 **Memoria Persistente (SQLite)**: Almacena recuerdos y preferencias del usuario entre reinicios de forma segura. Inyecta dinámicamente hasta 20 recuerdos en el prompt del sistema para dotar a Jarvis de una consciencia pasiva de tus datos sin coste extra de tokens.
*   🛡️ **Centinela de Código en Caliente**: Daemon en segundo plano que monitoriza archivos Python del repositorio, ejecutando de forma optimizada y aislada las pruebas unitarias afectadas al guardar cambios. Alerta por voz únicamente en cambios de estado (`pass ↔ fail`).
*   📅 **Planificador de Tareas y Monitor de URLs (Fase 2)**: Motor de segundo plano que gestiona recordatorios por voz y monitoreo periódico de páginas web (verificando cambios de contenido mediante hash SHA-256). Protege contra spam de alertas pausando la red hasta la reactivación del usuario. Bloquea el acceso a la red local por defecto (permitida únicamente con `allow_local_network=True` y confirmación verbal explícita).
*   🛡️ **Centinela de Red Local (Network Sentinel)**: Daemon pasivo de solo lectura que monitoriza la red Wi-Fi mediante ping sweep y parsing ARP, limitándose estrictamente a la subred privada local con intervalos de seguridad razonables (mínimo 60s). Guarda los dispositivos en `logs/last_network_scan.json` y emite alertas por voz/Telegram de intrusos.
*   🚀 **Asistente Git Inteligente**: Módulo de Git interactivo para formatear commits en base al diff (`git diff`), generar mensajes bajo Conventional Commits usando IA, crear changelogs locales y aplicar commits mediante confirmaciones de seguridad terminal/verbal.
*   📖 **Auto-Documentador de Código**: Escáner sintáctico AST que analiza funciones/clases Python sin docstrings y genera su documentación según el estilo PEP 257 de Google mediante IA, permitiendo previsualizar cambios en Unified Diff antes de su aplicación persistente.

---

## 🦾 Protocolos y Módulos Estilo Iron Man

Conjunto de servicios de fondo y experiencias visuales/voz inspirados en el HUD de Stark. Cada uno se activa por voz y/o por variable de entorno (la mayoría desactivados por defecto; consulta `.env.example`).

*   🎙️ **Voz Adaptativa (Tone Shifting)**: Jarvis ajusta automáticamente velocidad, tono y estilo de su voz según el contexto de cada frase: sereno al informar, firme y rápido en alertas, pausado y grave de noche, brillante al confirmar un éxito y juguetón en la ironía. Funciona sobre Edge-TTS (`rate`/`pitch`) y ElevenLabs (`voice_settings`). Interruptor `JARVIS_VOICE_ADAPTIVE_ENABLED`.
*   🦾 **HUD Overlay Flotante**: Ventana de escritorio sin bordes, semitransparente y siempre encima (topmost) con telemetría en vivo (reloj, RAM/CPU, servicios activos, DEFCON, último comando). Borde rojo parpadeante en alerta; arrastrable y `Esc` para cerrar. Voz: *"abre el HUD"*.
*   🔥 **Mapa de Calor de Hardware 3D**: Visualización 3D (three.js) de la carga real por núcleo de la CPU (azul→rojo, con relieve por carga) más CPU/RAM/temperatura/batería. Voz: *"abre el mapa de calor"*.
*   🌍 **Atlas Global 3D**: Globo terráqueo interactivo (Mapbox GL) que vuela a cualquier lugar por voz: *"abre el mapa"*, *"llévame a Tokio"*.
*   🎯 **Protocolo Verónica (Modo Enfoque)**: Silencia las notificaciones de Windows, tiñe la GUI en ámbar de alto contraste y muestra un temporizador de productividad. Voz: *"modo enfoque 50 minutos"*.
*   🌙 **Protocolo Blackout (Modo Noche)**: Pasada cierta hora atenúa la interfaz en tonos cálidos y, una vez por noche, sugiere descansar con voz suave. Voz: *"modo noche"*.
*   🔒 **Smart Lock por Bluetooth**: Bloquea el PC automáticamente cuando tu móvil/reloj se aleja (escaneo BLE por MAC/nombre y RSSI con anti-rebote) y te da la bienvenida al volver.
*   👁️ **JARVIS Proactivo Visual**: Captura periódicamente la pantalla y la analiza con Gemini Vision para avisarte por voz si detecta algo relevante (opt-in; envía capturas a Google).
*   🧠 **Memoria Semántica (RAG local)**: Indexa los recuerdos con embeddings de Google y permite buscarlos por significado (coseno sobre vectores).
*   🧭 **Conciencia de Proyecto (Project Awareness)**: Detecta el repositorio git activo (rama, último commit, cambios sin confirmar) e inyecta ese contexto en el prompt del sistema.
*   🔊 **Control de Audio y Multimedia por Voz**: Sube/baja/silencia el volumen del sistema (pycaw) y controla play/pausa/siguiente/anterior por voz.
*   📥 **Bandeja de Entrada (Inbox)**: Panel interactivo en la GUI para capturar notas/tareas rápidas por voz o teclado.
*   🌡️ **Nivel de Amenaza DEFCON y Self-Monitoring**: Tinte de la interfaz por nivel de amenaza agregado y dashboard de salud en vivo (uso de IA, servicios, sistema).

---

## 🛠️ Configuración e Instalación

### 1. Requisitos
Asegúrate de tener instalado Python 3.10+ y las claves correspondientes en tu entorno.

### 2. Instalar Dependencias
Instala los paquetes necesarios definidos en `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3. Configuración de Variables de Entorno
Crea o edita un archivo `.env` en la raíz del proyecto con la siguiente estructura:
```env
# Claves de API
OPENROUTER_API_KEY=tu_clave_de_openrouter
TAVILY_API_KEY=tu_clave_de_tavily
GOOGLE_API_KEY=tu_clave_de_google_ai_studio
ELEVENLABS_API_KEY=tu_clave_de_elevenlabs
ELEVENLABS_VOICE_ID=voice_id_deseado

# Modelos Jarvis
JARVIS_MODEL_DEFAULT=deepseek/deepseek-v4-pro
JARVIS_MODEL_THINK=qwen/qwen3.7-plus
JARVIS_MODEL_CODE=qwen/qwen3-coder
JARVIS_MODEL_AGENT=minimax/minimax-m2.7
JARVIS_MODEL_PRO=moonshotai/kimi-k2.6
JARVIS_MODEL_GPT=openai/gpt-5.4-mini
JARVIS_MODEL_GEMINI=gemini-3.5-flash
```

---

## ▶️ Ejecución y Pruebas

### Ejecutar Jarvis
Para arrancar el asistente de voz en segundo plano e iniciar la interfaz gráfica en el navegador de manera automática:
```bash
python main.py --awake
```
*Si prefieres iniciarlo en modo vigilante silencioso (esperando el comando "despierta" para abrir el navegador), ejecútalo simplemente con:*
```bash
python main.py
```

### Ejecutar el Suite de Pruebas
Puedes validar que el enrutador, los comandos rápidos locales y las importaciones de todas las herramientas funcionen perfectamente ejecutando (recomendado, igual que en CI):
```bash
python -m pytest -q
```
*(o, con la librería estándar: `python -m unittest discover -s tests -p "test_*.py"`)*.

> **Nota (Windows local):** algunos tests que importan `tools/voice.py` o `gui/app.py` pueden abortar localmente por el conocido error nativo de OpenSSL (`no OPENSSL_Applink`). El pipeline de CI (windows-latest, entorno limpio) los ejecuta sin problema y debe reportar todo en verde.
