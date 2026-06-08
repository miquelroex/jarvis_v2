import os
import sqlite3
from datetime import datetime, timezone
import logging

DB_DIR = "memory"
DB_NAME = "jarvis.db"
DEFAULT_DB_PATH = os.path.join(DB_DIR, DB_NAME)

_db_path = DEFAULT_DB_PATH

def set_db_path(path: str):
    """Establece la ruta de la base de datos (útil para pruebas unitarias)."""
    global _db_path
    _db_path = path

def get_db_path() -> str:
    """Retorna la ruta actual de la base de datos."""
    return _db_path

def init_db(db_path: str = None):
    """Inicializa la base de datos SQLite y la tabla de memorias."""
    global _db_path
    if db_path is not None:
        _db_path = db_path
    
    # Crear directorio si no es una base de datos en memoria y no existe
    if _db_path != ":memory:":
        dir_name = os.path.dirname(_db_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            logging.info(f"Creada la carpeta para la base de datos: {dir_name}")

    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            source TEXT,
            content TEXT UNIQUE,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    logging.info(f"Base de datos de memoria inicializada en: {_db_path}")

def save_memory(content: str, category: str = "general", source: str = "user") -> bool:
    """
    Guarda una nueva memoria.
    Retorna True si tiene éxito, False si ya existía (violación de UNIQUE) u ocurre un error.
    """
    content = content.strip()
    if not content:
        return False
        
    init_db()  # Asegurar que esté inicializada
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    created_at = datetime.now(timezone.utc).isoformat()
    
    try:
        cursor.execute(
            "INSERT INTO memories (category, source, content, created_at) VALUES (?, ?, ?, ?)",
            (category, source, content, created_at)
        )
        conn.commit()
        logging.info(f"Recuerdo guardado: '{content}' (Categoría: {category}, Origen: {source})")
        return True
    except sqlite3.IntegrityError:
        logging.info(f"El recuerdo ya existía en la base de datos: '{content}'")
        return False
    except Exception as e:
        logging.error(f"Error al guardar memoria: {e}")
        return False
    finally:
        conn.close()

def search_memories(query: str) -> list:
    """
    Busca recuerdos que contengan la consulta (case-insensitive).
    Retorna una lista de diccionarios.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, category, source, content, created_at FROM memories WHERE content LIKE ? ORDER BY id DESC",
            (f"%{query}%",)
        )
        rows = cursor.fetchall()
        memories = []
        for row in rows:
            memories.append({
                "id": row[0],
                "category": row[1],
                "source": row[2],
                "content": row[3],
                "created_at": row[4]
            })
        return memories
    except Exception as e:
        logging.error(f"Error al buscar memorias con query '{query}': {e}")
        return []
    finally:
        conn.close()

def delete_memory_by_content(query: str) -> bool:
    """
    Elimina recuerdos que contengan o coincidan con el query.
    Retorna True si se eliminó al menos un registro, False de lo contrario.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    
    try:
        # Primero buscamos si hay coincidencias para saber si eliminamos algo
        cursor.execute("SELECT id FROM memories WHERE content LIKE ?", (f"%{query}%",))
        matching_ids = [row[0] for row in cursor.fetchall()]
        
        if not matching_ids:
            return False
            
        # Eliminar usando los IDs encontrados
        placeholders = ",".join("?" for _ in matching_ids)
        cursor.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", matching_ids)
        conn.commit()
        logging.info(f"Eliminados {cursor.rowcount} recuerdos que coinciden con '{query}'")
        return True
    except Exception as e:
        logging.error(f"Error al eliminar memorias con query '{query}': {e}")
        return False
    finally:
        conn.close()

def get_all_memories(limit: int = 20) -> list:
    """
    Retorna todos los recuerdos ordenados por los más recientes (con un límite).
    Retorna una lista de diccionarios.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, category, source, content, created_at FROM memories ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        memories = []
        for row in rows:
            memories.append({
                "id": row[0],
                "category": row[1],
                "source": row[2],
                "content": row[3],
                "created_at": row[4]
            })
        return memories
    except Exception as e:
        logging.error(f"Error al obtener todas las memorias: {e}")
        return []
    finally:
        conn.close()
