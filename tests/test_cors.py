"""Regresion: CORS no debe reflejar cualquier origen."""
import os
import sys
import unittest
from pathlib import Path

os.environ["AVES_MODO_DEMO"] = "1"
os.environ.pop("AVES_CORS_ORIGINS", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/Main"))

import app as aves  # noqa: E402  (requiere SWI-Prolog instalado)


class PruebasCors(unittest.TestCase):
    def test_lista_de_origenes(self):
        self.assertEqual(
            aves.origenes_cors(" https://a.example.test/, ,https://b.example.test "),
            ["https://a.example.test", "https://b.example.test"],
        )
        self.assertEqual(aves.origenes_cors(""), [])

    def test_sin_origenes_no_hay_cabeceras_cors(self):
        cliente = aves.app.test_client()
        respuesta = cliente.get("/", headers={"Origin": "https://atacante.example.test"})
        self.assertIsNone(respuesta.headers.get("Access-Control-Allow-Origin"))
        previa = cliente.options(
            "/buscar",
            headers={"Origin": "https://atacante.example.test", "Access-Control-Request-Method": "POST"},
        )
        self.assertIsNone(previa.headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
