"""
tools/voice.py
=============================================
Sistema de voz de Jarvis con 3 capas.
Orden de preferencia (si una falla, salta a la siguiente):

    1) ElevenLabs (voz premium Martin Osborne, online)
    2) edge-tts   (voz neural AlvaroNeural de Microsoft, online)
    3) pyttsx3    (voz offline Pablo, siempre funciona)

Función pública principal:
    speak(text)  ->  no bloqueante, lanza la voz en un hilo

Variables de entorno necesarias (en .env):
    ELEVENLABS_API_KEY   -> clave de ElevenLabs
    ELEVENLABS_VOICE_ID  -> voice_id de Martin Osborne (u otra voz)
=============================================
"""

import os
import uuid
import tempfile
import asyncio
import threading

import edge_tts
import pygame
import pyttsx3
from elevenlabs.client import ElevenLabs

