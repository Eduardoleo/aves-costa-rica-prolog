"""Pruebas unitarias de la lista blanca y del citado de atomos Prolog."""
import os
import sys
import unittest
from pathlib import Path

os.environ["AVES_MODO_DEMO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/Main"))

import prolog_seguro as ps  # noqa: E402


class ListaBlancaTests(unittest.TestCase):
    def test_valores_validos_se_normalizan(self):
        self.assertEqual(ps.validar_filtro("color", "  Verde  Oscuro "), "verde oscuro")
        self.assertEqual(ps.validar_filtro("peso", "1.5 - 2,5 kg"), "1.5 - 2,5 kg")
        self.assertEqual(ps.validar_filtro("habitat", "montaña"), "montaña")
        self.assertEqual(ps.validar_filtro("color", ""), "")
        self.assertEqual(ps.validar_filtro("color", None), "")

    def test_rechaza_metacaracteres_de_prolog(self):
        for valor in ("o'brien", "a(b)", "x, y)", "a\\b", "a;b", "a:-b", "a|b", '"a"', "-inicio", "a\x00b"):
            with self.subTest(valor=valor), self.assertRaises(ps.EntradaInvalida):
                ps.validar_filtro("color", valor)

    def test_rechaza_tipos_y_longitud(self):
        for valor in (5, ["verde"], {"a": 1}, True, "a" * 61):
            with self.subTest(valor=valor), self.assertRaises(ps.EntradaInvalida):
                ps.validar_filtro("color", valor)

    def test_mensaje_no_repite_la_entrada(self):
        with self.assertRaises(ps.EntradaInvalida) as ctx:
            ps.validar_filtro("color", "valor'secreto")
        self.assertNotIn("secreto", str(ctx.exception))

    def test_genero(self):
        self.assertEqual(ps.validar_genero("Pharomachrus"), "Pharomachrus")
        for valor in ("", "Ara'", "a(b)", "x y", 3):
            with self.subTest(valor=valor), self.assertRaises(ps.EntradaInvalida):
                ps.validar_genero(valor)


class CitadoTests(unittest.TestCase):
    def test_escapa_comilla_y_barra(self):
        self.assertEqual(ps.atomo_prolog("a'b"), "'a\\'b'")
        self.assertEqual(ps.atomo_prolog("a\\"), "'a\\\\'")

    def test_rechaza_caracteres_de_control(self):
        with self.assertRaises(ValueError):
            ps.atomo_prolog("a\nb")

    def test_consulta_es_un_predicado_fijo(self):
        consulta = ps.consulta_busqueda(color="verde")
        self.assertTrue(consulta.startswith("buscar_aves('', 'verde', '', '', '', Nombre,"))

    def test_atomo_citado_se_lee_como_un_solo_atomo(self):
        """Aun sin lista blanca, el citado impide salir del atomo."""
        try:
            from pyswip import Prolog
        except ImportError:
            self.skipTest("pyswip no disponible")
        prolog = Prolog()
        for texto in ("a'b", "x'), fail, atom('", "fin\\", "\\'), true, ('"):
            with self.subTest(texto=texto):
                consulta = f"A = {ps.atomo_prolog(texto)}, atom(A), atom_length(A, L)"
                soluciones = list(prolog.query(consulta))
                self.assertEqual(len(soluciones), 1)
                self.assertEqual(soluciones[0]["L"], len(texto))


class GeneradorHechosTests(unittest.TestCase):
    def test_hecho_generado_es_un_solo_termino(self):
        """Valores del LLM con comillas o barra final no rompen el hecho."""
        try:
            from pyswip import Prolog
        except ImportError:
            self.skipTest("pyswip no disponible")
        import IA_Generativa_Aves as generador
        datos = {"reino": "Animalia", "filo": "fin\\", "color": "o'scuro", "peso": 300,
                 "alimento": "linea\nnueva", "habitat": "x'). :- fail. %", "descripcion": "ok"}
        hecho = generador.generar_hechos_prolog(datos, "Ave-Prueba")
        self.assertTrue(hecho.endswith(")."))
        soluciones = list(Prolog().query(f"T = {hecho[:-1]}, functor(T, caracteristicas, 8), arg(3, T, F)"))
        self.assertEqual(len(soluciones), 1)
        self.assertEqual(soluciones[0]["F"], "fin\\")


if __name__ == "__main__":
    unittest.main()
