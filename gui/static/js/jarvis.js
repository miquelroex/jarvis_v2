// ==========================================
// JARVIS — Interfaz gráfica animada
// ==========================================

// --- CONFIGURACIÓN THREE.JS ---
const canvas = document.getElementById('jarvis-canvas');

// Elementos de texto
const statusEl = document.getElementById('status');
const transcriptEl = document.getElementById('transcript');
const responseEl = document.getElementById('response');
const modelContainerEl = document.getElementById('model-container');
const modelNameEl = document.getElementById('model-name');
const activeWindowContainerEl = document.getElementById('active-window-container');
const activeWindowAppEl = document.getElementById('active-window-app');
const activeWindowTitleEl = document.getElementById('active-window-title');
const socraticBadgeEl = document.getElementById('socratic-badge');

// Elementos de la Consola de Pensamiento y Planificación
const thoughtConsoleContainerEl = document.getElementById('thought-console-container');
const thoughtConsoleIndicatorEl = document.getElementById('thought-console-indicator');
const thoughtLogEl = document.getElementById('thought-log');
const planStepsListEl = document.getElementById('plan-steps-list');

// Elementos del Panel de Artefactos
const artifactsPanelEl = document.getElementById('artifacts-panel');
const artifactFilenameEl = document.getElementById('artifact-filename');
const artifactIconEl = document.getElementById('artifact-icon');
const artifactCodeDisplayEl = document.getElementById('artifact-code-display');
const artifactPreviewPaneEl = document.getElementById('artifact-preview-pane');
const artifactCodePaneEl = document.getElementById('artifact-code-pane');

const btnTabPreview = document.getElementById('artifact-tab-preview');
const btnTabCode = document.getElementById('artifact-tab-code');
const btnRun = document.getElementById('artifact-btn-run');
const btnCopy = document.getElementById('artifact-btn-copy');
const btnClose = document.getElementById('artifact-btn-close');

// Elementos del Panel de Configuración
const settingsPanelEl = document.getElementById('settings-panel');
const settingsBtn = document.getElementById('settings-btn');
const settingsBtnClose = document.getElementById('settings-btn-close');
const whisperModelSelect = document.getElementById('whisper-model-select');
const whisperStatusValue = document.getElementById('whisper-status-value');

// Elementos de métricas acumuladas diarias
const dailyCallsVal = document.getElementById('daily-calls-val');
const dailyTokensVal = document.getElementById('daily-tokens-val');
const dailyCostVal = document.getElementById('daily-cost-val');

// --- COLORES Y PARÁMETROS SEGÚN ESTADO ---
const stateColors = {
    idle:      { r: 0.0, g: 0.83, b: 1.0 },   // Azul cian (#00d4ff)
    listening: { r: 0.0, g: 0.59, b: 1.0 },   // Azul brillante (#0096ff)
    thinking:  { r: 1.0, g: 0.78, b: 0.0 },   // Amarillo/dorado (#ffc800)
    speaking:  { r: 0.0, g: 1.0, b: 0.53 }    // Verde (#00ff88)
};

const stateLabels = {
    idle:      'EN ESPERA',
    listening: 'ESCUCHANDO...',
    thinking:  'PROCESANDO...',
    speaking:  'RESPONDIENDO'
};

const stateParams = {
    idle:      { driftAmp: 1.0, gravityContraction: 1.0, voiceRippleAmp: 0.0, connectionDistance: 1.1, lineOpacityMultiplier: 0.35, dustSpeed: 0.2, nodeSize: 0.12 },
    listening: { driftAmp: 1.5, gravityContraction: 1.0, voiceRippleAmp: 0.1, connectionDistance: 1.3, lineOpacityMultiplier: 0.50, dustSpeed: 0.4, nodeSize: 0.15 },
    thinking:  { driftAmp: 0.5, gravityContraction: 0.32, voiceRippleAmp: 0.0, connectionDistance: 0.6, lineOpacityMultiplier: 0.70, dustSpeed: 2.0, nodeSize: 0.08 },
    speaking:  { driftAmp: 1.2, gravityContraction: 1.0, voiceRippleAmp: 0.45, connectionDistance: 1.2, lineOpacityMultiplier: 0.45, dustSpeed: 0.3, nodeSize: 0.16 }
};

let currentState = 'idle';
let currentColor = { ...stateColors.idle };
let targetColor = { ...stateColors.idle };

let currentParams = { ...stateParams.idle };
let targetParams = { ...stateParams.idle };

// DEFCON: color de la esfera según el nivel de amenaza (rojo/violet la fuerzan).
const defconColors = {
    amber:  { r: 1.0,  g: 0.67, b: 0.0  },
    red:    { r: 1.0,  g: 0.2,  b: 0.27 },
    violet: { r: 0.69, g: 0.36, b: 1.0  }
};
let defconOverride = false;

// Setup de Three.js
const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.z = 8.0;

const hologramGroup = new THREE.Group();
scene.add(hologramGroup);

// Helper para crear textura de punto redondo suave dinámicamente
const createCircleTexture = () => {
    const canvasTex = document.createElement('canvas');
    canvasTex.width = 16;
    canvasTex.height = 16;
    const ctx = canvasTex.getContext('2d');
    const grad = ctx.createRadialGradient(8, 8, 0, 8, 8, 8);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.5, 'rgba(255, 255, 255, 0.5)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 16, 16);
    return new THREE.CanvasTexture(canvasTex);
};
const pointTexture = createCircleTexture();

// 1. Nodos Neuronales Principales (220 centros activos)
const nodeCount = 220;
const nodesGeom = new THREE.BufferGeometry();
const nodesPositions = new Float32Array(nodeCount * 3);
nodesGeom.setAttribute('position', new THREE.BufferAttribute(nodesPositions, 3));

const nodeData = [];
for (let i = 0; i < nodeCount; i++) {
    // Distribución esférica aleatoria tridimensional
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2.0 * Math.random() - 1.0);
    const r = Math.pow(Math.random(), 0.8) * 2.2;
    
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta);
    const z = r * Math.cos(phi);
    
    nodesPositions[i * 3] = x;
    nodesPositions[i * 3 + 1] = y;
    nodesPositions[i * 3 + 2] = z;
    
    nodeData.push({
        x: x, y: y, z: z,
        baseX: x, baseY: y, baseZ: z,
        // Parámetros de deriva orgánica individual
        phaseX: Math.random() * Math.PI * 2,
        phaseY: Math.random() * Math.PI * 2,
        phaseZ: Math.random() * Math.PI * 2,
        freqX: 0.8 + Math.random() * 1.5,
        freqY: 0.8 + Math.random() * 1.5,
        freqZ: 0.8 + Math.random() * 1.5,
        amp: 0.2 + Math.random() * 0.4
    });
}

const nodeMaterial = new THREE.PointsMaterial({
    size: currentParams.nodeSize,
    map: pointTexture,
    color: new THREE.Color(currentColor.r, currentColor.g, currentColor.b),
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false
});
const coreNodes = new THREE.Points(nodesGeom, nodeMaterial);
hologramGroup.add(coreNodes);

// 2. Filamentos Dinámicos (Líneas interconectoras)
const maxConnections = 800; // Limitar líneas para mantener 60 FPS
const lineGeom = new THREE.BufferGeometry();
const linePositions = new Float32Array(maxConnections * 2 * 3);
const lineColors = new Float32Array(maxConnections * 2 * 3);
lineGeom.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
lineGeom.setAttribute('color', new THREE.BufferAttribute(lineColors, 3));

const lineMaterial = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 1.0,
    blending: THREE.AdditiveBlending,
    depthWrite: false
});
const neuralLines = new THREE.LineSegments(lineGeom, lineMaterial);
hologramGroup.add(neuralLines);

// 3. Enjambre Cósmico de Fondo (2500 micro-partículas)
const dustCount = 2500;
const dustGeom = new THREE.BufferGeometry();
const dustPositions = new Float32Array(dustCount * 3);
dustGeom.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));

const dustData = [];
for (let i = 0; i < dustCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2.0 * Math.random() - 1.0);
    const r = 1.0 + Math.pow(Math.random(), 0.7) * 3.5;
    
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta);
    const z = r * Math.cos(phi);
    
    dustPositions[i * 3] = x;
    dustPositions[i * 3 + 1] = y;
    dustPositions[i * 3 + 2] = z;
    
    dustData.push({
        r: r,
        theta: theta,
        phi: phi,
        speed: 0.02 + Math.random() * 0.05
    });
}

const dustMaterial = new THREE.PointsMaterial({
    size: 0.035,
    color: new THREE.Color(currentColor.r, currentColor.g, currentColor.b),
    transparent: true,
    opacity: 0.25,
    blending: THREE.AdditiveBlending,
    depthWrite: false
});
const dustPoints = new THREE.Points(dustGeom, dustMaterial);
hologramGroup.add(dustPoints);

// Redimensionamiento dinámico
function resize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}
window.addEventListener('resize', resize);

// Parallax con el ratón
let mouseX = 0, mouseY = 0;
let targetMouseX = 0, targetMouseY = 0;
window.addEventListener('mousemove', (e) => {
    targetMouseX = (e.clientX / window.innerWidth) * 2 - 1;
    targetMouseY = -(e.clientY / window.innerHeight) * 2 + 1;
});

const lerp = (start, end, amt) => (1 - amt) * start + amt * end;

let lastTime = 0;
let runTime = 0;

// --- Núcleo holográfico reactivo a la voz ---
let voiceLevelTarget = 0;   // amplitud objetivo (0..1) recibida del backend
let voiceLevelSmooth = 0;   // amplitud suavizada para la animación
let extraRipple = 0;        // contribución de la voz a la onda radial
let voiceCoreActive = false; // Jarvis está hablando (entre start y stop)
let lastVoiceLevelAt = 0;   // timestamp del último voice_level real recibido

// Actualizar posiciones de nodos principales
const updateNodes = (time) => {
    const posAttr = coreNodes.geometry.attributes.position;
    const posArray = posAttr.array;
    
    nodeData.forEach((node, i) => {
        // Deriva orgánica individual
        const driftX = Math.sin(time * node.freqX + node.phaseX) * node.amp * currentParams.driftAmp;
        const driftY = Math.cos(time * node.freqY + node.phaseY) * node.amp * currentParams.driftAmp;
        const driftZ = Math.sin(time * node.freqZ + node.phaseZ) * node.amp * currentParams.driftAmp;
        
        // Contracción gravitatoria en 'thinking'
        const mult = currentParams.gravityContraction;
        let targetX = node.baseX * mult + driftX;
        let targetY = node.baseY * mult + driftY;
        let targetZ = node.baseZ * mult + driftZ;
        
        // Onda expansiva radial para hablar ('speaking')
        const distFromCenter = Math.sqrt(node.baseX * node.baseX + node.baseY * node.baseY + node.baseZ * node.baseZ);
        if (distFromCenter > 0.1) {
            const radialRipple = Math.sin(distFromCenter * 3.0 - time * 12.0) * (currentParams.voiceRippleAmp + extraRipple);
            if (radialRipple > 0) {
                targetX += (node.baseX / distFromCenter) * radialRipple;
                targetY += (node.baseY / distFromCenter) * radialRipple;
                targetZ += (node.baseZ / distFromCenter) * radialRipple;
            }
        }
        
        node.x = targetX;
        node.y = targetY;
        node.z = targetZ;
        
        posArray[i * 3] = node.x;
        posArray[i * 3 + 1] = node.y;
        posArray[i * 3 + 2] = node.z;
    });
    posAttr.needsUpdate = true;
};

