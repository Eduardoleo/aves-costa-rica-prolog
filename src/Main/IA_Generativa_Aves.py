import os
import openai
import json
import re
from pathlib import Path

from azure_config import cliente_aves
from prolog_seguro import atomo_prolog
client = cliente_aves
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

ultimo_prompt = ""  # Variable global para guardar el último prompt usado

# Rutas relativas al script (src/Main): funcionan desde cualquier carpeta y equipo.
CARPETA_SCRIPT = Path(__file__).resolve().parent
CARPETA_PROLOG = CARPETA_SCRIPT.parents[1] / "Bases_Prolog"
ARCHIVO_ENTRADA = CARPETA_PROLOG / "Aves_Existentes_cr.pl"
ARCHIVO_SALIDA = CARPETA_PROLOG / "Aves_CR_Caracteristicas.pl"
ARCHIVO_ERRORES = CARPETA_SCRIPT / "errores.log"

# Función para leer el archivo Prolog existente
def Aves_existentes(path):
    aves = []
    patron = re.compile(r"ave\((.+?),\s*(.+?),\s*(.+?),\s*(.+?)\)\.")
    with open(path, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            match = patron.match(linea.strip())
            if match:
                nombre_cientifico, familia, reino, filo = match.groups()
                aves.append({
                    "nombre_comun": nombre_cientifico.replace("_", " ").title(),
                    "nombre_cientifico": nombre_cientifico,
                    "nombre_ingles": "",
                    "familia": familia
                })
    return aves

# Función para obtener datos de Azure OpenAI
def generar_datos(ave):
    global ultimo_prompt
    prompt = (
        f"Proporciona exclusivamente una respuesta en formato JSON con los siguientes campos para el ave "
        f"'{ave['nombre_comun']}' (nombre científico: {ave['nombre_cientifico']}):\n"
        f"reino, filo, color, peso, alimento, habitat, descripcion.\n"
        f"No incluyas explicaciones ni texto adicional, solo un objeto JSON válido."
    )
    ultimo_prompt = prompt

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    content = response.choices[0].message.content
    print(f"\nRespuesta cruda del modelo para {ave['nombre_comun']}:\n{content}\n")

    # Eliminar posibles etiquetas ```json o ``` del contenido
    if content.startswith("```"):
        content = content.strip().strip("`").strip("json").strip()

    return json.loads(content)

# Función para generar hechos en formato Prolog
def generar_hechos_prolog(datos_ave, nombre_comun):
    # La respuesta del LLM no es confiable: cada valor se cita como atomo
    # (escapando comilla y barra invertida) para que el hecho generado no
    # pueda cerrar el atomo ni agregar directivas al archivo .pl.
    def limpiar(texto):
        return atomo_prolog(" ".join(str(texto).split()))
    campos = ("reino", "filo", "color", "peso", "alimento", "habitat", "descripcion")
    argumentos = [limpiar(nombre_comun)] + [limpiar(datos_ave[campo]) for campo in campos]
    return "caracteristicas(" + ", ".join(argumentos) + ")."

# Script principal
if __name__ == "__main__":
    archivo_entrada = ARCHIVO_ENTRADA
    archivo_salida = ARCHIVO_SALIDA

    aves = Aves_existentes(archivo_entrada)

    hechos = [
        "% Base de hechos: Características de aves de Costa Rica",
        "% caracteristicas(NombreComun, Reino, Filo, Color, Peso, Alimento, Habitat, Descripcion).",
        ":- module(aves_cr_caracteristicas, [caracteristicas/8])."
    ]

    for ave in aves:
        try:
            datos = generar_datos(ave)
            hecho = generar_hechos_prolog(datos, ave["nombre_comun"])
            hechos.append(hecho)
        except Exception as e:
            print(f"Error con {ave['nombre_comun']}: {e}")
            with open(ARCHIVO_ERRORES, "a", encoding="utf-8") as error_log:
                error_log.write(f"\nError con {ave['nombre_comun']}:\n{e}\n")
                error_log.write(f"Prompt usado:\n{ultimo_prompt}\n")
                error_log.write("--------------------------------------------------\n")

    with open(archivo_salida, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(hechos))

    print(f"Archivo generado: {archivo_salida}")
