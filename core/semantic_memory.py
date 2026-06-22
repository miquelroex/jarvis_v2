"""
core/semantic_memory.py — Memoria semántica (RAG) sobre los recuerdos de Jarvis.

Genera embeddings de los recuerdos con la API de Google (genai) y permite
buscarlos por SIGNIFICADO (similitud coseno) en vez de por subcadena.

Los embeddings se guardan como JSON en la columna `embedding` de la tabla
`memories` (añadida por la migración v2 del esquema). Módulo ligero (numpy +
stdlib); el cliente de genai se importa de forma perezosa.
"""
import os
import json
import sqlite3
import logging

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("JARVIS_EMBEDDING_MODEL", "text-embedding-004")


def embed_text(text: str):
    """Devuelve el embedding (lista de floats) del texto vía Google, o None.

    None si no hay GOOGLE_API_KEY, el texto está vacío o falla la llamada.
    """
    if not text or not text.strip():
        return None
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
        embeddings = getattr(result, "embeddings", None)
        if embeddings:
            return list(embeddings[0].values)
        # Compatibilidad con respuestas que devuelven .embedding
        emb = getattr(result, "embedding", None)
        if emb is not None:
            return list(getattr(emb, "values", emb))
        return None
    except Exception as e:
        logger.warning(f"[SemanticMemory] Error al generar embedding: {e}")
        return None


def _cosine(a, b) -> float:
    """Similitud coseno entre dos vectores (numpy). 0 si alguno es nulo."""
    import numpy as np
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _db_path() -> str:
    from core.memory import get_db_path, init_db
    init_db()
    return get_db_path()


def index_memory(memory_id: int, content: str) -> bool:
    """Calcula y guarda el embedding de un recuerdo concreto. Best-effort."""
    vec = embed_text(content)
    if vec is None:
        return False
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute("UPDATE memories SET embedding = ? WHERE id = ?", (json.dumps(vec), memory_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[SemanticMemory] Error al indexar el recuerdo {memory_id}: {e}")
        return False
    finally:
        conn.close()


def backfill_embeddings() -> int:
    """Genera embeddings para todos los recuerdos que aún no lo tengan.

    Devuelve cuántos se indexaron. Si la API no está disponible, para y devuelve
    los que llevara.
    """
    conn = sqlite3.connect(_db_path())
    indexed = 0
    try:
        rows = conn.execute("SELECT id, content FROM memories WHERE embedding IS NULL").fetchall()
        for mid, content in rows:
            vec = embed_text(content)
            if vec is None:
                break  # API no disponible: no insistir
            conn.execute("UPDATE memories SET embedding = ? WHERE id = ?", (json.dumps(vec), mid))
            indexed += 1
        conn.commit()
    except Exception as e:
        logger.error(f"[SemanticMemory] Error en el backfill de embeddings: {e}")
    finally:
        conn.close()
    if indexed:
        logger.info(f"[SemanticMemory] Indexados {indexed} recuerdos.")
    return indexed


def semantic_search(query: str, top_k: int = 5, min_score: float = 0.0) -> list:
    """Busca recuerdos por significado. Devuelve los top_k por similitud coseno.

    Cada resultado: {id, category, source, content, created_at, score}.
    Lista vacía si no se puede embeber la consulta.
    """
    qvec = embed_text(query)
    if qvec is None:
        return []

    results = []
    conn = sqlite3.connect(_db_path())
    try:
        cur = conn.execute(
            "SELECT id, category, source, content, created_at, embedding "
            "FROM memories WHERE embedding IS NOT NULL"
        )
        for row in cur.fetchall():
            try:
                emb = json.loads(row[5])
            except Exception:
                continue
            score = _cosine(qvec, emb)
            if score >= min_score:
                results.append({
                    "id": row[0], "category": row[1], "source": row[2],
                    "content": row[3], "created_at": row[4], "score": round(score, 4),
                })
    finally:
        conn.close()

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]
