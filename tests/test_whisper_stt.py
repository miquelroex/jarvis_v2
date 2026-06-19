"""Tests para core.whisper_stt con mocks (sin descargar modelos reales)."""

import io
import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

import speech_recognition as sr


def _make_fake_audio() -> sr.AudioData:
    """Crea un AudioData falso para testing (1s de silencio 16kHz mono)."""
    sample_rate = 16000
    sample_width = 2
    num_samples = sample_rate
    raw_data = b'\x00' * (num_samples * sample_width)
    return sr.AudioData(raw_data, sample_rate, sample_width)


class TestWhisperLazyLoading(unittest.TestCase):
    """Verifica que el modelo se carga lazy y se cachea correctamente."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    def test_no_model_loaded_at_import(self):
        """El modelo no debe cargarse al importar el módulo."""
        import core.whisper_stt as ws
        self.assertIsNone(ws._model)
        self.assertIsNone(ws._model_name)

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_model_loaded_on_first_transcription(self, mock_cls):
        """El modelo se carga en la primera transcripción, no antes."""
        import core.whisper_stt as ws

        mock_model_instance = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "hola mundo"
        mock_model_instance.transcribe.return_value = (
            [mock_segment],
            MagicMock(),
        )
        mock_cls.return_value = mock_model_instance

        self.assertIsNone(ws._model)

        audio = _make_fake_audio()
        result = ws.transcribe_audio(audio, google_fallback=False)

        mock_cls.assert_called_once_with("small", device="cpu", compute_type="int8")
        self.assertEqual(result, "hola mundo")
        self.assertIsNotNone(ws._model)
        self.assertEqual(ws._model_name, "small")


class TestModelCaching(unittest.TestCase):
    """Verifica que el modelo se cachea y no se recarga innecesariamente."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_model_cached_on_second_call(self, mock_cls):
        """El modelo se crea una sola vez para múltiples transcripciones."""
        import core.whisper_stt as ws

        mock_model_instance = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "test"
        mock_model_instance.transcribe.return_value = ([mock_segment], MagicMock())
        mock_cls.return_value = mock_model_instance

        audio = _make_fake_audio()
        ws.transcribe_audio(audio, google_fallback=False)
        ws.transcribe_audio(audio, google_fallback=False)
        ws.transcribe_audio(audio, google_fallback=False)

        # El constructor solo debe llamarse 1 vez
        mock_cls.assert_called_once()
        # Pero transcribe se llama 3 veces
        self.assertEqual(mock_model_instance.transcribe.call_count, 3)

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_model_reloads_on_env_change(self, mock_cls):
        """Si JARVIS_WHISPER_MODEL cambia, se descarga el anterior y carga el nuevo."""
        import core.whisper_stt as ws

        mock_model_instance = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "test"
        mock_model_instance.transcribe.return_value = ([mock_segment], MagicMock())
        mock_cls.return_value = mock_model_instance

        audio = _make_fake_audio()

        # Primera transcripción con "small"
        ws.transcribe_audio(audio, google_fallback=False)
        self.assertEqual(ws._model_name, "small")
        self.assertEqual(mock_cls.call_count, 1)

        # Cambiar a "medium" vía env
        with patch.dict(os.environ, {"JARVIS_WHISPER_MODEL": "medium"}):
            ws.transcribe_audio(audio, google_fallback=False)
            self.assertEqual(ws._model_name, "medium")
            self.assertEqual(mock_cls.call_count, 2)

            # Llamar de nuevo con "medium" — no recarga
            ws.transcribe_audio(audio, google_fallback=False)
            self.assertEqual(mock_cls.call_count, 2)