// Reconstruir filamentos de conexión basados en distancias
const updateConnections = (threeColor) => {
    const posAttr = neuralLines.geometry.attributes.position;
    const colAttr = neuralLines.geometry.attributes.color;
    const posArray = posAttr.array;
    const colArray = colAttr.array;
    
    let lineIdx = 0;
    const threshold = currentParams.connectionDistance;
    
    for (let i = 0; i < nodeCount; i++) {
        const nodeA = nodeData[i];
        for (let j = i + 1; j < nodeCount; j++) {
            const nodeB = nodeData[j];
            
            const dx = nodeA.x - nodeB.x;
            const dy = nodeA.y - nodeB.y;
            const dz = nodeA.z - nodeB.z;
            const distSq = dx*dx + dy*dy + dz*dz;
            
            if (distSq < threshold * threshold) {
                const dist = Math.sqrt(distSq);
                // La opacidad decae a mayor distancia
                const opacity = (1.0 - dist / threshold) * currentParams.lineOpacityMultiplier;
                
                posArray[lineIdx * 6] = nodeA.x;
                posArray[lineIdx * 6 + 1] = nodeA.y;
                posArray[lineIdx * 6 + 2] = nodeA.z;
                posArray[lineIdx * 6 + 3] = nodeB.x;
                posArray[lineIdx * 6 + 4] = nodeB.y;
                posArray[lineIdx * 6 + 5] = nodeB.z;
                
                // Color modulado por la opacidad (Additive Blending)
                const r = threeColor.r * opacity;
                const g = threeColor.g * opacity;
                const b = threeColor.b * opacity;
                
                colArray[lineIdx * 6] = r;
                colArray[lineIdx * 6 + 1] = g;
                colArray[lineIdx * 6 + 2] = b;
                colArray[lineIdx * 6 + 3] = r;
                colArray[lineIdx * 6 + 4] = g;
                colArray[lineIdx * 6 + 5] = b;
                
                lineIdx++;
                if (lineIdx >= maxConnections) break;
            }
        }
        if (lineIdx >= maxConnections) break;
    }
    
    // Limpiar posiciones de filamentos sobrantes
    for (let i = lineIdx; i < maxConnections; i++) {
        posArray[i * 6] = 0; posArray[i * 6 + 1] = 0; posArray[i * 6 + 2] = 0;
        posArray[i * 6 + 3] = 0; posArray[i * 6 + 4] = 0; posArray[i * 6 + 5] = 0;
        
        colArray[i * 6] = 0; colArray[i * 6 + 1] = 0; colArray[i * 6 + 2] = 0;
        colArray[i * 6 + 3] = 0; colArray[i * 6 + 4] = 0; colArray[i * 6 + 5] = 0;
    }
    
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
};

// Actualizar enjambre cósmico lento
const updateDust = (delta) => {
    const posAttr = dustPoints.geometry.attributes.position;
    const posArray = posAttr.array;
    
    for (let i = 0; i < dustCount; i++) {
        const d = dustData[i];
        d.theta += d.speed * delta * currentParams.dustSpeed;
        
        const mult = currentParams.gravityContraction;
        const currentR = d.r * mult;
        
        posArray[i * 3] = currentR * Math.sin(d.phi) * Math.cos(d.theta);
        posArray[i * 3 + 1] = currentR * Math.sin(d.phi) * Math.sin(d.theta);
        posArray[i * 3 + 2] = currentR * Math.cos(d.phi);
    }
    posAttr.needsUpdate = true;
};

// Bucle de renderizado
function animate(now) {
    requestAnimationFrame(animate);
    
    const delta = (now - lastTime) * 0.001 || 0.016;
    lastTime = now;
    
    runTime += delta;
    
    // Suavizar transiciones de colores
    currentColor.r = lerp(currentColor.r, targetColor.r, 0.05);
    currentColor.g = lerp(currentColor.g, targetColor.g, 0.05);
    currentColor.b = lerp(currentColor.b, targetColor.b, 0.05);
    
    // Suavizar transiciones de parámetros
    currentParams.driftAmp = lerp(currentParams.driftAmp, targetParams.driftAmp, 0.05);
    currentParams.gravityContraction = lerp(currentParams.gravityContraction, targetParams.gravityContraction, 0.05);
    currentParams.voiceRippleAmp = lerp(currentParams.voiceRippleAmp, targetParams.voiceRippleAmp, 0.05);
    currentParams.connectionDistance = lerp(currentParams.connectionDistance, targetParams.connectionDistance, 0.05);
    currentParams.lineOpacityMultiplier = lerp(currentParams.lineOpacityMultiplier, targetParams.lineOpacityMultiplier, 0.05);
    currentParams.dustSpeed = lerp(currentParams.dustSpeed, targetParams.dustSpeed, 0.05);
    currentParams.nodeSize = lerp(currentParams.nodeSize, targetParams.nodeSize, 0.05);

    // Núcleo reactivo a la voz: si el backend no envía amplitud real, generar un
    // pulso sintético orgánico mientras Jarvis habla (entre start y stop).
    if (voiceCoreActive && (now - lastVoiceLevelAt) > 150) {
        const s = runTime;
        const synth = 0.35 + 0.32 * Math.abs(Math.sin(s * 9.0))
                           + 0.18 * Math.abs(Math.sin(s * 21.0 + 1.3));
        voiceLevelTarget = Math.min(1, synth);
    }
    voiceLevelSmooth += (voiceLevelTarget - voiceLevelSmooth) * 0.35;
    extraRipple = voiceLevelSmooth * 0.55;

    const threeColor = new THREE.Color(currentColor.r, currentColor.g, currentColor.b);

    // 1. Sincronizar colores y tamaños de materiales
    nodeMaterial.color.copy(threeColor);
    nodeMaterial.size = currentParams.nodeSize + voiceLevelSmooth * 1.4;
    dustMaterial.color.copy(threeColor);
    
    // 1b. Sincronizar colores del badge del modelo en la GUI
    if (modelContainerEl && modelContainerEl.classList.contains('active')) {
        const r255 = Math.round(currentColor.r * 255);
        const g255 = Math.round(currentColor.g * 255);
        const b255 = Math.round(currentColor.b * 255);
        
        modelContainerEl.style.borderColor = `rgba(${r255}, ${g255}, ${b255}, 0.25)`;
        modelContainerEl.style.boxShadow = `0 0 15px rgba(${r255}, ${g255}, ${b255}, 0.08)`;
        modelContainerEl.style.background = `rgba(${r255}, ${g255}, ${b255}, 0.04)`;
        
        modelNameEl.style.color = `rgb(${r255}, ${g255}, ${b255})`;
        modelNameEl.style.textShadow = `0 0 8px rgba(${r255}, ${g255}, ${b255}, 0.5)`;
    }
    
    // 1c. Sincronizar colores del panel de artefactos en la GUI
    if (artifactsPanelEl && artifactsPanelEl.classList.contains('active')) {
        const r255 = Math.round(currentColor.r * 255);
        const g255 = Math.round(currentColor.g * 255);
        const b255 = Math.round(currentColor.b * 255);
        
        artifactsPanelEl.style.borderColor = `rgba(${r255}, ${g255}, ${b255}, 0.3)`;
        
        const headerEl = document.getElementById('artifact-header');
        if (headerEl) {
            headerEl.style.borderBottomColor = `rgba(${r255}, ${g255}, ${b255}, 0.2)`;
        }
        
        const activeBtn = document.querySelector('#artifact-controls button.active');
        if (activeBtn) {
            activeBtn.style.background = `rgb(${r255}, ${g255}, ${b255})`;
            activeBtn.style.boxShadow = `0 0 10px rgba(${r255}, ${g255}, ${b255}, 0.4)`;
            activeBtn.style.color = '#000000';
            activeBtn.style.borderColor = `rgb(${r255}, ${g255}, ${b255})`;
        }
        
        const inactiveBtns = document.querySelectorAll('#artifact-controls button:not(.active)');
        inactiveBtns.forEach(btn => {
            btn.style.color = `rgb(${r255}, ${g255}, ${b255})`;
            btn.style.borderColor = `rgba(${r255}, ${g255}, ${b255}, 0.35)`;
            btn.style.background = 'transparent';
            btn.style.boxShadow = 'none';
        });
    }
    
    // 2. Ejecutar físicas y actualizaciones
    updateNodes(runTime);
    updateConnections(threeColor);
    updateDust(delta);
    
    // 3. Rotar suavemente todo el grupo neural
    hologramGroup.rotation.y += 0.0012;
    
    // 4. Parallax del ratón
    mouseX = lerp(mouseX, targetMouseX, 0.05);
    mouseY = lerp(mouseY, targetMouseY, 0.05);
    hologramGroup.rotation.y = mouseX * 0.35 + (runTime * 0.02);
    hologramGroup.rotation.x = -mouseY * 0.35;

    // 5. Latido del núcleo al ritmo de la voz
    hologramGroup.scale.setScalar(1 + voiceLevelSmooth * 0.08);

    renderer.render(scene, camera);
}

// Arrancar la animación
animate();

// --- SOCKET.IO: recibir estados de Jarvis ---
const socket = io();
let clearTextTimer = null; // Guardará el ID del temporizador

const chatHistoryEl = document.getElementById('chat-history');
const modelUsageListEl = document.getElementById('model-usage-list');

// --- BARGE-IN: INTERRUPCIÓN DE VOZ ---
function requestMute() {
    if (currentState === 'speaking') {
        console.log('[JARVIS GUI] Enviando mute_request...');
        socket.emit('mute_request');
    }
}

// Interrupción al hacer clic en el fondo o en el panel central
canvas.addEventListener('click', requestMute);
document.getElementById('overlay').addEventListener('click', (e) => {
    // Solo silenciar si se hace click en el contenedor o panel principal
    if (e.target.id === 'overlay' || e.target.id === 'main-panel' || e.target.id === 'title') {
        requestMute();
    }
});

// Interrupción al pulsar ESC
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        requestMute();
    }
});

function addChatMessage(role, text) {
    if (!text) return;
    
    // Evitar duplicados consecutivos idénticos para el mismo rol (evita duplicados por reconexión)
    const lastMsg = chatHistoryEl.lastElementChild;
    if (lastMsg && lastMsg.classList.contains(role) && lastMsg.textContent === text) {
        return;
    }

    const msg = document.createElement('div');
    msg.classList.add('chat-msg', role);
    msg.textContent = text;
    chatHistoryEl.appendChild(msg);
    // Baja el scroll hasta el final suavemente
    chatHistoryEl.scrollTo({ top: chatHistoryEl.scrollHeight, behavior: 'smooth' });
}

function renderLogItem(log) {
    const item = document.createElement('div');
    item.classList.add('log-item');
    
    // Obtener sólo la hora
    const timeOnly = log.timestamp.split(' ')[1] || log.timestamp;
    
    // Formatear el coste y tokens
    const costText = log.cost ? '$' + parseFloat(log.cost).toFixed(5) : '$0.00000';
    const providerText = (log.provider || 'openrouter').toUpperCase();
    const promptTokens = log.prompt_tokens || 0;
    const completionTokens = log.completion_tokens || 0;
    const totalTokens = log.total_tokens || 0;
    
    item.innerHTML = `
        <div class="log-header">
            <span>${timeOnly} | <span style="font-size: 0.62rem; color: #00d4ff; font-weight: normal;">${providerText}</span></span>
            <span style="font-weight: bold; font-family: monospace; font-size: 0.7rem;">${log.tool_name}</span>
        </div>
        <div class="log-model" style="font-weight: bold; color: #ffffff; margin-top: 2px;">${log.model_name}</div>
        <div class="log-prompt" style="margin-top: 4px; font-style: italic; color: #888888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${log.prompt}</div>
        <div class="log-meta-stats" style="display: flex; justify-content: space-between; font-size: 0.62rem; color: #888888; margin-top: 6px; border-top: 1px dashed rgba(0, 212, 255, 0.15); padding-top: 4px; font-family: monospace;">
            <span>TOKENS: ${promptTokens}+${completionTokens} (${totalTokens})</span>
            <span style="color: #00ff88; font-weight: bold; text-shadow: 0 0 4px rgba(0, 255, 136, 0.2);">${costText}</span>
        </div>
    `;
    return item;
}

socket.on('initial_logs', (logs) => {
    if (!modelUsageListEl) return;   // panel de logs retirado de la GUI
    modelUsageListEl.innerHTML = '';
    // Renderizar de más nuevo a más viejo (los últimos arriba)
    logs.slice().reverse().forEach(log => {
        modelUsageListEl.appendChild(renderLogItem(log));
    });
});

