// ==========================================
// JARVIS — Interfaz gráfica animada
// ==========================================

// --- CONFIGURACIÓN ---
const canvas = document.getElementById('jarvis-canvas');
const ctx = canvas.getContext('2d');

// Elementos de texto
const statusEl = document.getElementById('status');
const transcriptEl = document.getElementById('transcript');
const responseEl = document.getElementById('response');

let logicalWidth = window.innerWidth;
let logicalHeight = window.innerHeight;

// Ajustar canvas al tamaño de la ventana con soporte Retina (DPR)
function resize() {
    logicalWidth = window.innerWidth;
    logicalHeight = window.innerHeight;
    const dpr = window.devicePixelRatio || 1;
    
    // Resolución real internamente
    canvas.width = logicalWidth * dpr;
    canvas.height = logicalHeight * dpr;
    
    // Tamaño lógico en CSS
    canvas.style.width = `${logicalWidth}px`;
    canvas.style.height = `${logicalHeight}px`;
    
    // Escalar el contexto bidimensional a la proporción de pixeles
    ctx.scale(dpr, dpr);
}
window.addEventListener('resize', resize);
resize();

// --- COLORES SEGÚN ESTADO ---
const stateColors = {
    idle:      { r: 0, g: 212, b: 255 },   // Azul cian
    listening: { r: 0, g: 150, b: 255 },   // Azul brillante
    thinking:  { r: 255, g: 200, b: 0 },   // Amarillo/dorado
    speaking:  { r: 0, g: 255, b: 136 }    // Verde
};

const stateLabels = {
    idle:      'EN ESPERA',
    listening: 'ESCUCHANDO...',
    thinking:  'PROCESANDO...',
    speaking:  'RESPONDIENDO'
};

let currentState = 'idle';
let currentColor = { ...stateColors.idle };
let targetColor = { ...stateColors.idle };

// --- PARTÍCULAS ---
const particles = [];
const PARTICLE_COUNT = 1500; // Muchos puntitos, polvo holográfico

// Cada partícula es un punto que flota alrededor del orbe
for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
        angle: Math.random() * Math.PI * 2,       
        radius: 60 + Math.pow(Math.random(), 1.2) * 280, // Circular, centrado
        // Velocidad relajada para que parezca movimiento inteligente
        speed: (0.0010 + Math.random() * 0.002) * (Math.random() > 0.5 ? 1 : -1), 
        size: 0.5 + Math.random() * 1.6,           
        opacity: 0.3 + Math.random() * 0.7,        
        // Frecuencia suave para ola interior
        stretchFreq: 0.0003 + Math.random() * 0.001,
        stretchPhase: Math.random() * Math.PI * 2,
        x: 0, 
        y: 0
    });
}

// --- ORBE CENTRAL ---
let orbePulse = 0;  // Controla el "latido" del orbe

