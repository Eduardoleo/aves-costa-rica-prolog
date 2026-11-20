from azure_config import cliente_aves, LimiteAzureError
from flask import Flask, request, jsonify, render_template, redirect, url_for
from pyswip import Prolog
from flask_cors import CORS
from colorthief import ColorThief
from prolog_seguro import CAMPOS_BUSQUEDA, EntradaInvalida, consulta_busqueda, validar_filtro, validar_genero
import webcolors
import openai
import json
import logging
import os

app = Flask(__name__, template_folder="Templates")
registro = logging.getLogger("aves")
MENSAJE_ERROR_BUSQUEDA = "No se pudo completar la búsqueda. Intente de nuevo más tarde."

def origenes_cors(valor=None):
    """Lista de orígenes de AVES_CORS_ORIGINS (separados por comas, sin barra final)."""
    valor = os.getenv("AVES_CORS_ORIGINS", "") if valor is None else valor
    return [origen.strip().rstrip("/") for origen in valor.split(",") if origen.strip()]

# Las plantillas usan el mismo origen, así que CORS queda apagado salvo que se
# declaren orígenes explícitos. Nunca se refleja cualquier origen.
ORIGENES_CORS = origenes_cors()
if ORIGENES_CORS:
    CORS(app, origins=ORIGENES_CORS)

@app.errorhandler(LimiteAzureError)
def limite_azure(error):
    return jsonify({"error": str(error)}), 429

cliente_openai = cliente_aves
despliegue_modelo = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

# --- Conectar con base de conocimiento Prolog ---
prolog = Prolog()
# Construir ruta absoluta al archivo Prolog
carpeta_prolog = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Bases_Prolog"))
ruta_base = os.path.join(carpeta_prolog, "Aves_CR_Caracteristicas.pl")
print(f"Intentando cargar archivo Prolog desde: {ruta_base}")
prolog.consult(ruta_base)
# Predicado fijo de búsqueda: los filtros solo viajan como átomos citados.
prolog.consult(os.path.join(carpeta_prolog, "busqueda_segura.pl"))

# --- Consultas Prolog seguras ---
def leer_filtros(origen):
    """Valida los filtros de búsqueda (lista blanca); lanza EntradaInvalida."""
    return {campo: validar_filtro(campo, origen.get(campo)) for campo in CAMPOS_BUSQUEDA}

def combinar_con_ia(filtros, filtros_ai):
    """Usa el valor sugerido por el LLM solo si pasa la misma lista blanca."""
    combinados = dict(filtros)
    if not isinstance(filtros_ai, dict):
        return combinados
    for campo in CAMPOS_BUSQUEDA:
        sugerido = filtros_ai.get(campo)
        if not sugerido:
            continue
        try:
            combinados[campo] = validar_filtro(campo, sugerido) or filtros[campo]
        except EntradaInvalida:
            registro.warning("Se descartó la sugerencia de la IA para el campo %s", campo)
    return combinados

def buscar_en_prolog(maximo=10, **filtros_validados):
    """Ejecuta buscar_aves/13 con filtros ya validados. Puede lanzar excepciones de Prolog."""
    return list(prolog.query(consulta_busqueda(**filtros_validados), maxresult=maximo))

# --- Obtener color dominante de imagen ---
def obtener_color_dominante(imagen):
    try:
        color_thief = ColorThief(imagen)
        return color_thief.get_color(quality=1)
    except Exception as error:
        registro.warning("No se pudo obtener el color dominante (%s)", type(error).__name__)
        return None

# --- Convertir RGB a nombre de color ---
def convertir_rgb_a_nombre(rgb):
    # Colores básicos con sus valores RGB aproximados
    colores_basicos = {
        "rojo": (255, 0, 0),
        "verde": (0, 255, 0),
        "azul": (0, 0, 255),
        "amarillo": (255, 255, 0),
        "naranja": (255, 165, 0),
        "morado": (128, 0, 128),
        "rosa": (255, 192, 203),
        "marrón": (165, 42, 42),
        "gris": (128, 128, 128),
        "negro": (0, 0, 0),
        "blanco": (255, 255, 255),
        "celeste": (135, 206, 235),
        "turquesa": (64, 224, 208),
        "beige": (245, 245, 220),
        "café": (139, 69, 19)
    }
    
    # Función para calcular la distancia entre dos colores RGB
    def distancia(c1, c2):
        return sum((a - b) ** 2 for a, b in zip(c1, c2))
    
    # Encontrar el color más cercano
    color_cercano = min(colores_basicos.items(), key=lambda x: distancia(rgb, x[1]))
    return color_cercano[0]