socket.on('new_model_log', (log) => {
    if (!modelUsageListEl) return;   // panel de logs retirado de la GUI
    // Prepend (añadir al principio)
    modelUsageListEl.insertBefore(renderLogItem(log), modelUsageListEl.firstChild);
    // Limitar a 15 elementos
    while (modelUsageListEl.children.length > 15) {
        modelUsageListEl.removeChild(modelUsageListEl.lastChild);
    }
});

socket.on('daily_usage_update', (data) => {
    if (dailyCallsVal) dailyCallsVal.textContent = data.calls || 0;
    if (dailyTokensVal) dailyTokensVal.textContent = data.tokens ? data.tokens.toLocaleString() : 0;
    if (dailyCostVal) {
        dailyCostVal.textContent = data.cost ? '$' + parseFloat(data.cost).toFixed(5) : '$0.00000';
    }
});

// Jarvis Inbox — bandeja de entrada interactiva
socket.on('inbox_update', (items) => {
    const listEl = document.getElementById('inbox-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    if (!items || items.length === 0) {
        listEl.innerHTML = '<div class="inbox-empty">Bandeja vacía. Escribe arriba o di "apunta en la bandeja...".</div>';
        return;
    }
    items.forEach(it => {
        const row = document.createElement('div');
        row.className = 'inbox-item';
        const txt = document.createElement('span');
        txt.className = 'inbox-text';
        txt.textContent = it.content;
        const btn = document.createElement('button');
        btn.className = 'inbox-done-btn';
        btn.textContent = '✓';
        btn.title = 'Marcar como hecha';
        btn.addEventListener('click', () => socket.emit('mark_inbox_done', { id: it.id }));
        row.appendChild(txt);
        row.appendChild(btn);
        listEl.appendChild(row);
    });
});

(() => {
    const input = document.getElementById('inbox-input');
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && input.value.trim()) {
                socket.emit('add_inbox_item', { content: input.value.trim() });
                input.value = '';
            }
        });
    }
    const clearBtn = document.getElementById('inbox-clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (confirm('¿Vaciar toda la bandeja de entrada?')) socket.emit('clear_inbox', {});
        });
    }
})();

// Self-Monitoring — dashboard de salud en vivo
socket.on('health_dashboard_update', (data) => {
    if (!data) return;
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const sys = data.system || {};
    const usage = data.usage || {};
    const svc = data.services || {};

    setText('sm-cpu', (sys.cpu_percent != null ? sys.cpu_percent : '—') + '%');
    setText('sm-ram-sys', (sys.system_ram_percent != null ? sys.system_ram_percent : '—') + '%');
    setText('sm-ram-proc', (sys.process_ram_mb != null ? Math.round(sys.process_ram_mb) : '—') + ' MB');
    setText('sm-services', (svc.running || 0) + ' on · ' + (svc.stopped || 0) + ' off');
    setText('sm-latency', usage.avg_latency_ms != null ? usage.avg_latency_ms + ' ms' : 'N/A');
    setText('sm-calls', usage.calls != null ? usage.calls : '—');
    setText('sm-tokens', usage.tokens != null ? usage.tokens.toLocaleString() : '—');
    setText('sm-cost', usage.cost != null ? '$' + Number(usage.cost).toFixed(4) : '—');

    const up = sys.uptime_seconds || 0;
    const h = Math.floor(up / 3600), m = Math.floor((up % 3600) / 60);
    setText('sm-uptime', h > 0 ? (h + 'h ' + m + 'm') : (m + 'm'));
});

// ===== Globo 3D del mundo (Mapbox) =====
const worldMap = (() => {
    const overlay = document.getElementById('map-overlay');
    const labelEl = document.getElementById('map-label');
    let map = null;
    let spinEnabled = true;
    let userInteracting = false;
    const SECONDS_PER_REV = 140;

    function spinGlobe() {
        if (!map) return;
        if (spinEnabled && !userInteracting && map.getZoom() < 5) {
            const center = map.getCenter();
            center.lng -= 360 / SECONDS_PER_REV;
            map.easeTo({ center, duration: 1000, easing: (n) => n });
        }
    }

    function ensureMap() {
        if (map) return map;
        if (!window.MAPBOX_TOKEN || !window.mapboxgl) {
            console.warn('[Map] Falta MAPBOX_TOKEN o Mapbox GL no cargó.');
            return null;
        }
        mapboxgl.accessToken = window.MAPBOX_TOKEN;
        map = new mapboxgl.Map({
            container: 'map-globe',
            style: 'mapbox://styles/mapbox/dark-v11',
            projection: 'globe',
            center: [0, 20],
            zoom: 1.4,
            attributionControl: false
        });
        map.on('style.load', () => {
            map.setFog({
                'color': 'rgb(8, 16, 26)',
                'high-color': 'rgb(0, 130, 180)',
                'horizon-blend': 0.25,
                'space-color': 'rgb(2, 5, 11)',
                'star-intensity': 0.55
            });
        });
        map.on('mousedown', () => userInteracting = true);
        map.on('dragstart', () => userInteracting = true);
        map.on('mouseup', () => { userInteracting = false; spinGlobe(); });
        map.on('touchend', () => { userInteracting = false; spinGlobe(); });
        map.on('moveend', () => spinGlobe());
        map.on('load', () => spinGlobe());
        return map;
    }

    function show() {
        overlay.classList.add('active');
        const m = ensureMap();
        if (m) setTimeout(() => m.resize(), 60);  // el contenedor estaba oculto
        return m;
    }
    function open() {
        const m = show();
        spinEnabled = true; userInteracting = false;
        if (labelEl) labelEl.textContent = '';
        if (m) {
            const reset = () => m.easeTo({ center: [0, 20], zoom: 1.4, duration: 2200 });
            m.loaded() ? reset() : m.once('load', reset);
        }
    }
    function close() {
        overlay.classList.remove('active');
        spinEnabled = true; userInteracting = false;
    }
    function flyTo(loc) {
        const m = show();
        if (!m || !loc) return;
        spinEnabled = false;
        if (labelEl) labelEl.textContent = loc.name || '';
        const go = () => m.flyTo({ center: [loc.lng, loc.lat], zoom: loc.zoom || 9, duration: 4500, essential: true });
        m.loaded() ? go() : m.once('load', go);
    }
    return { open, close, flyTo };
})();

socket.on('map_open', () => worldMap.open());
socket.on('map_close', () => worldMap.close());
socket.on('map_flyto', (loc) => worldMap.flyTo(loc));

(() => {
    const btn = document.getElementById('map-close-btn');
    if (btn) btn.addEventListener('click', () => worldMap.close());
})();

// DEFCON — nivel de amenaza: tiñe la interfaz y la esfera según el nivel
socket.on('threat_level_update', (data) => {
    const level = (data && data.level) || 'green';
    document.body.classList.remove('defcon-green', 'defcon-amber', 'defcon-red', 'defcon-violet');
    document.body.classList.add('defcon-' + level);

    const levelEl = document.getElementById('defcon-level');
    const reasonEl = document.getElementById('defcon-reason');
    if (levelEl) levelEl.textContent = 'DEFCON ' + level.toUpperCase();
    if (reasonEl) {
        reasonEl.textContent = (data.reasons && data.reasons.length) ? '· ' + data.reasons[0] : '';
    }

    // La esfera adopta el color de alarma en rojo/violet; en green/amber sigue el estado.
    if (level === 'red' || level === 'violet') {
        defconOverride = true;
        targetColor = { ...defconColors[level] };
    } else {
        defconOverride = false;
        targetColor = { ...(stateColors[currentState] || stateColors.idle) };
    }
});

// Núcleo holográfico reactivo a la voz: la esfera pulsa con la amplitud real
socket.on('voice_core_start', () => {
    voiceCoreActive = true;
    lastVoiceLevelAt = 0;
});
socket.on('voice_level', (data) => {
    voiceLevelTarget = Math.max(0, Math.min(1, (data && data.level) || 0));
    lastVoiceLevelAt = performance.now();
});
socket.on('voice_core_stop', () => {
    voiceCoreActive = false;
    voiceLevelTarget = 0;
});

// Protocolo Blackout (modo noche) — atenúa la interfaz en tonos cálidos
socket.on('blackout_on', () => {
    document.body.classList.add('blackout-active');
});
socket.on('blackout_off', () => {
    document.body.classList.remove('blackout-active');
});

// Protocolo Verónica (modo enfoque) — tinte ámbar + temporizador de cuenta atrás
const veronica = (() => {
    let endsAt = null;      // epoch ms
    let ticker = null;
    const panel = document.getElementById('veronica-timer');
    const countEl = document.getElementById('veronica-countdown');

    function fmt(secs) {
        secs = Math.max(0, Math.floor(secs));
        const m = String(Math.floor(secs / 60)).padStart(2, '0');
        const s = String(secs % 60).padStart(2, '0');
        return m + ':' + s;
    }
    function tick() {
        if (endsAt === null) return;
        const remaining = (endsAt - Date.now()) / 1000;
        if (countEl) countEl.textContent = fmt(remaining);
        if (remaining <= 0) stop();   // el backend también lo cierra
    }
    function start(payload) {
        endsAt = (payload && payload.ends_at ? payload.ends_at * 1000 : Date.now() + 25 * 60000);
        document.body.classList.add('focus-veronica');
        if (panel) panel.classList.remove('hidden');
        tick();
        if (ticker) clearInterval(ticker);
        ticker = setInterval(tick, 1000);
    }
    function stop() {
        endsAt = null;
        if (ticker) { clearInterval(ticker); ticker = null; }
        document.body.classList.remove('focus-veronica');
        if (panel) panel.classList.add('hidden');
    }
    socket.on('veronica_on', start);
    socket.on('veronica_off', stop);
    return { start, stop };
})();

// Mapa de calor de hardware 3D (Stark Thermal Telemetry)
const thermalHud = (() => {
    const overlay = document.getElementById('thermal-overlay');
    const canvas = document.getElementById('thermal-canvas');
    const statsEl = document.getElementById('thermal-stats');
    const closeBtn = document.getElementById('thermal-close-btn');
    let scene, camera, renderer, group, tiles = [];
    let rafId = null, built = false, open = false, latest = null;

    function loadColor(load) {
        // 0 (frío/azul 210°) -> 100 (caliente/rojo 0°)
        const t = Math.max(0, Math.min(1, load / 100));
        const hue = (1 - t) * 210;
        const light = 28 + t * 28;
        const c = new THREE.Color();
        c.setStyle(`hsl(${hue.toFixed(0)}, 100%, ${light.toFixed(0)}%)`);
        return c;
    }

    function build() {
        const n = (latest && latest.cores ? latest.cores.length : 16) || 16;
        const cols = Math.ceil(Math.sqrt(n));
        const rows = Math.ceil(n / cols);
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 1000);
        camera.position.set(0, cols * 1.05, cols * 1.5);
        camera.lookAt(0, 0, 0);
        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        resize();

        group = new THREE.Group();
        const gap = 1.18;
        tiles = [];
        for (let i = 0; i < n; i++) {
            const r = Math.floor(i / cols), c = i % cols;
            const geo = new THREE.BoxGeometry(0.95, 1, 0.95);
            const mat = new THREE.MeshBasicMaterial({ color: 0x0a3a6b });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set((c - (cols - 1) / 2) * gap, 0, (r - (rows - 1) / 2) * gap);
            // arista holográfica
            const edges = new THREE.LineSegments(
                new THREE.EdgesGeometry(geo),
                new THREE.LineBasicMaterial({ color: 0x67d4ff, transparent: true, opacity: 0.35 }));
            mesh.add(edges);
            group.add(mesh);
            tiles.push(mesh);
        }
        scene.add(group);
        built = true;
        if (latest) apply(latest);
    }

    function apply(data) {
        if (!built || !data || !data.cores) return;
        data.cores.forEach((core, i) => {
            const mesh = tiles[i];
            if (!mesh) return;
            const load = core.load || 0;
            mesh.material.color = loadColor(load);
            const h = 0.4 + (load / 100) * 2.4;
            mesh.scale.y = h;
            mesh.position.y = h / 2 - 0.2;
        });
        if (statsEl) {
            const temp = (data.cpu_temp != null) ? `${data.cpu_temp}°C` : 'N/D';
            const bat = data.battery ? `${data.battery.percent}%${data.battery.plugged ? ' ⚡' : ''}` : 'N/D';
            statsEl.textContent = `CPU ${data.cpu_overall ?? 0}%  ·  RAM ${data.ram_percent ?? 0}%  ·  TEMP ${temp}  ·  BAT ${bat}`;
        }
    }

    function resize() {
        if (!renderer || !camera) return;
        const w = canvas.clientWidth, h = canvas.clientHeight;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }

    function animate() {
        rafId = requestAnimationFrame(animate);
        if (group) group.rotation.y += 0.0045;
        if (renderer && scene && camera) renderer.render(scene, camera);
    }

    function show() {
        if (!overlay) return;
        overlay.classList.add('active');
        open = true;
        if (!built) build();
        resize();
        if (rafId === null) animate();
    }
    function hide() {
        if (!overlay) return;
        overlay.classList.remove('active');
        open = false;
        if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
    }

    socket.on('thermal_update', (data) => {
        latest = data;
        if (open) apply(data);
    });
    socket.on('thermal_open', show);
    socket.on('thermal_close', hide);
    if (closeBtn) closeBtn.addEventListener('click', hide);
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && open) hide(); });
    window.addEventListener('resize', () => { if (open) resize(); });
    return { show, hide };
})();