// --- FUNCIÓN PRINCIPAL DE ANIMACIÓN ---
function animate() {
    // Limpiar el canvas
    ctx.clearRect(0, 0, logicalWidth, logicalHeight);

    const cx = logicalWidth / 2;   
    const cy = logicalHeight / 2;  

    // Interpolar color suavemente
    currentColor.r += (targetColor.r - currentColor.r) * 0.05;
    currentColor.g += (targetColor.g - currentColor.g) * 0.05;
    currentColor.b += (targetColor.b - currentColor.b) * 0.05;

    const r = Math.round(currentColor.r);
    const g = Math.round(currentColor.g);
    const b = Math.round(currentColor.b);

    // Pulso (Súper natural y rítmico, como una respiración en reposo)
    orbePulse += 0.02;
    const pulseSize = currentState === 'idle' ? 4 : 10;
    const pulse = Math.sin(orbePulse) * pulseSize;

    // --- Dibujar el resplandor de fondo (Casi invisible) ---
    const glowRadius = 450 + pulse * 2;
    const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowRadius);
    glow.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.03)`); 
    glow.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, 0.01)`); 
    glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, logicalWidth, logicalHeight);

    // --- Dibujar el orbe central (Holograma sutil) ---
    const orbeRadius = 120 + pulse * 1.5;
    const orbeGradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, orbeRadius);
    orbeGradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.3)`); 
    orbeGradient.addColorStop(0.6, `rgba(${r}, ${g}, ${b}, 0.05)`);
    orbeGradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
    ctx.beginPath();
    ctx.arc(cx, cy, orbeRadius, 0, Math.PI * 2);
    ctx.fillStyle = orbeGradient;
    ctx.fill();

    // Tiempo global y rotación de cámara
    const time = Date.now();
    const globalSpin = time * 0.00015; // Un giro global majestuoso y sumamente lento

    // Deformación de respiración orgánica global - Movimientos lentos y fluidos
    const rx = 1 + Math.sin(time * 0.00015) * 0.08;
    const ry = 1 + Math.cos(time * 0.0001) * 0.06;

    // --- Dibujar partículas y calcular coordenadas ---
    particles.forEach(p => {
        p.angle += p.speed;

        // Suave agitación cuando procesa información
        const agitation = currentState === 'idle' ? 1 : 2;
        
        // Movimiento vibratorio radial relajado
        const wave = Math.sin(time * p.stretchFreq + p.stretchPhase) * 15 * agitation;
        const currentRadius = p.radius + pulse * 1.2 * agitation + wave;

        // Ecuación final con giro global y "respiración volumétrica" (rx, ry)
        p.x = cx + Math.cos(p.angle + globalSpin) * currentRadius * rx;
        p.y = cy + Math.sin(p.angle + globalSpin) * currentRadius * ry;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${p.opacity * 0.9})`;
        ctx.fill();
    });

    // --- Líneas de conexión (Hilos neuronales) ---
    ctx.lineWidth = 0.6; // Un poco más visibles
    for (let i = 0; i < particles.length; i++) {
        // Aumentamos a 50 partículas colindantes (recuperamos parte de las uniones perdidas)
        const maxJ = Math.min(particles.length, i + 50); 
        for (let j = i + 1; j < maxJ; j++) {
            const pi = particles[i];
            const pj = particles[j];
            
            const dist = Math.hypot(pi.x - pj.x, pi.y - pj.y);

            // Umbral de distancia a 45 para devolver algunos puentes obvios entre grupos de nodos
            if (dist < 45) {
                ctx.beginPath();
                ctx.moveTo(pi.x, pi.y);
                ctx.lineTo(pj.x, pj.y);
                ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.4 * (1 - dist / 45)})`;
                ctx.stroke();
            }
        }
    }

    requestAnimationFrame(animate);
}

// Arrancar la animación
animate();

// --- SOCKET.IO: recibir estados de Jarvis ---
const socket = io();
let clearTextTimer = null; // Guardará el ID del temporizador

const chatHistoryEl = document.getElementById('chat-history');

function addChatMessage(role, text) {
    if (!text) return;
    const msg = document.createElement('div');
    msg.classList.add('chat-msg', role);
    msg.textContent = text;
    chatHistoryEl.appendChild(msg);
    // Baja el scroll hasta el final suavemente
    chatHistoryEl.scrollTo({ top: chatHistoryEl.scrollHeight, behavior: 'smooth' });
}

socket.on('state_update', (data) => {
    // Actualizar estado
    currentState = data.status;
    targetColor = { ...stateColors[data.status] } || stateColors.idle;

    // Actualizar textos
    statusEl.textContent = stateLabels[data.status] || 'EN ESPERA';

    if (data.status === 'thinking' && data.transcript) {
        transcriptEl.textContent = '"' + data.transcript + '"';
        addChatMessage('user', data.transcript);
    }
    if (data.status === 'speaking' && data.response) {
        responseEl.textContent = data.response;
        addChatMessage('jarvis', data.response);
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
        }, 5000);
    }
});

socket.on('connect', () => {
    console.log('[JARVIS GUI] Conectado al servidor');
});

// Cuando el servidor backend se apaga repentinamente (Por la Opción 2 del BAT)
socket.on('disconnect', () => {
    console.log('[JARVIS GUI] Desconectado del servidor. Iniciando apagado de la interfaz...');
    
    // Cambiamos el estado a "Apagado" visualmente
    currentState = 'idle';
    statusEl.textContent = "SISTEMA CAÍDO";
    statusEl.style.color = "red";
    
    // Intentar cerrar la pestaña después de 1.5 segundos
    setTimeout(() => {
        // Ejecuta el cierre del navegador
        window.close();
        
        // Si el navegador bloquea window.close() por motivos de seguridad, mostramos este fallo
        document.body.innerHTML = `
            <div style="display:flex; justify-content:center; align-items:center; height:100vh; background:black; color:red; font-family:monospace; flex-direction:column;">
                <h1 style="font-size:3rem; margin:0;">[ CONEXIÓN PERDIDA ]</h1>
                <p>Jarvis se ha desconectado. Ya puedes cerrar esta pestaña.</p>
                <p style="color:gray; font-size:0.8rem;">(Tu navegador bloqueó el auto-cierre de seguridad)</p>
            </div>
        `;
    }, 1500);
});