# --- Limpiar tildes/caracteres raros ---
def normalizar_texto(texto):
    if texto:
        try:
            return texto.encode('latin1').decode('utf8')
        except Exception:
            return texto
    return texto

# --- IA: enriquecer filtros de búsqueda ---
def enriquecer_filtros(filtros):
    prompt = (
        f"Con base en estos filtros de búsqueda de aves: {filtros}, "
        "proporciona sugerencias o información adicional en formato JSON "
        "para ayudar a mejorar la búsqueda. Solo responde con JSON válido."
    )

    respuesta = cliente_openai.chat.completions.create(
        model=despliegue_modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    contenido = respuesta.choices[0].message.content

    if contenido.startswith("```"):
        contenido = contenido.strip("`").replace("json", "").strip()

    return json.loads(contenido)

# --- Ruta principal de interfaz ---
@app.route("/")
def inicio():
    # Aves destacadas. Fotos de Wikimedia Commons con licencia libre, servidas desde static/aves/
    # (miniaturas de 800 px). Autoría y licencia en cada entrada y en ATRIBUCIONES.md.
    aves_destacadas = [
        {
            "nombre": "Quetzal", 
            "descripcion": "El quetzal resplandeciente es una de las aves más emblemáticas de Costa Rica, conocido por su plumaje verde brillante y larga cola.",
            "imagen": url_for("static", filename="aves/quetzal.jpg"),
            "alt": "Quetzal resplandeciente (Pharomachrus mocinno)",
            "credito": {"autor": "Frank Vassen", "licencia": "CC BY 2.0", "licencia_url": "https://creativecommons.org/licenses/by/2.0/", "fuente": "https://commons.wikimedia.org/wiki/File:Resplendent_Quetzal,_Mirador_de_Quetzales,_Costa_Rica.jpg"}
        },
        {
            "nombre": "Tucán", 
            "descripcion": "Los tucanes son aves tropicales conocidas por sus picos grandes y coloridos. En Costa Rica se pueden encontrar varias especies.",
            "imagen": url_for("static", filename="aves/tucan.jpg"),
            "alt": "Tucán pico iris (Ramphastos sulfuratus)",
            "credito": {"autor": "Bernard Gagnon", "licencia": "CC0 1.0", "licencia_url": "https://creativecommons.org/publicdomain/zero/1.0/", "fuente": "https://commons.wikimedia.org/wiki/File:Keel-billed_toucan_in_Costa_Rica_01.jpg"}
        },
        {
            "nombre": "Lapa Roja", 
            "descripcion": "Las lapas rojas son guacamayos de colores brillantes que habitan en los bosques tropicales de Costa Rica.",
            "imagen": url_for("static", filename="aves/lapa-roja.jpg"),
            "alt": "Lapa roja (Ara macao) en vuelo",
            "credito": {"autor": "ImagePerson", "licencia": "CC BY 4.0", "licencia_url": "https://creativecommons.org/licenses/by/4.0/", "fuente": "https://commons.wikimedia.org/wiki/File:Scarlet_Macaw_(Ara_macao)_Costa_Rica_8598.jpg"}
        },
        {
            "nombre": "Yigüirro", 
            "descripcion": "El yigüirro es el ave nacional de Costa Rica, conocido por su hermoso canto y presencia en todo el país.",
            "imagen": url_for("static", filename="aves/yiguirro.jpg"),
            "alt": "Yigüirro (Turdus grayi)",
            "credito": {"autor": "Fneskljvnl", "licencia": "CC BY 4.0", "licencia_url": "https://creativecommons.org/licenses/by/4.0/", "fuente": "https://commons.wikimedia.org/wiki/File:Clay-Colored-Thrush-CR.jpg"}
        },
        {
            "nombre": "Tángara", 
            "descripcion": "Las tángaras son aves pequeñas y coloridas que se encuentran en los bosques y jardines de Costa Rica.",
            "imagen": url_for("static", filename="aves/tangara.jpg"),
            "alt": "Tangara lomo escarlata, macho (Ramphocelus passerinii)",
            "credito": {"autor": "Hans Hillewaert", "licencia": "CC BY-SA 3.0", "licencia_url": "https://creativecommons.org/licenses/by-sa/3.0/", "fuente": "https://commons.wikimedia.org/wiki/File:Ramphocelus_passerinii_(male).jpg"}
        }
    ]
    
    return render_template("index.html", es_inicio=True, aves_destacadas=aves_destacadas)

# --- Interfaz gráfica con formulario de búsqueda ---
@app.route("/busca", methods=["GET", "POST"])
def buscar_formulario():
    resultados = []
    color_detectado = None
    color = habitat = peso = alimento = ""

    if request.method == "POST":
        color = request.form.get("color", "").lower().strip()
        habitat = request.form.get("habitat", "").lower().strip()
        peso = request.form.get("peso", "").lower().strip()
        alimento = request.form.get("alimento", "").lower().strip()

        def pagina(error=None, codigo=200):
            return render_template(
                "index.html",
                resultados=resultados,
                color_detectado=color_detectado,
                color=color,
                habitat=habitat,
                peso=peso,
                alimento=alimento,
                error=error
            ), codigo

        imagen = request.files.get("imagen")
        if imagen and imagen.filename:
            rgb = obtener_color_dominante(imagen.stream)
            if rgb:
                color_detectado = convertir_rgb_a_nombre(rgb)
                print(f"Color detectado de imagen: {color_detectado}")
                if not color:
                    color = color_detectado

        try:
            filtros = leer_filtros({"color": color, "habitat": habitat, "peso": peso, "alimento": alimento})
        except EntradaInvalida as error:
            return pagina(str(error), 400)

        try:
            filtros_ai = enriquecer_filtros(filtros)
        except Exception as error:
            registro.warning("No se pudieron enriquecer los filtros con IA (%s)", type(error).__name__)
            filtros_ai = {}

        try:
            for solucion in buscar_en_prolog(**combinar_con_ia(filtros, filtros_ai)):
                resultados.append({
                    "Nombre": normalizar_texto(solucion["Nombre"]),
                    "Reino": normalizar_texto(solucion["Reino"]),
                    "Filo": normalizar_texto(solucion["Filo"]),
                    "Color": normalizar_texto(solucion["Color"]),
                    "Peso": normalizar_texto(solucion["Peso"]),
                    "Alimento": normalizar_texto(solucion["Alimento"]),
                    "Habitat": normalizar_texto(solucion["Habitat"]),
                    "Descripcion": normalizar_texto(solucion["Descripcion"])
                })

        except Exception as error:
            registro.error("Falló la consulta Prolog del formulario (%s)", type(error).__name__)
            resultados = []
            return pagina(MENSAJE_ERROR_BUSQUEDA, 500)

    return render_template(
        "index.html",
        resultados=resultados,
        color_detectado=color_detectado,
        color=color,
        habitat=habitat,
        peso=peso,
        alimento=alimento
    )

# --- API REST para búsqueda desde frontend externo ---
@app.route("/buscar", methods=["POST"])
def buscar_api():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON con los filtros color, habitat, peso o alimento."}), 400

    try:
        filtros = leer_filtros(datos)
    except EntradaInvalida as error:
        return jsonify({"error": str(error)}), 400

    try:
        filtros_ai = enriquecer_filtros(filtros)
    except Exception as error:
        registro.warning("No se pudieron enriquecer los filtros con IA (%s)", type(error).__name__)
        filtros_ai = {}

    resultados = []
    try:
        for solucion in buscar_en_prolog(**combinar_con_ia(filtros, filtros_ai)):
            resultados.append({
                "nombre": normalizar_texto(solucion["Nombre"]),
                "color": normalizar_texto(solucion["Color"]),
                "habitat": normalizar_texto(solucion["Habitat"]),
                "peso": normalizar_texto(solucion["Peso"]),
                "alimento": normalizar_texto(solucion["Alimento"]),
                "descripcion": normalizar_texto(solucion["Descripcion"])
            })

    except Exception as error:
        registro.error("Falló la consulta Prolog de la API (%s)", type(error).__name__)
        return jsonify({"error": MENSAJE_ERROR_BUSQUEDA}), 500

    return jsonify(resultados)

# --- Validar formato y tamaño de archivo ---
def validar_imagen(archivo):
    # Extensiones permitidas
    EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}
    # Tamaño máximo en bytes (5MB)
    TAMANO_MAXIMO = 5 * 1024 * 1024
    
    if not archivo or not archivo.filename:
        return False, "No se proporcionó imagen"
        
    # Verificar extensión
    extension = archivo.filename.rsplit('.', 1)[1].lower() if '.' in archivo.filename else ''
    if extension not in EXTENSIONES_PERMITIDAS:
        return False, f"Formato de archivo no permitido. Use: {', '.join(EXTENSIONES_PERMITIDAS)}"
    
    # Verificar tamaño
    archivo.seek(0, 2)  # Ir al final del archivo
    tamano = archivo.tell()  # Obtener posición (tamaño)
    archivo.seek(0)  # Volver al inicio
    
    if tamano > TAMANO_MAXIMO:
        return False, f"El archivo excede el tamaño máximo permitido de 5MB"
    
    return True, ""