// Sala de Hologramas: explorador de arquitectura 3D (constelación de módulos)
const holograph = (() => {
    const overlay = document.getElementById('holo-overlay');
    const canvas = document.getElementById('holo-canvas');
    const statsEl = document.getElementById('holo-stats');
    const closeBtn = document.getElementById('holo-close-btn');
    let scene, camera, renderer, group;
    let rafId = null, built = false, open = false, latest = null;
    let dragging = false, lastX = 0, lastY = 0, zoom = 60;

    const GROUP_COLORS = { core: '#00e5ff', tools: '#ffb000', gui: '#39ff8a' };
    function groupColor(g) { return GROUP_COLORS[g] || '#bf5af2'; }

    function makeLabelSprite(text, colorHex) {
        const cv = document.createElement('canvas');
        const ctx = cv.getContext('2d');
        const font = 22;
        ctx.font = `bold ${font}px Consolas, monospace`;
        cv.width = ctx.measureText(text).width + 16;
        cv.height = font + 12;
        ctx.font = `bold ${font}px Consolas, monospace`;
        ctx.fillStyle = colorHex;
        ctx.shadowColor = colorHex;
        ctx.shadowBlur = 8;
        ctx.fillText(text, 8, font);
        const tex = new THREE.CanvasTexture(cv);
        const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
        const sprite = new THREE.Sprite(mat);
        sprite.scale.set(cv.width / 26, cv.height / 26, 1);
        return sprite;
    }

    function build() {
        const data = latest || { nodes: [], edges: [] };
        const nodes = data.nodes || [];
        const N = Math.max(1, nodes.length);
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(50, canvas.clientWidth / canvas.clientHeight, 0.1, 2000);
        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        resize();

        group = new THREE.Group();
        const R = 26 + N * 0.12;
        const pos = {};
        // Umbral de tamaño para etiquetar sólo los módulos relevantes (evita ruido).
        const sizes = nodes.map(n => n.size || 0).sort((a, b) => b - a);
        const labelThreshold = sizes.length > 28 ? sizes[28] : 0;

        nodes.forEach((n, i) => {
            // Distribución uniforme en esfera (espiral áurea).
            const phi = Math.acos(1 - 2 * (i + 0.5) / N);
            const theta = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
            const x = R * Math.sin(phi) * Math.cos(theta);
            const y = R * Math.sin(phi) * Math.sin(theta);
            const z = R * Math.cos(phi);
            pos[n.id] = new THREE.Vector3(x, y, z);

            const col = new THREE.Color(groupColor(n.group));
            const r = 0.6 + Math.min(n.size || 0, 30) / 30 * 2.2;
            const mesh = new THREE.Mesh(
                new THREE.SphereGeometry(r, 16, 16),
                new THREE.MeshBasicMaterial({ color: col }));
            mesh.position.set(x, y, z);
            group.add(mesh);

            if ((n.size || 0) >= labelThreshold && labelThreshold > 0 || nodes.length <= 30) {
                const label = makeLabelSprite(n.label.replace(/^([a-z]+)\./, ''), groupColor(n.group));
                label.position.set(x, y + r + 1.4, z);
                group.add(label);
            }
        });

        // Aristas (imports) como líneas tenues.
        const verts = [];
        const colors = [];
        (data.edges || []).forEach(e => {
            const a = pos[e.source], b = pos[e.target];
            if (!a || !b) return;
            const c = new THREE.Color(groupColor((e.target.split('.')[0])));
            verts.push(a.x, a.y, a.z, b.x, b.y, b.z);
            colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
        });
        if (verts.length) {
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
            geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
            const lines = new THREE.LineSegments(geo,
                new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.22 }));
            group.add(lines);
        }

        scene.add(group);
        built = true;
        if (statsEl) statsEl.textContent = `${data.module_count ?? nodes.length} módulos · ${data.edge_count ?? (data.edges || []).length} enlaces`;
    }

    function resize() {
        if (!renderer || !camera) return;
        const w = canvas.clientWidth, h = canvas.clientHeight;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }

    function animate() {
        rafId = requestAnimationFrame(animate);
        if (group && !dragging) group.rotation.y += 0.0016;
        if (camera) { camera.position.set(0, 0, zoom); camera.lookAt(0, 0, 0); }
        if (renderer && scene && camera) renderer.render(scene, camera);
    }

    function rebuild() {
        if (renderer) { try { renderer.dispose(); } catch (e) {} }
        built = false;
        build();
    }

    function show() {
        if (!overlay) return;
        overlay.classList.add('active');
        open = true;
        if (!built) build();
        resize();
        if (rafId === null) animate();
    }
    function hide() {
        if (!overlay) return;
        overlay.classList.remove('active');
        open = false;
        if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
    }

    // Rotación con arrastre y zoom con rueda.
    if (canvas) {
        canvas.addEventListener('mousedown', (e) => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
        window.addEventListener('mouseup', () => { dragging = false; });
        window.addEventListener('mousemove', (e) => {
            if (!dragging || !group) return;
            group.rotation.y += (e.clientX - lastX) * 0.005;
            group.rotation.x += (e.clientY - lastY) * 0.005;
            lastX = e.clientX; lastY = e.clientY;
        });
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            zoom = Math.max(20, Math.min(160, zoom + Math.sign(e.deltaY) * 6));
        }, { passive: false });
    }

    socket.on('architecture_graph', (data) => {
        latest = data;
        if (open) rebuild();
    });
    socket.on('holo_open', show);
    socket.on('holo_close', hide);
    if (closeBtn) closeBtn.addEventListener('click', hide);
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && open) hide(); });
    window.addEventListener('resize', () => { if (open) resize(); });
    return { show, hide };
})();

socket.on('state_update', (data) => {
    // Actualizar estado
    currentState = data.status;
    // En nivel DEFCON rojo/violet la esfera mantiene el color de alarma.
    if (!defconOverride) {
        targetColor = { ...(stateColors[data.status] || stateColors.idle) };
    }
    targetParams = { ...(stateParams[data.status] || stateParams.idle) };

    // Actualizar textos
    statusEl.textContent = stateLabels[data.status] || 'EN ESPERA';

    // Actualizar badge socrático
    if (socraticBadgeEl) {
        if (data.socratic_mode) {
            socraticBadgeEl.style.display = 'inline-flex';
        } else {
            socraticBadgeEl.style.display = 'none';
        }
    }

    // Actualizar modelo en la GUI
    if (data.model) {
        modelNameEl.textContent = data.model;
        modelContainerEl.classList.add('active');
    } else {
        modelContainerEl.classList.remove('active');
    }

    if (data.status === 'thinking' && data.transcript) {
        transcriptEl.textContent = '"' + data.transcript + '"';
        addChatMessage('user', data.transcript);
    }
    if (data.status === 'speaking' && data.response) {
        responseEl.textContent = data.response;
        addChatMessage('jarvis', data.response);
        // Analizar y crear artefacto si existe bloque de código
        checkAndCreateArtifact(data.response);
    }

    // Limpiar temporizador previo si se interrumpe el estado idle
    if (clearTextTimer) {
        clearTimeout(clearTextTimer);
        clearTextTimer = null;
    }

    // Limpiar textos centrales cuando vuelve a idle tras 5 segundos
    if (data.status === 'idle') {
        clearTextTimer = setTimeout(() => {
            transcriptEl.textContent = '';
            responseEl.textContent = '';
            modelContainerEl.classList.remove('active');
            if (thoughtConsoleContainerEl) {
                thoughtConsoleContainerEl.style.display = 'none';
                thoughtLogEl.textContent = '';
                planStepsListEl.innerHTML = '';
            }
        }, 5000);
    }
});

socket.on('active_window_update', (data) => {
    if (data && data.app_name && data.app_name.trim() !== "") {
        activeWindowAppEl.textContent = data.app_name.toUpperCase();
        let title = data.title || "";
        if (title.length > 50) {
            title = title.substring(0, 47) + "...";
        }
        activeWindowTitleEl.textContent = title;
        activeWindowContainerEl.style.display = 'flex';
    } else {
        activeWindowContainerEl.style.display = 'none';
    }
});

socket.on('connect', () => {
    console.log('[JARVIS GUI] Conectado al servidor');
});

// Cuando el servidor backend se apaga repentinamente
socket.on('disconnect', () => {
    console.log('[JARVIS GUI] Desconectado del servidor. Iniciando apagado de la interfaz...');
    
    // Cambiamos el estado a "Apagado" visualmente
    currentState = 'idle';
    statusEl.textContent = "SISTEMA CAÍDO";
    statusEl.style.color = "red";
    
    // Intentar cerrar la pestaña después de 1.5 segundos
    setTimeout(() => {
        window.close();
        
        // Fallback por si el navegador bloquea auto-cierre
        document.body.innerHTML = `
            <div style="display:flex; justify-content:center; align-items:center; height:100vh; background:black; color:red; font-family:monospace; flex-direction:column;">
                <h1 style="font-size:3rem; margin:0;">[ CONEXIÓN PERDIDA ]</h1>
                <p>Jarvis se ha desconectado. Ya puedes cerrar esta pestaña.</p>
                <p style="color:gray; font-size:0.8rem;">(Tu navegador bloqueó el auto-cierre de seguridad)</p>
            </div>
        `;
    }, 1500);
});

// ==========================================
// LÓGICA DE CONTROL DEL PANEL DE ARTEFACTOS
// ==========================================
let currentArtifact = null;

