import os
import unittest
import tempfile
import sqlite3
from core.memory import (
    init_db,
    save_memory,
    search_memories,
    delete_memory_by_content,
    get_all_memories,
    set_db_path,
    get_db_path
)

class TestMemoryCore(unittest.TestCase):
    def setUp(self):
        # Crear un archivo temporal real para posibilitar múltiples conexiones persistentes durante la prueba
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        set_db_path(self.test_db_path)
        init_db(self.test_db_path)

    def tearDown(self):
        # Eliminar archivo temporal
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_init_db_creates_table(self):
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists, "La tabla 'memories' debería existir.")
        
        # Verificar columnas
        cursor.execute("PRAGMA table_info(memories)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        self.assertIn("id", columns)
        self.assertIn("category", columns)
        self.assertIn("source", columns)
        self.assertIn("content", columns)
        self.assertIn("created_at", columns)
        conn.close()

    def test_save_and_retrieve_memories(self):
        # Guardar varios recuerdos
        res1 = save_memory("Me gusta programar en Python", category="gustos", source="test")
        res2 = save_memory("Mi perro se llama Toby", category="mascota", source="test")
        
        self.assertTrue(res1)
        self.assertTrue(res2)
        
        # Obtener todos y verificar
        all_mems = get_all_memories()
        self.assertEqual(len(all_mems), 2)
        
        # Comprobar campos
        m1 = [m for m in all_mems if m["category"] == "gustos"][0]
        self.assertEqual(m1["content"], "Me gusta programar en Python")
        self.assertEqual(m1["source"], "test")
        self.assertIsNotNone(m1["created_at"])
        
        m2 = [m for m in all_mems if m["category"] == "mascota"][0]
        self.assertEqual(m2["content"], "Mi perro se llama Toby")
        self.assertEqual(m2["source"], "test")

    def test_save_duplicate_memory(self):
        res1 = save_memory("La lasaña es mi comida favorita", category="comida", source="test")
        res2 = save_memory("La lasaña es mi comida favorita", category="gusto", source="test_alt")
        
        self.assertTrue(res1)
        self.assertFalse(res2, "No se debería guardar un recuerdo exactamente duplicado.")
        
        all_mems = get_all_memories()
        self.assertEqual(len(all_mems), 1)

    def test_search_memories(self):
        save_memory("Me gusta la pizza", category="comida")
        save_memory("Tengo un gato negro", category="mascota")
        save_memory("Ayer comí pizza con piña", category="comida")
        
        # Buscar "pizza"
        results = search_memories("pizza")
        self.assertEqual(len(results), 2)
        contents = [m["content"] for m in results]
        self.assertIn("Me gusta la pizza", contents)
        self.assertIn("Ayer comí pizza con piña", contents)
        
        # Buscar algo inexistente
        results_empty = search_memories("computadora")
        self.assertEqual(len(results_empty), 0)

    def test_delete_memory(self):
        save_memory("Recordar comprar pan", category="tareas")
        save_memory("Recordar comprar leche", category="tareas")
        
        # Eliminar por coincidencia parcial "leche"
        del_res1 = delete_memory_by_content("leche")
        self.assertTrue(del_res1)
        
        all_mems = get_all_memories()
        self.assertEqual(len(all_mems), 1)
        self.assertEqual(all_mems[0]["content"], "Recordar comprar pan")
        
        # Intentar eliminar algo que no existe
        del_res2 = delete_memory_by_content("automovil")
        self.assertFalse(del_res2)

    def test_get_all_memories_limit(self):
        # Guardar 25 memorias
        for i in range(25):
            save_memory(f"Recuerdo número {i}", category="secuencia")
            
        mems_default = get_all_memories() # Límite por defecto es 20
        self.assertEqual(len(mems_default), 20)
        
        mems_custom = get_all_memories(limit=10)
        self.assertEqual(len(mems_custom), 10)
        
        # La más reciente (número 24) debería estar al principio
        self.assertEqual(mems_custom[0]["content"], "Recuerdo número 24")

if __name__ == "__main__":
    unittest.main()