# --- IA: analizar imagen de ave con Azure OpenAI ---
def analizar_imagen_ave(imagen_stream):
    prompt = (
        "Analiza esta imagen de un ave y proporciona la siguiente información en formato JSON:\n"
        "1. nombre: nombre común del ave\n"
        "2. nombre_cientifico: nombre científico del ave\n"
        "3. familia: familia taxonómica\n"
        "4. reino: reino biológico\n"
        "5. filo: filo taxonómico\n"
        "6. color: color principal del ave\n"
        "7. peso: peso aproximado\n"
        "8. alimento: tipo de alimentación\n"
        "9. habitat: hábitat natural\n"
        "10. descripcion: breve descripción\n\n"
        "Responde SOLO con el objeto JSON, sin explicaciones adicionales."
    )
    
    try:
        # Aquí normalmente enviaríamos la imagen a Azure OpenAI
        # Como no podemos enviar la imagen directamente en este ejemplo,
        # simularemos la respuesta basada en el color detectado
        
        # Primero detectamos el color
        imagen_stream.seek(0)  # Asegurarse de estar al inicio del stream
        rgb = obtener_color_dominante(imagen_stream)
        if not rgb:
            return None, "No se pudo obtener el color principal de la imagen"
            
        color_nombre = convertir_rgb_a_nombre(rgb)
        print(f"Color detectado en la imagen: {color_nombre}")
        
        # Ahora enviamos el prompt con el color detectado
        prompt_con_color = (
            f"Analiza una imagen de un ave con color principal '{color_nombre}' "
            "y proporciona la siguiente información en formato JSON:\n"
            "1. nombre: nombre común del ave\n"
            "2. nombre_cientifico: nombre científico del ave\n"
            "3. familia: familia taxonómica\n"
            "4. reino: reino biológico\n"
            "5. filo: filo taxonómico\n"
            "6. color: color principal del ave (incluye '{color_nombre}')\n"
            "7. peso: peso aproximado\n"
            "8. alimento: tipo de alimentación\n"
            "9. habitat: hábitat natural\n"
            "10. descripcion: breve descripción\n\n"
            "Responde SOLO con el objeto JSON, sin explicaciones adicionales."
        )
        
        respuesta = cliente_openai.chat.completions.create(
            model=despliegue_modelo,
            messages=[{"role": "user", "content": prompt_con_color}],
            temperature=0.7
        )
        contenido = respuesta.choices[0].message.content
        
        # Limpiar el contenido si viene con formato markdown
        if contenido.startswith("```"):
            contenido = contenido.strip("`").replace("json", "").strip()
            
        # Convertir a JSON
        datos_ave = json.loads(contenido)
        return datos_ave, None
        
    except LimiteAzureError as error:
        return None, str(error)
    except Exception as error:
        registro.error("Error al analizar imagen (%s); revise la configuracion local.", type(error).__name__)
        return None, "No se pudo analizar la imagen. Intente de nuevo más tarde."