function checkAndCreateArtifact(text) {
    if (!text) return;
    
    // Regex para encontrar el primer bloque de código markdown de lenguajes soportados
    const regex = /```(html|css|js|javascript|json|php|python|bat|cmd|batch)\s*([\s\S]*?)```/;
    const match = text.match(regex);
    
    if (match) {
        let lang = match[1].toLowerCase();
        let code = match[2];
        
        if (lang === 'js') lang = 'javascript';
        
        // Determinar icono y nombre por defecto
        let filename = 'documento.txt';
        let icon = '📁';
        if (lang === 'html') { filename = 'index.html'; icon = '🌐'; }
        else if (lang === 'css') { filename = 'estilos.css'; icon = '🎨'; }
        else if (lang === 'javascript') { filename = 'script.js'; icon = '⚡'; }
        else if (lang === 'json') { filename = 'datos.json'; icon = '📊'; }
        else if (lang === 'php') { filename = 'index.php'; icon = '🐘'; }
        else if (lang === 'python') { filename = 'programa.py'; icon = '🐍'; }
        else if (lang === 'bat' || lang === 'cmd' || lang === 'batch') { filename = 'macro.bat'; icon = '⚙️'; }
        
        currentArtifact = { language: lang, code: code, filename: filename };
        
        // Actualizar cabecera
        artifactFilenameEl.textContent = filename;
        artifactIconEl.textContent = icon;
        
        // Resaltado de sintaxis con Prism.js
        let prismLang = lang;
        if (lang === 'javascript') prismLang = 'js';
        artifactCodeDisplayEl.className = `language-${prismLang}`;
        artifactCodeDisplayEl.textContent = code.trim();
        if (window.Prism) {
            Prism.highlightElement(artifactCodeDisplayEl);
        }
        
        // Mostrar / Ocultar botón ejecutar
        if (lang === 'python' || lang === 'php' || lang === 'bat' || lang === 'cmd' || lang === 'batch') {
            btnRun.style.display = 'inline-block';
        } else {
            btnRun.style.display = 'none';
        }
        
        // Renderizar vista previa por defecto
        renderArtifactPreview();
        
        // Activar tab de vista previa al inicio
        btnTabPreview.classList.add('active');
        btnTabCode.classList.remove('active');
        artifactPreviewPaneEl.classList.add('active');
        artifactCodePaneEl.classList.remove('active');
        
        // Mostrar panel
        artifactsPanelEl.classList.add('active');
    }
}

function renderArtifactPreview() {
    if (!currentArtifact) return;
    
    const { language, code } = currentArtifact;
    artifactPreviewPaneEl.innerHTML = '';
    
    if (language === 'html' || language === 'javascript') {
        const iframe = document.createElement('iframe');
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        iframe.style.background = '#ffffff';
        iframe.sandbox = 'allow-scripts';
        
        if (language === 'html') {
            iframe.srcdoc = code;
        } else {
            iframe.srcdoc = `
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body { font-family: monospace; padding: 20px; background: #02070e; color: #00ff88; font-size: 0.85rem; line-height: 1.4; margin: 0; }
                        #console { white-space: pre-wrap; word-break: break-all; }
                        h3 { color: #00d4ff; margin-top: 0; font-family: sans-serif; border-bottom: 1px solid rgba(0, 212, 255, 0.2); padding-bottom: 8px; font-size: 1rem; }
                    </style>
                </head>
                <body>
                    <h3>Javascript Output</h3>
                    <div id="console"></div>
                    <script>
                        const consoleDiv = document.getElementById('console');
                        const log = console.log;
                        console.log = (...args) => {
                            consoleDiv.textContent += args.join(' ') + '\\n';
                            log(...args);
                        };
                        try {
                            ${code}
                        } catch(e) {
                            consoleDiv.innerHTML += '<span style="color:#ff3344;">[ERROR] ' + e.message + '</span>\\n';
                        }
                    </script>
                </body>
                </html>
            `;
        }
        artifactPreviewPaneEl.appendChild(iframe);
    } 
    else if (language === 'css') {
        const iframe = document.createElement('iframe');
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        iframe.style.background = '#ffffff';
        iframe.sandbox = 'allow-scripts';
        
        iframe.srcdoc = `
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: sans-serif; padding: 25px; margin: 0; background: #f8fafc; color: #1e293b; }
                    .demo-container { display: flex; flex-direction: column; gap: 20px; max-width: 500px; margin: 0 auto; }
                    .demo-section { padding: 15px; border: 1px dashed #cbd5e1; border-radius: 6px; background: #ffffff; }
                    .demo-title { font-size: 0.8rem; color: #64748b; text-transform: uppercase; margin-bottom: 10px; font-weight: bold; }
                </style>
                <style>
                    ${code}
                </style>
            </head>
            <body>
                <div class="demo-container">
                    <h3 style="margin:0;">Vista Previa de Estilos</h3>
                    <div class="demo-section">
                        <div class="demo-title">Botones (Buttons)</div>
                        <button class="btn btn-primary">Botón Principal</button>
                        <button class="btn btn-secondary">Botón Secundario</button>
                    </div>
                    <div class="demo-section">
                        <div class="demo-title">Tarjetas (Cards)</div>
                        <div class="card">
                            <h4 class="card-title">Título de Tarjeta</h4>
                            <p class="card-text">Párrafo de prueba para ver el estilo y maquetación de la tarjeta con tus estilos CSS.</p>
                            <a href="#" class="card-link">Leer más</a>
                        </div>
                    </div>
                    <div class="demo-section">
                        <div class="demo-title">Formularios / Inputs</div>
                        <input type="text" class="form-input" placeholder="Escribe algo aquí..." />
                    </div>
                </div>
            </body>
            </html>
        `;
        artifactPreviewPaneEl.appendChild(iframe);
    }
    else if (language === 'json') {
        try {
            const parsed = JSON.parse(code);
            artifactPreviewPaneEl.appendChild(buildJSONNode(parsed));
        } catch (e) {
            artifactPreviewPaneEl.innerHTML = `<div style="color:#ff3344; font-family:monospace; padding:10px;">Error al parsear JSON: ${e.message}</div>`;
        }
    } 
    else if (language === 'python' || language === 'php' || language === 'bat' || language === 'cmd' || language === 'batch') {
        const consoleHtml = `
            <div class="console-container">
                <div class="terminal-box">
                    <div class="terminal-header">Consola Virtual</div>
                    <div id="console-output" class="terminal-output">
                        <span class="info">Listo para ejecutar el script '${currentArtifact.filename}' en el servidor...</span>
                    </div>
                </div>
                <div id="console-plot" class="console-plot-preview" style="display: none;"></div>
            </div>
        `;
        artifactPreviewPaneEl.innerHTML = consoleHtml;
    }
}

function buildJSONNode(value, key = null) {
    const li = document.createElement('li');
    li.className = 'json-node';
    
    if (key !== null) {
        const keySpan = document.createElement('span');
        keySpan.className = 'json-key';
        keySpan.textContent = `"${key}": `;
        li.appendChild(keySpan);
    }
    
    if (value === null) {
        const valSpan = document.createElement('span');
        valSpan.className = 'json-value null';
        valSpan.textContent = 'null';
        li.appendChild(valSpan);
    } 
    else if (typeof value === 'object') {
        const isArray = Array.isArray(value);
        const collapsible = document.createElement('span');
        collapsible.className = 'json-collapsible';
        collapsible.textContent = isArray ? `Array[${value.length}]` : 'Object';
        li.appendChild(collapsible);
        
        const childTree = document.createElement('ul');
        childTree.className = 'json-tree';
        
        for (const k in value) {
            childTree.appendChild(buildJSONNode(value[k], k));
        }
        li.appendChild(childTree);
        
        collapsible.addEventListener('click', (e) => {
            e.stopPropagation();
            collapsible.classList.toggle('collapsed');
        });
    } 
    else {
        const valSpan = document.createElement('span');
        valSpan.className = `json-value ${typeof value}`;
        if (typeof value === 'string') {
            valSpan.textContent = `"${value}"`;
        } else {
            valSpan.textContent = value.toString();
        }
        li.appendChild(valSpan);
    }
    
    if (key === null) {
        const rootUl = document.createElement('ul');
        rootUl.className = 'json-tree';
        rootUl.appendChild(li);
        return rootUl;
    }
    return li;
}

// Botones e interacción de pestañas
btnTabPreview.addEventListener('click', () => {
    btnTabPreview.classList.add('active');
    btnTabCode.classList.remove('active');
    artifactPreviewPaneEl.classList.add('active');
    artifactCodePaneEl.classList.remove('active');
});

btnTabCode.addEventListener('click', () => {
    btnTabCode.classList.add('active');
    btnTabPreview.classList.remove('active');
    artifactCodePaneEl.classList.add('active');
    artifactPreviewPaneEl.classList.remove('active');
});

btnClose.addEventListener('click', () => {
    artifactsPanelEl.classList.remove('active');
});

btnCopy.addEventListener('click', () => {
    if (currentArtifact) {
        navigator.clipboard.writeText(currentArtifact.code).then(() => {
            const originalText = btnCopy.textContent;
            btnCopy.textContent = '¡Copiado!';
            setTimeout(() => btnCopy.textContent = originalText, 1500);
        });
    }
});

// Botón de ejecución socket
btnRun.addEventListener('click', () => {
    if (!currentArtifact) return;
    
    const consoleOutput = document.getElementById('console-output');
    const consolePlot = document.getElementById('console-plot');
    
    if (consoleOutput) {
        consoleOutput.innerHTML = '<span class="info">Ejecutando script, por favor espere...</span>';
    }
    if (consolePlot) {
        consolePlot.style.display = 'none';
        consolePlot.innerHTML = '';
    }
    
    btnRun.disabled = true;
    btnRun.textContent = 'Corriendo...';
    
    socket.emit('run_code_request', {
        language: currentArtifact.language,
        code: currentArtifact.code
    });
});

socket.on('run_code_response', (data) => {
    btnRun.disabled = false;
    btnRun.textContent = 'Ejecutar';
    
    const consoleOutput = document.getElementById('console-output');
    const consolePlot = document.getElementById('console-plot');
    
    if (!consoleOutput) return;
    
    consoleOutput.innerHTML = '';
    
    if (data.error) {
        consoleOutput.innerHTML = `<span class="stderr">${data.error}</span>`;
        return;
    }
    
    let contentHtml = '';
    if (data.stdout) {
        contentHtml += `<span class="stdout">${data.stdout}</span>`;
    }
    if (data.stderr) {
        contentHtml += `<span class="stderr">${data.stderr}</span>`;
    }
    
    if (!data.stdout && !data.stderr) {
        contentHtml += '<span class="info">[Ejecución concluida sin salida en consola]</span>';
    }
    
    consoleOutput.innerHTML = contentHtml;
    
    // Si hay una gráfica en base64 de Python
    if (data.image_base64 && consolePlot) {
        consolePlot.innerHTML = `<img src="data:image/png;base64,${data.image_base64}" alt="Gráfica Generada" />`;
        consolePlot.style.display = 'flex';
    }
});

// --- CENTINELA DE RED LOCAL ---
// ===== Radar visual de red =====
const networkRadar = (() => {
    const canvas = document.getElementById('network-radar');
    if (!canvas) return { setDevices: () => {} };
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const maxR = Math.min(cx, cy) - 8;
    let sweep = 0;
    let devices = [];

    const hash = (str) => {
        let h = 0;
        for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
        return h;
    };
    const posFor = (dev) => {
        const h = hash(dev.mac || dev.ip || '');
        const angle = (h % 360) * Math.PI / 180;
        const radius = (0.30 + ((h >>> 9) % 1000) / 1000 * 0.62) * maxR;
        return { angle, x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
    };
    const setDevices = (list) => {
        devices = (list || []).map(d => ({ ...d, ...posFor(d) }));
    };

    function draw() {
        ctx.clearRect(0, 0, W, H);
        // Anillos concéntricos
        ctx.strokeStyle = 'rgba(0, 212, 255, 0.16)';
        ctx.lineWidth = 1;
        for (let i = 1; i <= 3; i++) { ctx.beginPath(); ctx.arc(cx, cy, maxR * i / 3, 0, Math.PI * 2); ctx.stroke(); }
        // Cruz
        ctx.beginPath();
        ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy);
        ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR);
        ctx.stroke();
        // Barrido giratorio
        ctx.save();
        ctx.translate(cx, cy); ctx.rotate(sweep);
        const g = ctx.createLinearGradient(0, 0, maxR, 0);
        g.addColorStop(0, 'rgba(0, 255, 136, 0.0)');
        g.addColorStop(1, 'rgba(0, 255, 136, 0.30)');
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, maxR, -0.38, 0); ctx.closePath();
        ctx.fillStyle = g; ctx.fill();
        ctx.strokeStyle = 'rgba(0, 255, 136, 0.55)';
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(maxR, 0); ctx.stroke();
        ctx.restore();
        // Centro (router/gateway)
        ctx.fillStyle = '#00d4ff';
        ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI * 2); ctx.fill();
        // Blips
        const now = performance.now() / 1000;
        devices.forEach(d => {
            const da = ((d.angle - sweep) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
            const lit = da < 0.5 ? (1 - da / 0.5) : 0;            // glow al pasar el barrido
            const c = d.known ? [0, 212, 255] : [255, 60, 80];
            const pulse = d.known ? 1 : (0.6 + 0.4 * Math.abs(Math.sin(now * 3)));
            const r = (d.known ? 3 : 4) + lit * 3;
            ctx.beginPath();
            ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.5 + 0.5 * lit) * pulse})`;
            ctx.arc(d.x, d.y, r, 0, Math.PI * 2); ctx.fill();
            if (lit > 0.05 || !d.known) {
                ctx.beginPath();
                ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${0.45 * Math.max(lit, d.known ? 0 : 0.5)})`;
                ctx.arc(d.x, d.y, r + 4, 0, Math.PI * 2); ctx.stroke();
            }
        });
        sweep = (sweep + 0.02) % (Math.PI * 2);
        requestAnimationFrame(draw);
    }
    draw();
    return { setDevices };
})();

