"""
core/inbox.py — Bandeja de entrada (Inbox) de Jarvis.

Captura rápida de notas, ideas y tareas por voz o texto, persistidas en la
misma base de datos SQLite que la memoria (tabla propia `inbox_items`).

Módulo ligero (sqlite3 + core.memory para la ruta de la BD): no importa
langchain ni tools, por lo que es testeable de forma aislada.
"""
import sys
import sqlite3
import logging
from datetime import datetime, timezone

from core.memory import get_db_path, init_db


def _emit_update():
    """Emite la bandeja actual a la GUI, SOLO si gui.app ya está cargado.

    Evita importar gui.app (que arrastra dependencias pesadas) cuando no hay GUI
    en marcha, así los tests no se ven afectados."""
    mod = sys.modules.get("gui.app")
    if mod is None:
        return
    try:
        mod.socketio.emit("inbox_update", get_inbox_items())
    except Exception:
        pass


def _connect() -> sqlite3.Connection:
    """Abre la conexión a la BD y asegura que existe la tabla del inbox."""
    init_db()  # asegura la BD y las tablas base de la memoria
    conn = sqlite3.connect(get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inbox_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TEXT,
            done INTEGER DEFAULT 0
        )
    """)
    return conn


def add_inbox_item(content: str) -> bool:
    """Añade una nota a la bandeja. Retorna True si se guardó, False si vacía/error."""
    content = (content or "").strip()
    if not content:
        return False
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO inbox_items (content, created_at, done) VALUES (?, ?, 0)",
            (content, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logging.info(f"[Inbox] Nota añadida: '{content}'")
        _emit_update()
        return True
    except Exception as e:
        logging.error(f"[Inbox] Error al añadir nota: {e}")
        return False
    finally:
        conn.close()


def get_inbox_items(include_done: bool = False) -> list:
    """Retorna las notas de la bandeja (por defecto solo las pendientes)."""
    conn = _connect()
    try:
        if include_done:
            query = "SELECT id, content, created_at, done FROM inbox_items ORDER BY id"
        else:
            query = "SELECT id, content, created_at, done FROM inbox_items WHERE done = 0 ORDER BY id"
        rows = conn.execute(query).fetchall()
        return [
            {"id": r[0], "content": r[1], "created_at": r[2], "done": bool(r[3])}
            for r in rows
        ]
    except Exception as e:
        logging.error(f"[Inbox] Error al leer la bandeja: {e}")
        return []
    finally:
        conn.close()


def mark_inbox_done(item_id: int) -> bool:
    """Marca una nota como completada. Retorna True si se actualizó algún registro."""
    conn = _connect()
    try:
        cur = conn.execute("UPDATE inbox_items SET done = 1 WHERE id = ?", (item_id,))
        conn.commit()
        if cur.rowcount > 0:
            _emit_update()
        return cur.rowcount > 0
    except Exception as e:
        logging.error(f"[Inbox] Error al marcar nota como hecha: {e}")
        return False
    finally:
        conn.close()


def clear_inbox(only_done: bool = False) -> int:
    """Elimina notas de la bandeja. Si only_done, solo las completadas.

    Retorna el número de notas eliminadas.
    """
    conn = _connect()
    try:
        if only_done:
            cur = conn.execute("DELETE FROM inbox_items WHERE done = 1")
        else:
            cur = conn.execute("DELETE FROM inbox_items")
        conn.commit()
        _emit_update()
        return cur.rowcount
    except Exception as e:
        logging.error(f"[Inbox] Error al vaciar la bandeja: {e}")
        return 0
    finally:
        conn.close()
