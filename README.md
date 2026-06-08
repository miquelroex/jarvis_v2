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
*   🔊 **Voz Natural Multicapa**: Sistema TTS asíncrono con preferencia por ElevenLabs y Edge-TTS (voces premium neurales en línea) con fallback a pyttsx3 (voz offline).
*   💾 **Memoria Persistente (SQLite)**: Almacena recuerdos y preferencias del usuario entre reinicios de forma segura. Inyecta dinámicamente hasta 20 recuerdos en el prompt del sistema para dotar a Jarvis de una consciencia pasiva de tus datos sin coste extra de tokens.
*   🛡️ **Centinela de Código en Caliente**: Daemon en segundo plano que monitoriza archivos Python del repositorio, ejecutando de forma optimizada y aislada las pruebas unitarias afectadas al guardar cambios. Alerta por voz únicamente en cambios de estado (`pass ↔ fail`).
*   📅 **Planificador de Tareas y Monitor de URLs (Fase 2)**: Motor de segundo plano que gestiona recordatorios por voz y monitoreo periódico de páginas web (verificando cambios de contenido mediante hash SHA-256). Protege contra spam de alertas pausando la red hasta la reactivación del usuario. Bloquea el acceso a la red local por defecto (permitida únicamente con `allow_local_network=True` y confirmación verbal explícita).
*   🛡️ **Centinela de Red Local (Network Sentinel)**: Daemon pasivo de solo lectura que monitoriza la red Wi-Fi mediante ping sweep y parsing ARP, limitándose estrictamente a la subred privada local con intervalos de seguridad razonables (mínimo 60s). Guarda los dispositivos en `logs/last_network_scan.json` y emite alertas por voz/Telegram de intrusos.

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
Puedes validar que el enrutador, los comandos rápidos locales y las importaciones de todas las herramientas funcionen perfectamente ejecutando:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
*(Todos los tests deben reportar `OK`)*.
