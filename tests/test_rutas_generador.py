"""El generador de hechos usa rutas relativas al script, no rutas de un equipo concreto."""
import os
import sys
import unittest
from pathlib import Path

os.environ["AVES_MODO_DEMO"] = "1"
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src/Main"))

import IA_Generativa_Aves as generador  # noqa: E402


class RutasGeneradorTests(unittest.TestCase):
    def test_rutas_dentro_del_repositorio(self):
        for ruta in (generador.ARCHIVO_ENTRADA, generador.ARCHIVO_SALIDA, generador.ARCHIVO_ERRORES):
            with self.subTest(ruta=ruta):
                self.assertTrue(ruta.is_relative_to(RAIZ), ruta)
        self.assertEqual(generador.CARPETA_PROLOG, RAIZ / "Bases_Prolog")

    def test_archivos_prolog_existen(self):
        self.assertTrue(generador.ARCHIVO_ENTRADA.is_file())
        self.assertTrue(generador.ARCHIVO_SALIDA.is_file())

    def test_lee_las_aves_existentes(self):
        aves = generador.Aves_existentes(generador.ARCHIVO_ENTRADA)
        self.assertGreater(len(aves), 0)
        self.assertTrue(all(ave["nombre_cientifico"] for ave in aves))

    def test_sin_rutas_absolutas_en_el_codigo(self):
        codigo = (RAIZ / "src/Main/IA_Generativa_Aves.py").read_text(encoding="utf-8")
        self.assertNotIn("C:/", codigo)
        self.assertNotIn("C:\\\\", codigo)


if __name__ == "__main__":
    unittest.main()