# --- Validar datos con base de conocimiento Prolog ---
def validar_con_prolog(datos_ia):
    try:
        # Los datos vienen del LLM: se tratan como entrada no confiable.
        resultados = []
        partes_nombre = str(datos_ia.get("nombre_cientifico") or "").split()
        if partes_nombre:
            try:
                genero = validar_genero(partes_nombre[0])
                resultados = buscar_en_prolog(maximo=5, nombre=genero)
            except EntradaInvalida:
                registro.warning("Se descartó el nombre científico sugerido por la IA")

        # Si no hay resultados, intentar buscar por color
        if not resultados and datos_ia.get("color"):
            try:
                color = validar_filtro("color", datos_ia.get("color"))
                if color:
                    resultados = buscar_en_prolog(maximo=5, color=color)
            except EntradaInvalida:
                registro.warning("Se descartó el color sugerido por la IA")
        
        # Si encontramos coincidencias, usar los datos de Prolog
        if resultados:
            solucion = resultados[0]  # Tomar la primera coincidencia
            datos_prolog = {
                "nombre": normalizar_texto(solucion["Nombre"]),
                "reino": normalizar_texto(solucion["Reino"]),
                "filo": normalizar_texto(solucion["Filo"]),
                "color": normalizar_texto(solucion["Color"]),
                "peso": normalizar_texto(solucion["Peso"]),
                "alimento": normalizar_texto(solucion["Alimento"]),
                "habitat": normalizar_texto(solucion["Habitat"]),
                "descripcion": normalizar_texto(solucion["Descripcion"])
            }
            
            # Combinar datos, priorizando Prolog
            datos_combinados = datos_ia.copy()
            for campo, valor in datos_prolog.items():
                if campo in datos_combinados and valor:
                    datos_combinados[campo] = valor
            
            return datos_combinados, True
        
        return datos_ia, False
        
    except Exception as error:
        registro.error("Error validando con Prolog (%s)", type(error).__name__)
        return datos_ia, False