socket.on('network_devices_update', (devices) => {
    networkRadar.setDevices(devices);
    const deviceListEl = document.getElementById('network-device-list');
    const statusEl = document.getElementById('sentinel-status');
    if (!deviceListEl) return;
    
    deviceListEl.innerHTML = '';
    
    if (statusEl) {
        statusEl.textContent = devices.length > 0 ? 'ACTIVO' : 'ESCANEANDO';
        statusEl.style.color = devices.length > 0 ? '#00ff88' : '#888888';
    }
    
    if (!devices || devices.length === 0) {
        deviceListEl.innerHTML = '<div style="color:#64748b; font-size:0.7rem; font-style:italic; text-align:center; padding:10px;">Escaneando red local...</div>';
        return;
    }
    
    // Ordenar: dispositivos extraños (unknown) primero
    const sorted = [...devices].sort((a, b) => (a.known === b.known) ? 0 : a.known ? 1 : -1);
    
    sorted.forEach(dev => {
        const item = document.createElement('div');
        item.className = `device-item ${dev.known ? '' : 'strange'}`;
        
        const info = document.createElement('div');
        info.className = 'device-info';
        
        const name = document.createElement('div');
        name.className = 'device-name';
        name.textContent = dev.name || (dev.known ? 'Dispositivo Confiado' : 'Dispositivo Extraño');
        
        const ip = document.createElement('div');
        ip.className = 'device-ip';
        ip.textContent = dev.ip;
        
        const mac = document.createElement('div');
        mac.className = 'device-mac';
        mac.textContent = dev.mac.toUpperCase();
        
        info.appendChild(name);
        info.appendChild(ip);
        info.appendChild(mac);
        
        const action = document.createElement('div');
        action.className = 'device-action';
        
        if (dev.known) {
            const badge = document.createElement('span');
            badge.className = 'badge-trusted';
            badge.textContent = 'CONFIADO';
            action.appendChild(badge);
        } else {
            const btn = document.createElement('button');
            btn.className = 'btn-trust';
            btn.textContent = 'Confiar';
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const customName = prompt(`¿Confiar en el dispositivo con IP ${dev.ip} y MAC ${dev.mac.toUpperCase()}?\nIngresa un nombre descriptivo:`, "Mi Dispositivo");
                if (customName !== null) {
                    const finalName = customName.trim() || "Dispositivo Confiado";
                    socket.emit('trust_device', { mac: dev.mac, name: finalName });
                }
            });
            action.appendChild(btn);
        }
        
        item.appendChild(info);
        item.appendChild(action);
        deviceListEl.appendChild(item);
    });
});

// --- PRIVACY GUARD ---
socket.on('privacy_update', (data) => {
    const findingsListEl = document.getElementById('privacy-findings-list');
    const statusEl = document.getElementById('privacy-status');
    if (!findingsListEl) return;
    
    findingsListEl.innerHTML = '';
    
    if (statusEl) {
        if (data.status === 'vulnerable') {
            statusEl.textContent = 'VULNERABLE';
            statusEl.style.color = '#ff3344';
            statusEl.style.textShadow = '0 0 10px #ff3344';
        } else {
            statusEl.textContent = 'PROTEGIDO';
            statusEl.style.color = '#00ff88';
            statusEl.style.textShadow = '0 0 10px #00ff88';
        }
    }
    
    if (!data.findings || data.findings.length === 0) {
        findingsListEl.innerHTML = '<div style="color:#64748b; font-size:0.7rem; font-style:italic; text-align:center; padding:10px; width:100%;">No se detectaron riesgos.</div>';
        return;
    }
    
    data.findings.forEach(f => {
        const item = document.createElement('div');
        item.className = 'device-item strange';
        item.style.padding = '8px';
        
        const info = document.createElement('div');
        info.className = 'device-info';
        
        const typeEl = document.createElement('div');
        typeEl.className = 'device-name';
        typeEl.style.color = '#ff3344';
        typeEl.style.fontSize = '0.75rem';
        typeEl.textContent = f.type;
        
        const fileEl = document.createElement('div');
        fileEl.className = 'device-ip';
        fileEl.style.fontSize = '0.65rem';
        fileEl.textContent = `${f.file}:${f.line}`;
        
        const snippetEl = document.createElement('div');
        snippetEl.className = 'device-mac';
        snippetEl.style.fontSize = '0.65rem';
        snippetEl.textContent = f.snippet;
        
        info.appendChild(typeEl);
        info.appendChild(fileEl);
        info.appendChild(snippetEl);
        
        const action = document.createElement('div');
        action.className = 'device-action';
        
        const btn = document.createElement('button');
        btn.className = 'btn-trust';
        btn.style.borderColor = 'rgba(255, 51, 68, 0.4)';
        btn.style.color = '#ff3344';
        btn.textContent = 'Ignorar';
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm(`¿Ignorar este secreto en ${f.file}?\nSe agregará a la lista de ignorados.`)) {
                socket.emit('ignore_secret', { hash: f.hash });
            }
        });
        
        action.appendChild(btn);
        
        item.appendChild(info);
        item.appendChild(action);
        findingsListEl.appendChild(item);
    });
});

// --- DEPENDENCY PATCHER ---
socket.on('vulnerability_update', (data) => {
    const findingsListEl = document.getElementById('vulnerability-findings-list');
    const statusEl = document.getElementById('vulnerability-status');
    if (!findingsListEl) return;
    
    findingsListEl.innerHTML = '';
    
    if (statusEl) {
        if (data.status === 'vulnerable') {
            statusEl.textContent = 'VULNERABLE';
            statusEl.style.color = '#ff3344';
            statusEl.style.textShadow = '0 0 10px #ff3344';
        } else {
            statusEl.textContent = 'SEGURO';
            statusEl.style.color = '#00ff88';
            statusEl.style.textShadow = '0 0 10px #00ff88';
        }
    }
    
    if (!data.findings || data.findings.length === 0) {
        findingsListEl.innerHTML = '<div style="color:#64748b; font-size:0.7rem; font-style:italic; text-align:center; padding:10px; width:100%;">Todas las dependencias están seguras.</div>';
        return;
    }
    
    data.findings.forEach(f => {
        const item = document.createElement('div');
        item.className = `vuln-item ${f.status}`;
        
        const info = document.createElement('div');
        info.className = 'vuln-info';
        
        const pkgEl = document.createElement('div');
        pkgEl.className = 'vuln-package';
        pkgEl.textContent = f.package;
        
        const versionsSpan = document.createElement('span');
        versionsSpan.className = 'vuln-versions';
        versionsSpan.textContent = `${f.current_version} → ${f.latest_version}`;
        pkgEl.appendChild(versionsSpan);
        
        const cvesEl = document.createElement('div');
        cvesEl.className = 'vuln-cves';
        cvesEl.textContent = f.vulnerabilities.map(v => v.id).join(', ');
        
        info.appendChild(pkgEl);
        info.appendChild(cvesEl);
        
        const action = document.createElement('div');
        action.className = 'vuln-action';
        
        if (f.status === 'conflictive') {
            const badge = document.createElement('span');
            badge.className = 'badge-conflict';
            badge.textContent = 'CONFLICTO';
            badge.title = 'Actualización rompió los tests unitarios. Revertida.';
            action.appendChild(badge);
        } else if (f.status === 'patching') {
            const badge = document.createElement('span');
            badge.className = 'badge-patching';
            badge.textContent = 'PARCHEANDO...';
            action.appendChild(badge);
        } else {
            const btn = document.createElement('button');
            btn.className = 'btn-patch';
            btn.textContent = 'Parchear';
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm(`¿Aplicar parche de seguridad para ${f.package} a la versión ${f.latest_version}?\nSe ejecutarán tests locales de validación.`)) {
                    // Actualizar el estado visual del botón
                    btn.disabled = true;
                    btn.textContent = 'Parcheando...';
                    item.className = 'vuln-item patching';
                    action.innerHTML = '<span class="badge-patching">PARCHEANDO...</span>';
                    
                    socket.emit('apply_patch', { package: f.package, version: f.latest_version });
                }
            });
            action.appendChild(btn);
        }
        
        item.appendChild(info);
        item.appendChild(action);
        findingsListEl.appendChild(item);
    });
});

// --- JARVIS INTEGRITY WATCHDOG ---
socket.on('jarvis_health_update', (data) => {
    const findingsListEl = document.getElementById('integrity-findings-list');
    const statusEl = document.getElementById('integrity-status');
    if (!findingsListEl) return;
    
    findingsListEl.innerHTML = '';
    
    if (statusEl) {
        const status = data.status.toUpperCase();
        statusEl.textContent = status;
        if (status === 'CRITICAL') {
            statusEl.style.color = '#ff3344';
            statusEl.style.textShadow = '0 0 10px #ff3344';
        } else if (status === 'WARNING') {
            statusEl.style.color = '#ffaa00';
            statusEl.style.textShadow = '0 0 10px #ffaa00';
        } else {
            statusEl.textContent = 'SEGURO';
            statusEl.style.color = '#00ff88';
            statusEl.style.textShadow = '0 0 10px #00ff88';
        }
    }
    
    // Crear items para el reporte
    // 1. Análisis de Sintaxis
    const syntaxItem = document.createElement('div');
    syntaxItem.className = 'health-item';
    const syntaxFails = data.syntax_failures || [];
    syntaxItem.innerHTML = `
        <div class="health-row">
            <span class="health-name">Sintaxis de Código</span>
            <span class="health-badge ${syntaxFails.length === 0 ? 'ok' : 'critical'}">
                ${syntaxFails.length === 0 ? 'OK' : 'FALLO'}
            </span>
        </div>
        <div class="health-detail ${syntaxFails.length > 0 ? 'error' : ''}">
            ${syntaxFails.length === 0 ? 'Todos los archivos Python válidos' : `${syntaxFails.length} archivo(s) con errores`}
        </div>
    `;
    findingsListEl.appendChild(syntaxItem);
    
    // 2. Carga de Herramientas
    const toolsItem = document.createElement('div');
    toolsItem.className = 'health-item';
    const toolsFails = data.tools_failures || [];
    toolsItem.innerHTML = `
        <div class="health-row">
            <span class="health-name">Módulos Tools</span>
            <span class="health-badge ${toolsFails.length === 0 ? 'ok' : 'critical'}">
                ${toolsFails.length === 0 ? 'OK' : 'ERROR'}
            </span>
        </div>
        <div class="health-detail ${toolsFails.length > 0 ? 'error' : ''}">
            ${toolsFails.length === 0 ? 'Herramientas importadas sin fallos' : `${toolsFails.length} fallo(s) de importación`}
        </div>
    `;
    findingsListEl.appendChild(toolsItem);
    
    // 3. Variables de Entorno
    const envItem = document.createElement('div');
    envItem.className = 'health-item';
    const envCheck = data.env_check || [];
    const unconfigured = envCheck.filter(item => !item.configured);
    const criticalMissing = unconfigured.filter(item => ['OPENAI_API_KEY', 'GOOGLE_API_KEY'].includes(item.name));
    
    let envStatus = 'ok';
    let envLabel = 'OK';
    if (criticalMissing.length > 0) {
        envStatus = 'critical';
        envLabel = 'FALTA API';
    } else if (unconfigured.length > 0) {
        envStatus = 'warning';
        envLabel = 'INCOMPLETO';
    }
    
    envItem.innerHTML = `
        <div class="health-row">
            <span class="health-name">Claves y Entorno</span>
            <span class="health-badge ${envStatus}">
                ${envLabel}
            </span>
        </div>
        <div class="health-detail">
            ${unconfigured.length === 0 ? 'Todas las variables configuradas' : `Falta(n) ${unconfigured.length} clave(s) (.env)`}
        </div>
    `;
    findingsListEl.appendChild(envItem);
    
    // 4. Pruebas Unitarias
    const testsItem = document.createElement('div');
    testsItem.className = 'health-item';
    const tests = data.test_results || {};
    const testsPassed = tests.passed;
    
    testsItem.innerHTML = `
        <div class="health-row">
            <span class="health-name">Tests Unitarios</span>
            <span class="health-badge ${testsPassed ? 'ok' : 'warning'}">
                ${testsPassed ? 'PASANDO' : 'FALLANDO'}
            </span>
        </div>
        <div class="health-detail">
            ${tests.ran > 0 ? `${tests.ran - tests.failures - tests.errors}/${tests.ran} tests pasados` : 'Ejecutando tests de integridad...'}
        </div>
    `;
    findingsListEl.appendChild(testsItem);
});

