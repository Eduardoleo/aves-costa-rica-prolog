"""Construccion segura de consultas Prolog.

Reglas:
1. La consulta siempre llama a un predicado fijo (buscar_aves/13, definido en
   Bases_Prolog/busqueda_segura.pl); el texto externo nunca forma objetivos.
2. Cada valor externo (usuario o LLM) se valida con una lista blanca estricta.
3. Ademas, cada valor se cita como atomo Prolog (defensa en profundidad).
"""
import re

CAMPOS_BUSQUEDA = ("color", "habitat", "peso", "alimento")
LONGITUD_MAXIMA = 60

# Letras (con tildes y ene), digitos, espacios y . , - ; debe empezar por letra o digito.
_PATRON_FILTRO = re.compile(r"[0-9a-záéíóúüñ][0-9a-záéíóúüñ .,\-]*")
# Primer termino de un nombre cientifico (p. ej. "Pharomachrus").
_PATRON_GENERO = re.compile(r"[A-Za-z][A-Za-z\-]*")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

VARIABLES_RESULTADO = ("Nombre", "Reino", "Filo", "Color", "Peso", "Alimento", "Habitat", "Descripcion")


class EntradaInvalida(ValueError):
    """Valor rechazado por la lista blanca. El mensaje no repite la entrada."""


def validar_filtro(campo, valor):
    """Devuelve el filtro normalizado ('' si viene vacio) o lanza EntradaInvalida."""
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise EntradaInvalida(f"El campo '{campo}' debe ser texto.")
    valor = " ".join(valor.lower().split())
    if not valor:
        return ""
    if len(valor) > LONGITUD_MAXIMA or not _PATRON_FILTRO.fullmatch(valor):
        raise EntradaInvalida(
            f"El campo '{campo}' solo admite letras, números, espacios y los signos . , - "
            f"(máximo {LONGITUD_MAXIMA} caracteres)."
        )
    return valor


def validar_genero(valor):
    """Valida el primer termino de un nombre cientifico; lanza EntradaInvalida."""
    if not isinstance(valor, str) or len(valor) > LONGITUD_MAXIMA or not _PATRON_GENERO.fullmatch(valor):
        raise EntradaInvalida("Nombre científico no válido.")
    return valor


def atomo_prolog(texto):
    """Cita texto como atomo Prolog entre comillas simples.

    Escapa la barra invertida y la comilla simple, y rechaza caracteres de
    control, de modo que el resultado siempre se lee como un unico atomo.
    """
    if not isinstance(texto, str):
        raise TypeError("Se esperaba texto")
    if _CONTROL.search(texto):
        raise ValueError("Caracteres de control no permitidos en un atomo Prolog")
    return "'" + texto.replace("\\", "\\\\").replace("'", "\\'") + "'"


def consulta_busqueda(nombre="", color="", habitat="", peso="", alimento=""):
    """Consulta fija buscar_aves/13; los argumentos deben estar ya validados."""
    argumentos = [atomo_prolog(v) for v in (nombre, color, habitat, peso, alimento)]
    return "buscar_aves(" + ", ".join(argumentos + list(VARIABLES_RESULTADO)) + ")"