class TestTranscription(unittest.TestCase):
    """Verifica la lógica de transcripción principal."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
        "JARVIS_WHISPER_LANGUAGE": "es",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_transcribe_joins_segments(self, mock_cls):
        """Múltiples segmentos se unen con espacio."""
        import core.whisper_stt as ws

        seg1 = MagicMock()
        seg1.text = "hola"
        seg2 = MagicMock()
        seg2.text = "qué tal"
        seg3 = MagicMock()
        seg3.text = "estás"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([seg1, seg2, seg3], MagicMock())
        mock_cls.return_value = mock_model

        audio = _make_fake_audio()
        result = ws.transcribe_audio(audio, google_fallback=False)

        self.assertEqual(result, "hola qué tal estás")

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_transcribe_passes_language_and_prompt(self, mock_cls):
        """Se pasan language e initial_prompt al modelo."""
        import core.whisper_stt as ws

        mock_model = MagicMock()
        seg = MagicMock()
        seg.text = "test"
        mock_model.transcribe.return_value = ([seg], MagicMock())
        mock_cls.return_value = mock_model

        audio = _make_fake_audio()
        with patch.dict(os.environ, {"JARVIS_WHISPER_LANGUAGE": "es"}):
            ws.transcribe_audio(audio, google_fallback=False)

        call_kwargs = mock_model.transcribe.call_args
        self.assertEqual(call_kwargs.kwargs.get("language") or call_kwargs[1].get("language"), "es")
        self.assertIn("beam_size", call_kwargs.kwargs or call_kwargs[1])

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_empty_transcription_raises(self, mock_cls):
        """Texto vacío de Whisper lanza ValueError (para trigger de fallback)."""
        import core.whisper_stt as ws

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_cls.return_value = mock_model

        audio = _make_fake_audio()
        with self.assertRaises(ValueError):
            ws.transcribe_audio(audio, google_fallback=False)


class TestGoogleFallback(unittest.TestCase):
    """Verifica el fallback a Google Web Speech API."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    @patch("core.whisper_stt._google_transcribe")
    def test_fallback_on_whisper_error(self, mock_google, mock_cls):
        """Si Whisper falla, se usa Google como fallback."""
        import core.whisper_stt as ws

        mock_cls.side_effect = RuntimeError("CUDA out of memory")
        mock_google.return_value = "texto de google"

        audio = _make_fake_audio()
        result = ws.transcribe_audio(audio, google_fallback=True)

        mock_google.assert_called_once_with(audio)
        self.assertEqual(result, "texto de google")

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_no_fallback_raises(self, mock_cls):
        """Sin fallback, el error se propaga."""
        import core.whisper_stt as ws

        mock_cls.side_effect = RuntimeError("CUDA error")

        audio = _make_fake_audio()
        with self.assertRaises(RuntimeError):
            ws.transcribe_audio(audio, google_fallback=False)

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    @patch("core.whisper_stt._google_transcribe")
    def test_fallback_on_empty_result(self, mock_google, mock_cls):
        """Si Whisper devuelve vacío, se activa el fallback."""
        import core.whisper_stt as ws

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_cls.return_value = mock_model
        mock_google.return_value = "fallback text"

        audio = _make_fake_audio()
        result = ws.transcribe_audio(audio, google_fallback=True)

        mock_google.assert_called_once()
        self.assertEqual(result, "fallback text")


class TestUnloadModel(unittest.TestCase):
    """Verifica la descarga explícita del modelo."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    def test_unload_clears_cache(self):
        """unload_model() libera el modelo cacheado."""
        import core.whisper_stt as ws

        ws._model = MagicMock()
        ws._model_name = "small"

        ws.unload_model()

        self.assertIsNone(ws._model)
        self.assertIsNone(ws._model_name)

    def test_unload_when_no_model(self):
        """unload_model() no falla si no hay modelo cargado."""
        import core.whisper_stt as ws
        ws.unload_model()
        self.assertIsNone(ws._model)


class TestGetModelInfo(unittest.TestCase):
    """Verifica get_model_info()."""

    def test_info_no_model_loaded(self):
        """Info correcta sin modelo cargado."""
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

        with patch.dict(os.environ, {"JARVIS_WHISPER_MODEL": "medium"}):
            info = ws.get_model_info()

        self.assertFalse(info["loaded"])
        self.assertIsNone(info["model_name"])
        self.assertEqual(info["configured_model"], "medium")

    def test_info_with_model_loaded(self):
        """Info correcta con modelo cargado."""
        import core.whisper_stt as ws
        ws._model = MagicMock()
        ws._model_name = "small"

        info = ws.get_model_info()

        self.assertTrue(info["loaded"])
        self.assertEqual(info["model_name"], "small")


class TestDeviceSelection(unittest.TestCase):
    """Verifica la selección de dispositivo y compute_type."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cuda",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_cuda_uses_float16(self, mock_cls):
        """CUDA usa float16 por defecto."""
        import core.whisper_stt as ws

        mock_cls.return_value = MagicMock()
        ws._get_model()

        mock_cls.assert_called_once_with("small", device="cuda", compute_type="float16")

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_cpu_uses_int8(self, mock_cls):
        """CPU usa int8 por defecto."""
        import core.whisper_stt as ws

        mock_cls.return_value = MagicMock()
        ws._get_model()

        mock_cls.assert_called_once_with("small", device="cpu", compute_type="int8")

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "auto",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_auto_device_uses_float16(self, mock_cls):
        """Auto device usa float16 (CTranslate2 elige GPU si hay)."""
        import core.whisper_stt as ws

        mock_cls.return_value = MagicMock()
        ws._get_model()

        mock_cls.assert_called_once_with("small", device="auto", compute_type="float16")

    @patch.dict(os.environ, {
        "JARVIS_WHISPER_MODEL": "small",
        "JARVIS_WHISPER_DEVICE": "cpu",
        "JARVIS_WHISPER_COMPUTE_TYPE": "float32",
    })
    @patch("core.whisper_stt._WhisperModelClass")
    def test_custom_compute_type(self, mock_cls):
        """Se puede forzar un compute_type personalizado."""
        import core.whisper_stt as ws

        mock_cls.return_value = MagicMock()
        ws._get_model()

        mock_cls.assert_called_once_with("small", device="cpu", compute_type="float32")


class TestImportError(unittest.TestCase):
    """Verifica el comportamiento cuando faster-whisper no está instalado."""

    def setUp(self):
        import core.whisper_stt as ws
        ws._model = None
        ws._model_name = None

    def test_raises_import_error_when_not_installed(self):
        """Si faster-whisper no está disponible, lanza ImportError."""
        import core.whisper_stt as ws

        original_class = ws._WhisperModelClass
        ws._WhisperModelClass = None
        try:
            with self.assertRaises(ImportError):
                ws._get_model()
        finally:
            ws._WhisperModelClass = original_class


if __name__ == '__main__':
    unittest.main()
