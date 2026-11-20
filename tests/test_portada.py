"""La portada usa solo imágenes locales con licencia libre y su crédito visible."""
import os
import re
import sys
import unittest
from pathlib import Path

os.environ["AVES_MODO_DEMO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/Main"))

import app as aves  # noqa: E402  (requiere SWI-Prolog instalado)

ESTATICOS = Path(__file__).resolve().parents[1] / "src/Main/static"


class PruebasPortada(unittest.TestCase):
    def test_imagenes_locales_con_credito(self):
        cliente = aves.app.test_client()
        html = cliente.get("/").get_data(as_text=True)
        fuentes = re.findall(r'<img src="([^"]+)"', html)
        self.assertEqual(len(fuentes), 5)
        for fuente in fuentes:
            self.assertTrue(fuente.startswith("/static/aves/"), fuente)
            self.assertTrue((ESTATICOS / fuente.removeprefix("/static/")).is_file(), fuente)
            self.assertEqual(cliente.get(fuente).status_code, 200)
        self.assertEqual(html.count('class="bird-credit"'), 5)
        self.assertNotRegex(html, r"gstatic|fbcdn|scontent|costarica\.org")


if __name__ == "__main__":
    unittest.main()