// Healthcheck de arranque (generado por main.py al iniciar Jarvis)
socket.on('startup_healthcheck', (data) => {
    const listEl = document.getElementById('startup-health-list');
    const statusEl = document.getElementById('startup-health-status');
    if (!listEl) return;

    listEl.innerHTML = '';

    // Estado global: healthy | degraded | error
    if (statusEl) {
        const status = (data.status || '').toLowerCase();
        if (status === 'error') {
            statusEl.textContent = 'ERROR';
            statusEl.style.color = '#ff3344';
            statusEl.style.textShadow = '0 0 10px #ff3344';
        } else if (status === 'degraded') {
            statusEl.textContent = 'DEGRADADO';
            statusEl.style.color = '#ffaa00';
            statusEl.style.textShadow = '0 0 10px #ffaa00';
        } else if (status === 'healthy') {
            statusEl.textContent = 'OPERATIVO';
            statusEl.style.color = '#00ff88';
            statusEl.style.textShadow = '0 0 10px #00ff88';
        } else {
            statusEl.textContent = '—';
            statusEl.style.color = '#888';
            statusEl.style.textShadow = 'none';
        }
    }

    const addItem = (name, badgeClass, badgeLabel, detail, isError) => {
        const item = document.createElement('div');
        item.className = 'health-item';
        item.innerHTML = `
            <div class="health-row">
                <span class="health-name">${name}</span>
                <span class="health-badge ${badgeClass}">${badgeLabel}</span>
            </div>
            <div class="health-detail ${isError ? 'error' : ''}">${detail}</div>
        `;
        listEl.appendChild(item);
    };

    // 1. Tools
    const tools = data.tools || {};
    const toolsFailed = tools.failed || [];
    addItem(
        'Herramientas',
        toolsFailed.length === 0 ? 'ok' : 'critical',
        toolsFailed.length === 0 ? 'OK' : 'FALLO',
        toolsFailed.length === 0
            ? `${tools.loaded || 0} herramientas cargadas`
            : `${toolsFailed.length} fallida(s) de ${(tools.loaded || 0) + toolsFailed.length}`,
        toolsFailed.length > 0
    );

    // 2. Servicios (disabled NO degrada)
    const services = data.services || {};
    const states = Object.values(services);
    const running = states.filter(s => s === 'running').length;
    const stopped = states.filter(s => s === 'stopped').length;
    const disabled = states.filter(s => s === 'disabled').length;
    addItem(
        'Servicios',
        stopped === 0 ? 'ok' : 'warning',
        stopped === 0 ? 'OK' : 'PARCIAL',
        `${running} activos · ${stopped} detenidos · ${disabled} desactivados`,
        false
    );

    // 3. Claves API (solo presencia, nunca el valor)
    const keys = data.api_keys || [];
    const missing = keys.filter(k => !k.configured);
    addItem(
        'Claves API',
        missing.length === 0 ? 'ok' : 'warning',
        missing.length === 0 ? 'OK' : 'INCOMPLETO',
        missing.length === 0
            ? `${keys.length} clave(s) presentes`
            : `Falta(n) ${missing.length} de ${keys.length}`,
        false
    );

    // 4. SQLite / Memoria
    const db = data.database || {};
    addItem(
        'SQLite / Memoria',
        db.ok ? 'ok' : 'critical',
        db.ok ? 'OK' : 'ERROR',
        db.ok ? 'Base de datos accesible' : (db.error || 'Base de datos inaccesible'),
        !db.ok
    );
});

// Manejadores para la Consola de Pensamiento y Planificación
socket.on('agent_thought', (data) => {
    if (!thoughtConsoleContainerEl || !thoughtLogEl || !thoughtConsoleIndicatorEl) return;
    
    // Al recibir un pensamiento, mostrar la consola
    thoughtConsoleContainerEl.style.display = 'block';
    
    // Si el temporizador de limpieza estaba activo por volver a idle, cancelarlo
    if (clearTextTimer) {
        clearTimeout(clearTextTimer);
        clearTextTimer = null;
    }
    
    if (data.type === 'tool_start') {
        thoughtConsoleIndicatorEl.textContent = 'PENSANDO / USANDO HERRAMIENTA';
        thoughtConsoleIndicatorEl.style.color = '#ffc800';
        
        let toolText = `> Decidiendo usar la herramienta: [${data.tool}]\n`;
        if (data.tool_input) {
            toolText += `  Parámetros: ${data.tool_input}\n`;
        }
        if (data.thought) {
            // Limpiar log interno de la acción
            let cleanThought = data.thought.replace(/Action:[\s\S]*/g, '').trim();
            if (cleanThought) {
                toolText += `  Razón: ${cleanThought}\n`;
            }
        }
        thoughtLogEl.textContent = toolText;
    } else if (data.type === 'tool_end') {
        let outputText = thoughtLogEl.textContent;
        let shortOutput = data.output || "";
        if (shortOutput.length > 250) {
            shortOutput = shortOutput.substring(0, 247) + "...";
        }
        outputText += `> Salida de la herramienta:\n  ${shortOutput}\n\n`;
        thoughtLogEl.textContent = outputText;
    } else if (data.type === 'agent_finish') {
        thoughtConsoleIndicatorEl.textContent = 'EJECUCIÓN COMPLETADA';
        thoughtConsoleIndicatorEl.style.color = '#00ff88';
        let outputText = thoughtLogEl.textContent;
        outputText += `> Respuesta final del agente obtenida.\n`;
        thoughtLogEl.textContent = outputText;
    }
    
    // Auto-scroll
    thoughtConsoleContainerEl.scrollTop = thoughtConsoleContainerEl.scrollHeight;
});

socket.on('plan_update', (data) => {
    if (!thoughtConsoleContainerEl || !planStepsListEl || !thoughtConsoleIndicatorEl) return;
    
    thoughtConsoleContainerEl.style.display = 'block';
    thoughtConsoleIndicatorEl.textContent = data.completed ? 'PLAN FINALIZADO' : 'PLAN EN EJECUCIÓN';
    thoughtConsoleIndicatorEl.style.color = data.completed ? '#00ff88' : '#ffc800';
    
    // Si el temporizador de limpieza estaba activo por volver a idle, cancelarlo
    if (clearTextTimer) {
        clearTimeout(clearTextTimer);
        clearTextTimer = null;
    }
    
    planStepsListEl.innerHTML = '';
    
    if (data.steps && data.steps.length > 0) {
        data.steps.forEach(step => {
            const stepEl = document.createElement('div');
            stepEl.style.fontSize = '0.75rem';
            stepEl.style.display = 'flex';
            stepEl.style.alignItems = 'center';
            stepEl.style.gap = '8px';
            stepEl.style.padding = '4px 0';
            
            let statusIcon = '⚪';
            let textColor = '#888888';
            let textWeight = 'normal';
            let textDecoration = 'none';
            let animationClass = '';
            
            if (step.status === 'in_progress') {
                statusIcon = '⚙️';
                textColor = '#ffc800';
                textWeight = 'bold';
                animationClass = 'loading-rotate';
            } else if (step.status === 'completed') {
                statusIcon = '✅';
                textColor = '#00ff88';
                textDecoration = 'line-through';
            } else if (step.status === 'failed') {
                statusIcon = '❌';
                textColor = '#ff3333';
                textWeight = 'bold';
            }
            
            const iconSpan = document.createElement('span');
            iconSpan.textContent = statusIcon;
            if (animationClass) {
                iconSpan.classList.add(animationClass);
            }
            
            const descSpan = document.createElement('span');
            descSpan.textContent = `${step.id}. ${step.description}`;
            descSpan.style.color = textColor;
            descSpan.style.fontWeight = textWeight;
            descSpan.style.textDecoration = textDecoration;
            
            if (step.status === 'in_progress') {
                descSpan.style.animation = 'blink 1.5s infinite';
            }
            
            stepEl.appendChild(iconSpan);
            stepEl.appendChild(descSpan);
            planStepsListEl.appendChild(stepEl);
        });
    }
    
    // Auto-scroll
    thoughtConsoleContainerEl.scrollTop = thoughtConsoleContainerEl.scrollHeight;
});

// --- MANEJADORES DE CONFIGURACIÓN ---
if (settingsBtn && settingsPanelEl) {
    settingsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        settingsPanelEl.classList.add('active');
        socket.emit('get_whisper_config');
        socket.emit('get_services_config');
    });
}

if (settingsBtnClose && settingsPanelEl) {
    settingsBtnClose.addEventListener('click', (e) => {
        e.stopPropagation();
        settingsPanelEl.classList.remove('active');
    });
}

// Cerrar panel si se hace clic fuera del mismo
document.addEventListener('click', (e) => {
    if (settingsPanelEl && settingsPanelEl.classList.contains('active')) {
        if (!settingsPanelEl.contains(e.target) && e.target !== settingsBtn) {
            settingsPanelEl.classList.remove('active');
        }
    }
});

if (whisperModelSelect) {
    whisperModelSelect.addEventListener('change', () => {
        const selectedModel = whisperModelSelect.value;
        if (whisperStatusValue) {
            whisperStatusValue.textContent = 'Actualizando...';
            whisperStatusValue.style.color = '#ffc800';
        }
        socket.emit('set_whisper_model', { model: selectedModel });
    });
}

socket.on('whisper_config_response', (data) => {
    if (whisperModelSelect) {
        whisperModelSelect.value = data.configured_model;
    }
    if (whisperStatusValue) {
        if (data.loaded) {
            whisperStatusValue.textContent = `Cargado: ${data.model_name} (${data.device})`;
            whisperStatusValue.style.color = '#00ff88';
        } else {
            whisperStatusValue.textContent = `No cargado (En espera | Config: ${data.configured_model})`;
            whisperStatusValue.style.color = '#888888';
        }
    }
});

const serviceNames = {
    network_sentinel: "Centinela de Red",
    api_sentinel: "Centinela de APIs",
    vulnerability_patcher: "Reparador de Dependencias",
    integrity_sentinel: "Sentinel de Integridad",
    test_watcher: "Centinela de Pruebas",
    task_scheduler: "Planificador de Tareas",
    telegram_bot: "Bot de Telegram",
    log_maintenance: "Mantenimiento de Logs",
    privacy_monitor: "Privacy Monitor"
};

