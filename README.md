# Aves de Costa Rica

**Caso de estudio:** [en español](https://eduardoleo.github.io/proyectos/aves-costa-rica/) · [in English](https://eduardoleo.github.io/en/projects/aves-costa-rica/)

Consulta de características de aves con Flask, Prolog y respuestas de Azure OpenAI. El flujo de imagen extrae únicamente el color dominante y envía texto sobre ese color; no envía la imagen a Azure. Las sugerencias no identifican visualmente una especie ni constituyen precisión validada.

## Estado de funcionalidades

- Implementado y verificado: lectura de configuración por dotenv, cinco fixtures demo sin Azure, manejo de 429 probado con un error simulado y página inicial demo HTTP 200.
- Implementado con verificación mínima: cliente Azure; una única petición corta respondió correctamente.
- Simulado: cinco casos fijos por color; se marcan como simulados.
- Implementado sin verificar de punta a punta: consultas Prolog, búsqueda por formulario y flujos de imagen.
- Pendiente: seguridad de términos Prolog, evaluación de calidad de sugerencias y fijación de versiones de dependencias.

## Equipo y contribuciones

Proyecto desarrollado en equipo de 3 estudiantes en la UIA (curso Lenguajes y Paradigmas, 2025).

**Mi contribución:** desarrollo principal: base de conocimiento en Prolog, back end Flask, integración con Azure OpenAI y front end. Proyecto académico en equipo; los compañeros contribuyeron con correcciones puntuales.

## Derechos

© 2025–2026 Eduardo León Hernández. Todos los derechos reservados (ver [LICENSE](LICENSE)).
El código se publica como muestra de trabajo: se puede ver y evaluar, pero no copiar,
modificar, distribuir ni reutilizar sin permiso escrito. Las fotos de la portada tienen
sus propias licencias libres (ver [ATRIBUCIONES.md](ATRIBUCIONES.md)).

## Arranque de esta copia

Requiere Python y SWI-Prolog disponible para PySwip. Desde la raiz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe src/Main/app.py
```

El .env se carga desde la raiz con python-dotenv, sin sobrescribir variables existentes del proceso. Para demo mantener AVES_MODO_DEMO=1: hay cinco casos fijos simulados por color (verde, rojo, amarillo, azul y negro); no son identificaciones y no llaman a Azure. Para Azure usar AVES_MODO_DEMO=0 y configurar las cuatro variables AZURE_OPENAI. Endpoint, clave, despliegue y version se leen del entorno. API estable v1: https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat .

La cuota 429 provoca un unico reintento despues de dos segundos y, si persiste, un mensaje para esperar. El SDK no hace reintentos adicionales.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Limitaciones: las consultas Prolog interpoladas y los flujos completos siguen pendientes de revision. Los casos demo son simulados. Dependencias sin versiones fijadas. No se presenta como un clasificador visual validado.

## Verificacion de esta copia (1 de octubre de 2026)

Dos pruebas offline correctas: cinco colores demo y un reintento ante 429 simulado. Pagina inicial en modo demo: HTTP 200 con Flask test_client y SWI-Prolog disponible. Una unica llamada minima a Azure: respuesta correcta; no demuestra precision ni valida los flujos completos. La prueba real no tuvo reintentos.