# --- IA: identificar posibles aves desde imagen ---
@app.route("/identificar", methods=["POST"])
def identificar_desde_imagen():
    imagen = request.files.get("imagen")
    if not imagen or not imagen.filename:
        return jsonify({"error": "No se proporcionó imagen"}), 400

    rgb = obtener_color_dominante(imagen.stream)
    if not rgb:
        return jsonify({"error": "No se pudo obtener el color principal"}), 500

    color_nombre = convertir_rgb_a_nombre(rgb)
    print(f"Color detectado: {color_nombre}")

    prompt = (
        f"Con base en el color principal '{color_nombre}' detectado en una imagen, "
        f"¿qué aves de Costa Rica podrían coincidir con ese color? "
        "Devuélvelo como una lista JSON con nombres comunes y científicos. "
        "No incluyas explicaciones, solo el JSON con las coincidencias."
    )

    try:
        respuesta = cliente_openai.chat.completions.create(
            model=despliegue_modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        contenido = respuesta.choices[0].message.content
        if contenido.startswith("```"):
            contenido = contenido.strip("`").replace("json", "").strip()
        aves = json.loads(contenido)
    except LimiteAzureError as error:
        return jsonify({"error": str(error)}), 429
    except Exception:
        return jsonify({"error": "No se pudo obtener la respuesta IA."}), 500

    return jsonify({
        "color_detectado": color_nombre,
        "aves_posibles": aves
    })

# --- Analizar imagen de ave y obtener datos detallados ---
@app.route("/analizar-ave", methods=["GET", "POST"])
def analizar_ave():
    resultados = []
    datos_ia_json = None
    error = None
    imagen_subida = False
    validado_prolog = False
    
    if request.method == "POST":
        # Verificar si se subió una imagen
        if 'imagen' not in request.files:
            error = "No se proporcionó ninguna imagen"
        else:
            imagen = request.files['imagen']
            
            # Validar formato y tamaño
            valido, mensaje = validar_imagen(imagen)
            if not valido:
                error = mensaje
            else:
                imagen_subida = True
                # Analizar la imagen con IA
                datos_ia, error_analisis = analizar_imagen_ave(imagen)
                
                if error_analisis:
                    error = error_analisis
                elif datos_ia:
                    # Guardar JSON crudo para mostrar
                    datos_ia_json = json.dumps(datos_ia, indent=2)
                    
                    # Validar con la base de conocimiento Prolog
                    datos_finales, validado_prolog = validar_con_prolog(datos_ia)
                    
                    # Crear un resultado para mostrar en el formato que espera la plantilla
                    resultados.append({
                        "nombre": datos_finales.get("nombre", "Desconocido"),
                        "Reino": datos_finales.get("reino", "Animalia"),
                        "Filo": datos_finales.get("filo", "Chordata"),
                        "Color": datos_finales.get("color", "Desconocido"),
                        "Peso": datos_finales.get("peso", "Desconocido"),
                        "Alimento": datos_finales.get("alimento", "Desconocido"),
                        "Habitat": datos_finales.get("habitat", "Desconocido"),
                        "Descripcion": datos_finales.get("descripcion", "Sin descripción disponible"),
                        "Familia": datos_finales.get("familia", "Desconocida"),
                        "NombreCientifico": datos_finales.get("nombre_cientifico", "Desconocido")
                    })
    
    return render_template(
        "index.html",
        resultados=resultados,
        datos_ia_json=datos_ia_json,
        error=error,
        imagen_subida=imagen_subida,
        validado_prolog=validado_prolog,
        es_analisis=True  # Para indicar que estamos en modo análisis
    )

if __name__ == "__main__":
    app.run(port=5001)
