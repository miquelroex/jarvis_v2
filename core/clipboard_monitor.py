"""
core/clipboard_monitor.py — Smart Clipboard Monitor daemon for JARVIS.

Runs in the background, checks the system clipboard for new entries, parses them
to identify tracebacks, URLs, or raw code blocks, emits events to the Flask-SocketIO GUI,
and triggers proactive speech when the assistant is idle.
"""

import re
import time
import threading
import logging
import os
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_monitor_thread = None
_last_clipboard_hash = None
_enabled = True

# Max clipboard content size to prevent memory spikes (200 KB)
MAX_CLIPBOARD_SIZE = 200 * 1024

# Detection regular expressions
RE_TRACEBACK = re.compile(r"(Traceback \(most recent call last\):|File \".+?\", line \d+)", re.IGNORECASE)
RE_URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
RE_CODE = re.compile(
    r"\b(def|class|import|from|return|if __name__ ==|const|let|var|function|async|await|public|private|void)\b|[{};]",
    re.IGNORECASE
)

# Global variable to store the latest active clipboard detection for voice/UI confirmation
LAST_DETECTION = None  # Dict: {"type": "traceback"|"url"|"code", "text": "...", "timestamp": float}


def is_clipboard_monitor_running() -> bool:
    """Returns True if the clipboard monitor thread is alive."""
    global _monitor_thread
    return _monitor_thread is not None and _monitor_thread.is_alive()


def detect_type(text: str) -> str | None:
    """
    Parses text content to determine if it contains a python traceback, URL, or code.
    """
    if not text:
        return None

    # 1. Python Traceback
    if RE_TRACEBACK.search(text):
        return "traceback"

    # 2. Plain URL
    stripped = text.strip()
    if RE_URL.match(stripped):
        return "url"

    # 3. Raw Code block (requires at least 2 occurrences of typical keywords or matching curly braces)
    matches = RE_CODE.findall(text)
    if len(matches) >= 2 or ("{" in text and "}" in text and len(text.splitlines()) > 2):
        return "code"

    return None


def read_clipboard_win32() -> str | None:
    """Reads unicode or text data from the Windows clipboard using pywin32."""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                return data
            elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
                if isinstance(data, bytes):
                    return data.decode("utf-8", errors="ignore")
                return data
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        logger.debug(f"[Clipboard] Error reading from win32clipboard: {e}")
    return None


def read_clipboard_tkinter() -> str | None:
    """Fallback reader using tkinter clipboard functionality."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        data = root.clipboard_get()
        root.destroy()
        return data
    except Exception as e:
        logger.debug(f"[Clipboard] Error reading from tkinter clipboard: {e}")
    return None


def read_clipboard() -> str | None:
    """Safely reads the system clipboard text with a win32 reader and a tkinter fallback."""
    data = read_clipboard_win32()
    if data is not None:
        return data
    return read_clipboard_tkinter()


def monitor_loop(socketio) -> None:
    """Background loop that periodically polls the clipboard and emits detection events."""
    global _last_clipboard_hash, LAST_DETECTION
    logger.info("[Clipboard] Clipboard monitor background loop started.")

    while not _stop_event.is_set():
        try:
            text = read_clipboard()
            if text and len(text.strip()) > 0 and len(text) < MAX_CLIPBOARD_SIZE:
                # Calculate MD5 hash to detect actual modifications
                text_hash = hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()

                if text_hash != _last_clipboard_hash:
                    _last_clipboard_hash = text_hash
                    detected_type = detect_type(text)

                    if detected_type:
                        logger.info(f"[Clipboard] Detected clipboard content type: '{detected_type}'")

                        # Store detection globally
                        LAST_DETECTION = {
                            "type": detected_type,
                            "text": text,
                            "timestamp": time.time()
                        }

                        # Emit SocketIO payload
                        preview = text[:150] + ("..." if len(text) > 150 else "")
                        payload = {
                            "type": detected_type,
                            "preview": preview,
                            "length": len(text)
                        }
                        socketio.emit("clipboard_detection", payload)

                        # Trigger proactive audio alert ONLY if Jarvis is completely idle
                        try:
                            from gui.app import jarvis_state
                            from tools.voice import speak

                            if jarvis_state.get("status") == "idle":
                                if detected_type == "traceback":
                                    speak("Señor, he detectado un error en el portapapeles. ¿Desea que intente solucionarlo?", disable_vad=True)
                                elif detected_type == "url":
                                    speak("Señor, he detectado un enlace en el portapapeles. ¿Desea que lo resuma?", disable_vad=True)
                        except Exception as ve:
                            logger.error(f"[Clipboard] Voice prompt warning: {ve}")

        except Exception as e:
            logger.error(f"[Clipboard] Exception in monitor loop: {e}")

        # Sleep using threading event wait for instant shutdown
        _stop_event.wait(1.0)

    logger.info("[Clipboard] Clipboard monitor background loop stopped.")


def start_clipboard_monitor() -> None:
    """Starts the clipboard monitor background daemon thread if enabled."""
    global _monitor_thread, _stop_event, _enabled

    _enabled = os.getenv("JARVIS_CLIPBOARD_MONITOR_ENABLED", "true").lower() in ("true", "1", "yes")
    if not _enabled:
        logger.info("[Clipboard] Clipboard monitor is disabled in configuration (.env).")
        return

    if _monitor_thread is not None and _monitor_thread.is_alive():
        logger.warning("[Clipboard] Clipboard monitor is already running.")
        return

    from gui.app import socketio as gui_socketio
    _stop_event.clear()
    _monitor_thread = threading.Thread(
        target=monitor_loop,
        args=(gui_socketio,),
        name="ClipboardMonitorThread",
        daemon=True
    )
    _monitor_thread.start()
    logger.info("[Clipboard] Clipboard monitor service started successfully.")


def stop_clipboard_monitor() -> None:
    """Clean stop of the clipboard monitor daemon."""
    global _monitor_thread
    if _monitor_thread is not None and _monitor_thread.is_alive():
        _stop_event.set()
        logger.info("[Clipboard] Stopping clipboard monitor service...")
