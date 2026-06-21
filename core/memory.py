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

# Versión actual del esquema de la base de datos. Incrementar al añadir una
# nueva migración en _MIGRATIONS.
SCHEMA_VERSION = 1


def _migration_v1(conn: sqlite3.Connection):
    """Esquema base (v1): tablas de memorias y de tareas programadas."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            source TEXT,
            content TEXT UNIQUE,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            task_type TEXT,
            target TEXT,
            interval_seconds INTEGER,
            next_run TEXT,
            enabled INTEGER DEFAULT 1,
            last_run TEXT,
            last_result TEXT,
            last_error TEXT,
            metadata TEXT,
            created_at TEXT
        )
    """)


# Registro ordenado de migraciones: versión_destino -> función(conn).
# Para evolucionar el esquema: subir SCHEMA_VERSION y añadir aquí la migración
# correspondiente (p.ej. 2: _migration_v2 con ALTER TABLE / CREATE TABLE).
_MIGRATIONS = {
    1: _migration_v1,
}


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Retorna la versión del esquema almacenada en la base de datos (PRAGMA user_version)."""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def current_schema_version() -> int:
    """Retorna la versión del esquema de la base de datos activa."""
    conn = sqlite3.connect(_db_path)
    try:
        return get_schema_version(conn)
    finally:
        conn.close()


def _apply_migrations(conn: sqlite3.Connection) -> int:
    """Aplica las migraciones pendientes en orden y actualiza user_version.

    Solo ejecuta las migraciones cuya versión sea mayor que la actual, por lo
    que es idempotente y seguro de llamar en cada init_db().
    """
    current = get_schema_version(conn)
    if current >= SCHEMA_VERSION:
        return current

    for version in range(current + 1, SCHEMA_VERSION + 1):
        migration = _MIGRATIONS.get(version)
        if migration is not None:
            migration(conn)
        # PRAGMA no admite parámetros; version es un int controlado (seguro).
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
        logging.info(f"[Memory] Esquema de base de datos migrado a la versión {version}.")

    return SCHEMA_VERSION


def init_db(db_path: str = None):
    """Inicializa la base de datos SQLite y aplica las migraciones de esquema pendientes."""
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
    try:
        _apply_migrations(conn)
    finally:
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

def db_save_task(name: str, task_type: str, target: str, interval_seconds: int, next_run: str, enabled: int = 1, metadata: str = None) -> bool:
    """
    Guarda o actualiza una tarea programada en la base de datos.
    Establece una conexión única por llamada.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    created_at = datetime.now(timezone.utc).isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO scheduled_tasks (name, task_type, target, interval_seconds, next_run, enabled, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                task_type=excluded.task_type,
                target=excluded.target,
                interval_seconds=excluded.interval_seconds,
                next_run=excluded.next_run,
                enabled=excluded.enabled,
                metadata=excluded.metadata
        """, (name, task_type, target, interval_seconds, next_run, enabled, metadata, created_at))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error al guardar tarea programada '{name}': {e}")
        return False
    finally:
        conn.close()

def db_get_active_tasks() -> list:
    """
    Retorna la lista de todas las tareas habilitadas.
    Establece una conexión única por llamada.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, task_type, target, interval_seconds, next_run, enabled, last_run, last_result, last_error, metadata, created_at
            FROM scheduled_tasks
            WHERE enabled = 1
            ORDER BY next_run ASC
        """)
        rows = cursor.fetchall()
        tasks = []
        for r in rows:
            tasks.append({
                "id": r[0],
                "name": r[1],
                "task_type": r[2],
                "target": r[3],
                "interval_seconds": r[4],
                "next_run": r[5],
                "enabled": r[6],
                "last_run": r[7],
                "last_result": r[8],
                "last_error": r[9],
                "metadata": r[10],
                "created_at": r[11]
            })
        return tasks
    except Exception as e:
        logging.error(f"Error al recuperar tareas activas: {e}")
        return []
    finally:
        conn.close()

def db_delete_task(name: str) -> bool:
    """
    Elimina una tarea programada por su nombre único.
    Retorna True si se eliminó algún registro.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM scheduled_tasks WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error al eliminar la tarea '{name}': {e}")
        return False
    finally:
        conn.close()

def db_update_task_execution(name: str, last_run: str, last_result: str, last_error: str = None, next_run: str = None, metadata: str = None) -> bool:
    """
    Actualiza el estado de ejecución y resultado de una tarea.
    Si se provee next_run, la actualiza; de lo contrario se mantiene.
    Si se provee metadata, se actualiza.
    """
    init_db()
    conn = sqlite3.connect(_db_path)
    cursor = conn.cursor()
    
    try:
        if next_run and metadata is not None:
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run = ?, last_result = ?, last_error = ?, next_run = ?, metadata = ?
                WHERE name = ?
            """, (last_run, last_result, last_error, next_run, metadata, name))
        elif next_run:
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run = ?, last_result = ?, last_error = ?, next_run = ?
                WHERE name = ?
            """, (last_run, last_result, last_error, next_run, name))
        elif metadata is not None:
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run = ?, last_result = ?, last_error = ?, metadata = ?
                WHERE name = ?
            """, (last_run, last_result, last_error, metadata, name))
        else:
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run = ?, last_result = ?, last_error = ?
                WHERE name = ?
            """, (last_run, last_result, last_error, name))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error al actualizar ejecución de la tarea '{name}': {e}")
        return False
    finally:
        conn.close()

