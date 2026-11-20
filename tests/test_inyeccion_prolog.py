"""Regresion: los filtros del usuario y las respuestas del LLM no deben
interpretarse como objetivos Prolog.

Cada prueba intenta (de forma inofensiva) agregar un hecho marcador con
assertz/1 y luego comprueba que ese hecho NO existe. No se usa red: el modo
demo esta activo y las respuestas del LLM se simulan con mocks.
"""
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["AVES_MODO_DEMO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/Main"))

import app as aves  # noqa: E402  (requiere SWI-Prolog instalado)
from PIL import Image  # noqa: E402

MARCADORES = ("marcador_filtro", "marcador_form", "marcador_llm", "marcador_nombre", "marcador_color")


def inyeccion(marcador):
    """Texto que cierra el atomo citado y agrega un objetivo assertz inofensivo."""
    return f"'), assertz({marcador}(1)), atom('"


def existe(marcador):
    # marcador es siempre una constante de este archivo, nunca entrada externa.
    return bool(list(aves.prolog.query(f"catch({marcador}(_), _, fail)")))


def respuesta_llm(datos):
    contenido = json.dumps(datos)
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))])


def imagen_png():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (10, 200, 10)).save(buffer, "PNG")
    buffer.seek(0)
    return buffer


class InyeccionPrologTests(unittest.TestCase):
    def setUp(self):
        self.cliente = aves.app.test_client()
        self.limpiar_marcadores()

    def tearDown(self):
        self.limpiar_marcadores()

    @staticmethod
    def limpiar_marcadores():
        for marcador in MARCADORES:
            list(aves.prolog.query(f"retractall({marcador}(_))"))

    def simular_llm(self, datos):
        return patch.object(aves.cliente_openai.chat.completions, "create",
                            return_value=respuesta_llm(datos))

    # --- Filtros del usuario ---
    def test_api_buscar_rechaza_filtro_con_objetivo(self):
        r = self.cliente.post("/buscar", json={"color": inyeccion("marcador_filtro")})
        self.assertFalse(existe("marcador_filtro"), "el filtro se ejecuto como objetivo Prolog")
        self.assertEqual(r.status_code, 400)

    def test_formulario_busca_rechaza_filtro_con_objetivo(self):
        r = self.cliente.post("/busca", data={"habitat": inyeccion("marcador_form")})
        self.assertFalse(existe("marcador_form"), "el filtro se ejecuto como objetivo Prolog")
        self.assertEqual(r.status_code, 400)

    # --- Valores que devuelve el LLM ---
    def test_api_buscar_descarta_valor_del_llm_con_objetivo(self):
        with self.simular_llm({"color": inyeccion("marcador_llm")}):
            r = self.cliente.post("/buscar", json={"color": "verde"})
        self.assertFalse(existe("marcador_llm"), "la respuesta del LLM se ejecuto como objetivo Prolog")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.get_json()), 0, "debe usar el filtro valido del usuario")

    def test_analizar_ave_nombre_cientifico_del_llm(self):
        datos = {"nombre": "x", "nombre_cientifico": "'),assertz(marcador_nombre(1)),atom('"}
        with self.simular_llm(datos):
            r = self.cliente.post("/analizar-ave", data={"imagen": (imagen_png(), "ave.png")},
                                  content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(existe("marcador_nombre"), "el nombre del LLM se ejecuto como objetivo Prolog")

    def test_analizar_ave_color_del_llm(self):
        datos = {"nombre": "x", "nombre_cientifico": "Zzzzinexistente", "color": inyeccion("marcador_color")}
        with self.simular_llm(datos):
            r = self.cliente.post("/analizar-ave", data={"imagen": (imagen_png(), "ave.png")},
                                  content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(existe("marcador_color"), "el color del LLM se ejecuto como objetivo Prolog")


class EntradaInvalidaTests(unittest.TestCase):
    def setUp(self):
        self.cliente = aves.app.test_client()

    def test_cuerpo_que_no_es_json(self):
        r = self.cliente.post("/buscar", data="color=verde", content_type="text/plain")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.get_json())

    def test_json_que_no_es_objeto(self):
        r = self.cliente.post("/buscar", json=["verde"])
        self.assertEqual(r.status_code, 400)

    def test_filtro_que_no_es_texto(self):
        r = self.cliente.post("/buscar", json={"color": 5})
        self.assertEqual(r.status_code, 400)

    def test_filtro_demasiado_largo(self):
        r = self.cliente.post("/buscar", json={"color": "a" * 61})
        self.assertEqual(r.status_code, 400)

    def test_mensaje_400_no_repite_la_entrada(self):
        r = self.cliente.post("/buscar", json={"color": "verde<script>"})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("<script>", r.get_data(as_text=True))


class ErroresInternosTests(unittest.TestCase):
    def setUp(self):
        self.cliente = aves.app.test_client()

    def test_api_no_expone_error_de_prolog(self):
        with patch.object(aves.prolog, "query", side_effect=RuntimeError("detalle-interno-XYZ")):
            r = self.cliente.post("/buscar", json={"color": "verde"})
        self.assertEqual(r.status_code, 500)
        cuerpo = r.get_data(as_text=True)
        self.assertNotIn("detalle-interno-XYZ", cuerpo)
        self.assertNotIn("caracteristicas", cuerpo)

    def test_formulario_no_expone_error_de_prolog(self):
        with patch.object(aves.prolog, "query", side_effect=RuntimeError("detalle-interno-XYZ")):
            r = self.cliente.post("/busca", data={"color": "rojo"})
        self.assertEqual(r.status_code, 500)
        self.assertFalse("detalle-interno-XYZ" in r.get_data(as_text=True),
                         "la pagina muestra el mensaje interno de la excepcion")

    def test_analisis_no_expone_error_interno(self):
        with patch.object(aves.cliente_openai.chat.completions, "create",
                          side_effect=RuntimeError("detalle-interno-XYZ")):
            r = self.cliente.post("/analizar-ave", data={"imagen": (imagen_png(), "ave.png")},
                                  content_type="multipart/form-data")
        self.assertFalse("detalle-interno-XYZ" in r.get_data(as_text=True),
                         "la pagina muestra el mensaje interno de la excepcion")


class ComportamientoNormalTests(unittest.TestCase):
    def setUp(self):
        self.cliente = aves.app.test_client()

    def test_api_busqueda_valida_devuelve_resultados(self):
        r = self.cliente.post("/buscar", json={"color": "verde"})
        self.assertEqual(r.status_code, 200)
        resultados = r.get_json()
        self.assertGreater(len(resultados), 0)
        self.assertLessEqual(len(resultados), 10)
        self.assertTrue(all("verde" in ave["color"] for ave in resultados))

    def test_api_combina_filtros(self):
        r = self.cliente.post("/buscar", json={"color": "verde", "habitat": "bosque"})
        self.assertEqual(r.status_code, 200)
        for ave in r.get_json():
            self.assertIn("verde", ave["color"])
            self.assertIn("bosque", ave["habitat"])

    def test_api_peso_con_digitos_y_guion(self):
        r = self.cliente.post("/buscar", json={"peso": "450-600"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.get_json()), 0)

    def test_formulario_busqueda_valida(self):
        r = self.cliente.post("/busca", data={"color": "rojo"})
        self.assertEqual(r.status_code, 200)

    def test_analizar_ave_demo(self):
        r = self.cliente.post("/analizar-ave", data={"imagen": (imagen_png(), "ave.png")},
                              content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Quetzal", r.data)


if __name__ == "__main__":
    unittest.main()