socket.on('services_config_response', (data) => {
    const listEl = document.getElementById('settings-services-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    
    const order = [
        "network_sentinel",
        "api_sentinel",
        "vulnerability_patcher",
        "integrity_sentinel",
        "test_watcher",
        "task_scheduler",
        "telegram_bot",
        "log_maintenance",
        "privacy_monitor"
    ];
    
    order.forEach(service => {
        if (!(service in data)) return;
        const status = data[service];
        const friendlyName = serviceNames[service] || service;
        const isEnabled = status !== 'disabled';
        
        const itemEl = document.createElement('div');
        itemEl.className = 'settings-service-item';
        
        let badgeClass = 'stopped';
        let badgeText = 'DETENIDO';
        if (status === 'running') {
            badgeClass = 'running';
            badgeText = 'ACTIVO';
        } else if (status === 'disabled') {
            badgeClass = 'disabled';
            badgeText = 'DESACTIVADO';
        }
        
        itemEl.innerHTML = `
            <div class="service-meta">
                <span class="service-name-label">${friendlyName}</span>
                <span class="service-status-badge ${badgeClass}">${badgeText}</span>
            </div>
            <label class="switch">
                <input type="checkbox" id="toggle-${service}" ${isEnabled ? 'checked' : ''}>
                <span class="slider"></span>
            </label>
        `;
        
        listEl.appendChild(itemEl);
        
        const checkbox = itemEl.querySelector(`#toggle-${service}`);
        checkbox.addEventListener('change', () => {
            const isChecked = checkbox.checked;
            checkbox.disabled = true;
            socket.emit('toggle_service', { service: service, enable: isChecked });
        });
    });
});

// ==========================================
// SUIT UP — Secuencia de Arranque Animada
// ==========================================

const suitupOverlayEl = document.getElementById('suitup-overlay');
const suitupCounterEl = document.getElementById('suitup-counter');
const suitupProgressBarEl = document.getElementById('suitup-progress-bar');
const suitupProgressLabelEl = document.getElementById('suitup-progress-label');
const suitupFinalEl = document.getElementById('suitup-final');
const suitupFinalItemsEl = document.getElementById('suitup-final-items');
const suitupFinalLevelEl = document.getElementById('suitup-final-level');
const suitupSkipHintEl = document.getElementById('suitup-skip-hint');

let suitupActive = false;
let suitupCompleted = false;

// Ocultar overlay al cargar si no hay secuencia activa (por ejemplo, al recargar)
// El overlay se mantendrá visible esperando el primer evento suitup_start.
// Si no llega en 8s, lo ocultamos automáticamente.
let suitupAutoHideTimer = setTimeout(() => {
    if (!suitupActive && suitupOverlayEl && !suitupCompleted) {
        dismissSuitup();
    }
}, 8000);

function dismissSuitup() {
    if (suitupCompleted) return;
    suitupCompleted = true;
    suitupActive = false;

    // Notificar al backend para que detenga la secuencia de telemetría
    socket.emit('skip_suitup');

    if (suitupOverlayEl) {
        suitupOverlayEl.classList.add('hidden');
        // Remover del DOM después de la transición
        setTimeout(() => {
            if (suitupOverlayEl.parentNode) {
                suitupOverlayEl.style.display = 'none';
            }
        }, 1000);
    }
    console.log('[JARVIS GUI] Suit Up sequence dismissed.');
}

// Interrupción con ESC o clic
if (suitupSkipHintEl) {
    suitupSkipHintEl.addEventListener('click', dismissSuitup);
}

if (suitupOverlayEl) {
    suitupOverlayEl.addEventListener('click', (e) => {
        if (suitupActive && (e.target === suitupOverlayEl || e.target.id === 'suitup-scanlines' || e.target.id === 'suitup-skip-hint')) {
            dismissSuitup();
        }
    });
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && suitupActive) {
        dismissSuitup();
    }
});

// Handler: Inicio de secuencia
socket.on('suitup_start', (data) => {
    console.log('[JARVIS GUI] Suit Up sequence started.', data);
    suitupActive = true;
    suitupCompleted = false;

    // Cancelar auto-hide
    if (suitupAutoHideTimer) {
        clearTimeout(suitupAutoHideTimer);
        suitupAutoHideTimer = null;
    }

    // Asegurar visibilidad
    if (suitupOverlayEl) {
        suitupOverlayEl.style.display = 'flex';
        suitupOverlayEl.classList.remove('hidden');
    }

    // Resetear estado visual
    if (suitupCounterEl) {
        suitupCounterEl.textContent = 'INITIALIZING...';
        suitupCounterEl.classList.add('active-phase');
    }

    // Resetear cards
    for (let i = 1; i <= 4; i++) {
        const card = document.getElementById(`suitup-phase-${i}`);
        if (card) {
            card.classList.remove('active', 'completed');
            const itemsContainer = card.querySelector('.phase-items');
            if (itemsContainer) itemsContainer.innerHTML = '';
        }
    }

    // Resetear barra de progreso
    if (suitupProgressBarEl) suitupProgressBarEl.style.width = '0%';
    if (suitupProgressLabelEl) suitupProgressLabelEl.textContent = '0%';

    // Ocultar panel final
    if (suitupFinalEl) suitupFinalEl.style.display = 'none';
    if (suitupFinalItemsEl) suitupFinalItemsEl.innerHTML = '';
    if (suitupFinalLevelEl) {
        suitupFinalLevelEl.textContent = '';
        suitupFinalLevelEl.className = '';
    }
});

// Handler: Fase de telemetría
socket.on('suitup_phase', (data) => {
    if (suitupCompleted) return;

    console.log(`[JARVIS GUI] Suit Up phase ${data.phase}: ${data.title}`);

    const phaseNum = data.phase;
    const progress = data.progress || 0;

    // Actualizar contador
    if (suitupCounterEl) {
        suitupCounterEl.textContent = `PHASE ${phaseNum}/${data.total_phases}: ${data.title}`;
        suitupCounterEl.classList.add('active-phase');
    }

    // Actualizar barra de progreso
    if (suitupProgressBarEl) suitupProgressBarEl.style.width = `${progress}%`;
    if (suitupProgressLabelEl) suitupProgressLabelEl.textContent = `${progress}%`;

    // Fases 1-4 van al grid
    if (phaseNum >= 1 && phaseNum <= 4) {
        // Marcar fases anteriores como completadas
        for (let i = 1; i < phaseNum; i++) {
            const prevCard = document.getElementById(`suitup-phase-${i}`);
            if (prevCard) {
                prevCard.classList.remove('active');
                prevCard.classList.add('completed');
            }
        }

        // Activar card actual
        const card = document.getElementById(`suitup-phase-${phaseNum}`);
        if (card) {
            card.classList.add('active');

            // Actualizar icono y título
            const iconEl = card.querySelector('.phase-icon');
            const titleEl = card.querySelector('.phase-title');
            if (iconEl && data.icon) iconEl.textContent = data.icon;
            if (titleEl && data.title) titleEl.textContent = data.title;

            // Renderizar items con stagger animation
            const itemsContainer = card.querySelector('.phase-items');
            if (itemsContainer && data.items) {
                itemsContainer.innerHTML = '';
                data.items.forEach((item, index) => {
                    const itemEl = document.createElement('div');
                    itemEl.classList.add('phase-item');
                    itemEl.style.animationDelay = `${index * 0.15}s`;
                    itemEl.innerHTML = `
                        <span class="item-label">${item.label}</span>
                        <span class="item-value status-${item.status || 'ok'}">${item.value}</span>
                    `;
                    itemsContainer.appendChild(itemEl);
                });
            }
        }
    }

    // Fase 5: Final Status
    if (phaseNum === 5) {
        // Marcar todas las cards del grid como completadas
        for (let i = 1; i <= 4; i++) {
            const prevCard = document.getElementById(`suitup-phase-${i}`);
            if (prevCard) {
                prevCard.classList.remove('active');
                prevCard.classList.add('completed');
            }
        }

        // Mostrar panel final
        if (suitupFinalEl) suitupFinalEl.style.display = 'block';
        if (suitupFinalItemsEl && data.items) {
            suitupFinalItemsEl.innerHTML = '';
            data.items.forEach((item, index) => {
                const itemEl = document.createElement('div');
                itemEl.classList.add('phase-item');
                itemEl.style.animationDelay = `${index * 0.2}s`;
                itemEl.innerHTML = `
                    <span class="item-label">${item.label}</span>
                    <span class="item-value status-${item.status || 'ok'}">${item.value}</span>
                `;
                suitupFinalItemsEl.appendChild(itemEl);
            });
        }

        // Nivel de estado
        if (suitupFinalLevelEl && data.level) {
            suitupFinalLevelEl.textContent = data.level;
            const levelClass = data.level === 'NOMINAL' ? 'level-nominal' :
                               data.level === 'ADVISORY' ? 'level-advisory' : 'level-critical';
            suitupFinalLevelEl.className = levelClass;
        }

        // Actualizar contador final
        if (suitupCounterEl) {
            suitupCounterEl.textContent = 'ALL SYSTEMS ONLINE';
            suitupCounterEl.classList.remove('active-phase');
        }
    }
});

// Handler: Secuencia completada
socket.on('suitup_complete', (data) => {
    console.log('[JARVIS GUI] Suit Up sequence complete!', data);

    // Breve pausa para que el usuario vea el resultado final
    setTimeout(() => {
        dismissSuitup();
    }, 1200);
});

// Handler: Secuencia cancelada
socket.on('suitup_cancelled', (data) => {
    console.log('[JARVIS GUI] Suit Up sequence cancelled!', data);
    dismissSuitup();
});

// ==========================================
// SMART CLIPBOARD — Notificación HUD Toast
// ==========================================

const clipboardToastEl = document.getElementById('clipboard-toast');
const clipboardTypeLabelEl = document.getElementById('clipboard-type-label');
const clipboardPreviewTextEl = document.getElementById('clipboard-preview-text');
const clipboardActionBtn = document.getElementById('clipboard-action-btn');
const clipboardIgnoreBtn = document.getElementById('clipboard-ignore-btn');
const clipboardCloseBtn = document.getElementById('clipboard-close-btn');

let clipboardToastTimeout = null;
let currentClipboardType = null;

function showClipboardToast(data) {
    if (!clipboardToastEl) return;

    currentClipboardType = data.type;

    // Rellenar etiquetas según tipo
    if (data.type === 'traceback') {
        clipboardTypeLabelEl.textContent = '❌ EXCEPCIÓN DETECTADA';
        clipboardActionBtn.textContent = 'Solucionar Error';
        clipboardActionBtn.style.display = 'inline-block';
    } else if (data.type === 'url') {
        clipboardTypeLabelEl.textContent = '📡 ENLACE WEB DETECTADO';
        clipboardActionBtn.textContent = 'Resumir Contenido';
        clipboardActionBtn.style.display = 'inline-block';
    } else if (data.type === 'code') {
        clipboardTypeLabelEl.textContent = '💻 CÓDIGO DETECTADO';
        clipboardActionBtn.textContent = 'Explicar Código';
        clipboardActionBtn.style.display = 'none';
    }

    clipboardPreviewTextEl.textContent = data.preview;

    // Mostrar el Toast removiendo 'hidden'
    clipboardToastEl.classList.remove('hidden');

    // Auto-ocultar tras 12 segundos
    if (clipboardToastTimeout) {
        clearTimeout(clipboardToastTimeout);
    }
    clipboardToastTimeout = setTimeout(hideClipboardToast, 12000);
}

function hideClipboardToast() {
    if (clipboardToastEl) {
        clipboardToastEl.classList.add('hidden');
    }
    if (clipboardToastTimeout) {
        clearTimeout(clipboardToastTimeout);
        clipboardToastTimeout = null;
    }
}

// Escuchar evento del SocketIO
socket.on('clipboard_detection', (data) => {
    console.log('[JARVIS GUI] Clipboard content detected:', data);
    showClipboardToast(data);
});

// Eventos de botones
if (clipboardCloseBtn) {
    clipboardCloseBtn.addEventListener('click', hideClipboardToast);
}

if (clipboardIgnoreBtn) {
    clipboardIgnoreBtn.addEventListener('click', hideClipboardToast);
}

if (clipboardActionBtn) {
    clipboardActionBtn.addEventListener('click', () => {
        if (!currentClipboardType) return;
        
        if (currentClipboardType === 'traceback') {
            socket.emit('solve_clipboard_error_request');
        } else if (currentClipboardType === 'url') {
            socket.emit('summarize_clipboard_url_request');
        }
        
        hideClipboardToast();
    });
}

