import unittest
from unittest.mock import patch, MagicMock
import time
import numpy as np
import pyaudio

# Asegurar import de voice
from tools.voice import _vad_monitor_thread, stop_speak

class TestVADSystem(unittest.TestCase):
    @patch('pygame.mixer.get_init')
    @patch('pygame.mixer.music.get_busy')
    @patch('tools.voice.stop_speak')
    @patch('pyaudio.PyAudio')
    def test_vad_interruption(self, mock_pyaudio_class, mock_stop_speak, mock_get_busy, mock_get_init):
        # 1. Configurar mocks de pygame
        mock_get_init.return_value = True
        
        # get_busy devolverá True las primeras 15 veces, luego False para detener el bucle.
        # Filtramos por hilo principal para evitar interferencias del hilo _global_key_listener.
        import threading
        main_thread = threading.main_thread()
        busy_states = [True] * 15 + [False]
        mock_get_busy.side_effect = lambda: (busy_states.pop(0) if busy_states else False) if threading.current_thread() is main_thread else False

        # 2. Configurar mock de PyAudio y Stream
        mock_pyaudio_instance = MagicMock()
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        
        mock_stream = MagicMock()
        mock_pyaudio_instance.open.return_value = mock_stream

        # Generar frames simulados
        # Los primeros 6 frames son silencio (RMS bajo ~ 40)
        silence_frame = np.zeros(1024, dtype=np.int16)
        silence_data = silence_frame.tobytes()

        # Los siguientes frames son de alta energía (RMS alto ~ 2000)
        voice_frame = np.sin(np.linspace(0, 2 * np.pi, 1024)) * 2000.0
        voice_frame = voice_frame.astype(np.int16)
        voice_data = voice_frame.tobytes()

        # Configurar stream.read para devolver frames en orden
        read_returns = [silence_data] * 6 + [voice_data] * 6
        mock_stream.read.side_effect = lambda chunk, exception_on_overflow=False: read_returns.pop(0) if read_returns else silence_data

        # 3. Ejecutar la función de monitoreo VAD
        # Configurar logging para ver la salida
        import logging
        logging.basicConfig(level=logging.INFO)
        
        print("Running VAD monitor thread...")
        _vad_monitor_thread()

        # 4. Verificar resultados
        print(f"get_init call count: {mock_get_init.call_count}")
        print(f"get_busy call count: {mock_get_busy.call_count}")
        print(f"stop_speak call count: {mock_stop_speak.call_count}")
        mock_stop_speak.assert_called_once()
        mock_pyaudio_instance.open.assert_called_once()
        mock_stream.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
