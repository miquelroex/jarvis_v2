import sys
import os
import unittest
import time
import wave
import struct
import pygame
from pathlib import Path

# Asegurar que el root del proyecto está en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tools.voice import stop_speak

class TestBargeIn(unittest.TestCase):
    def setUp(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error as e:
            # En CI headless (sin tarjeta/endpoint de audio) WASAPI no encuentra
            # dispositivo. El test es dependiente de hardware: lo saltamos.
            self.skipTest(f"No hay dispositivo de audio disponible: {e}")
        self.dummy_wav = os.path.join(project_root, "tests", "dummy_test_sound.wav")
        self.create_silent_wav(self.dummy_wav)

    def tearDown(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.unload()
        if os.path.exists(self.dummy_wav):
            try:
                os.remove(self.dummy_wav)
            except Exception:
                pass

    def create_silent_wav(self, path):
        # Generar un archivo de sonido de 1 segundo de silencio
        with wave.open(path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            # 22050 muestras de silencio (0)
            for _ in range(22050):
                w.writeframes(struct.pack('<h', 0))

    def test_stop_speak_halts_playback(self):
        # 1. Cargar y empezar a reproducir el audio
        pygame.mixer.music.load(self.dummy_wav)
        pygame.mixer.music.play()
        
        # Debe estar sonando
        self.assertTrue(pygame.mixer.music.get_busy())
        
        # 2. Detener la reproducción
        stop_speak()
        
        # Ya no debe estar sonando
        self.assertFalse(pygame.mixer.music.get_busy())

if __name__ == "__main__":
    unittest.main()
