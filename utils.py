import streamlit as st
import json
import tempfile
import pandas as pd
import io
import re
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Configuración inicial
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
    json.dump(json.loads(st.secrets["SERVICE_ACCOUNT_JSON"]), f)
    SERVICE_ACCOUNT_FILE = f.name

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
docs_service = build("docs", "v1", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)
sheets_service = build("sheets", "v4", credentials=creds)

TEMPLATE_ID = "1I2jMQ1IjmG6_22dC7u6LYQfQzlND4WIvEusd756LFuo"

# === Función base para llamar a GPT
def call_gpt(prompt):
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# === Funciones de generación individuales
def generar_perfil_ingreso(nombre_del_curso, nivel, publico, student_persona, siguiente_learning_unit):
    prompt = f"""Mejora el perfil de ingreso para el curso de {nombre_del_curso}, tomando como base el siguiente perfil:
    {student_persona}
    
    Este curso es de nivel {nivel} y está dirigido a:
    {publico}
    
    El siguiente curso sugerido después de este es: {siguiente_learning_unit} (No lo menciones directamente).
    """
    return call_gpt(prompt)

def generar_objetivos(nombre_del_curso, nivel, perfil_ingreso, objetivos_raw):
    prompt = f"""Basándote en los siguientes objetivos iniciales:
    {objetivos_raw}
    
    Redacta los objetivos finales del curso "{nombre_del_curso}" (nivel {nivel}), dirigido a este perfil:
    {perfil_ingreso}
    
    Devuelve un objetivo general y 5 objetivos secundarios en tabla Markdown con columnas: Número, Nombre, Descripción.
    """
    return call_gpt(prompt)

def generar_perfil_egreso(nombre_del_curso, perfil_ingreso, objetivos_mejorados, siguiente_learning_unit):
    prompt = f"""Redacta el perfil de egreso para el curso "{nombre_del_curso}", basado en estos objetivos:
    {objetivos_mejorados}
    
    Este curso está dirigido a:
    {perfil_ingreso}
    
    Y el siguiente paso ideal sería el curso: {siguiente_learning_unit} (no lo menciones directamente).
    
    Incluye:
    - Un párrafo con el perfil de egreso.
    - Una lista de 5 habilidades principales con bullet points."""
    return call_gpt(prompt)

def generar_outline(nombre_del_curso, nivel, perfil_ingreso, objetivos_mejorados):
    prompt = f"""Crea un temario tipo tabla Markdown para el curso "{nombre_del_curso}" (nivel {nivel}).
    
    Dirigido a: {perfil_ingreso}
    
    Objetivos:
    {objetivos_mejorados}
    
    Requisitos:
        - El curso dura 3 semanas.
        - Cada semana incluye exactamente 4 clases (12 clases en total).
        - No repitas títulos ni uses “parte 1 / parte 2”.
        - Cada clase debe tener un enfoque único.

        Entrega una tabla en formato Markdown con las siguientes columnas:

        1. Semana  
        2. Clase (nombre breve y distinto)  
        3. Conceptos clave (exactamente 3, numerados, distintos entre clases)  
        4. Descripción (párrafo claro que explique qué se verá en la clase. Será usado por otro modelo para crear una presentación desde cero. Incluye contexto, ejemplos, enfoque didáctico y qué aprenderá el alumno).  
        5. Objetivos (3 objetivos claros, distintos entre sí, centrados en habilidades o conocimientos que se desarrollarán en esa clase)

        Ejemplo para “Conceptos clave”:
        1. Ciclo de vida del dato  
        2. Analítica descriptiva  
        3. KPIs de negocio

        Ejemplo para “Objetivos”:
        - Comprender las fases del ciclo de vida de los datos.  
        - Analizar un ejemplo real usando analítica descriptiva.  
        - Evaluar qué KPI es más relevante según el contexto de negocio.

        Asegúrate de que:
        - No se repitan conceptos clave entre clases.
        - Los objetivos estén bien diferenciados."""
    
    return call_gpt(prompt)

# === Generar partes del syllabus
def generar_syllabus_partes(perfil_ingreso, perfil_egreso, objetivos_mejorados, outline, nombre_del_curso, anio):
    # Prompt para generar las partes generales
    prompt_general = f"""Redacta el contenido del syllabus para el curso "{nombre_del_curso}" del año {anio}. Devuelve solo el texto sin formato.
    
    Incluye las siguientes partes:
    
    [GENERALIDADES_DEL_PROGRAMA]
    Parrafo corto que combine la descripción del curso, el objetivo general (en una frase) y el perfil de egreso (en una frase).
    
    [PERFIL_INGRESO]
    Un parrafo corto con el perfil de ingreso.
    
    [DETALLES_PLAN_ESTUDIOS]
    Una lista con las clases del curso. Cada clase debe tener título y una breve descripción.
    
    Perfil de ingreso:
    {perfil_ingreso}
    
    Perfil de egreso:
    {perfil_egreso}
    
    Objetivos:
    {objetivos_mejorados}
    
    Outline:
    {outline}"""
    
    respuesta_general = call_gpt(prompt_general)
    
    def extraer_seccion(etiqueta, texto):
        patron = rf"\[{etiqueta}\]\n(.*?)(?=\[|\Z)"
        resultado = re.search(patron, texto, re.DOTALL)
        return resultado.group(1).strip() if resultado else ""
    
    generalidades = extraer_seccion("GENERALIDADES_DEL_PROGRAMA", respuesta_general)
    ingreso = extraer_seccion("PERFIL_INGRESO", respuesta_general)
    detalles = extraer_seccion("DETALLES_PLAN_ESTUDIOS", respuesta_general)
    
    # Prompt específico para generar los objetivos secundarios en el formato requerido
    prompt_objetivos = f"""Extrae los 3 objetivos secundarios más importantes de la siguiente tabla de objetivos:
    {objetivos_mejorados}
    
    Para cada uno, proporciona:
    [TITULO_PRIMER_OBJETIVO_SECUNDARIO]
    El título del primer objetivo secundario (solo el título del objetivo, sin número ni descripción).
    
    [DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO]
    Una descripción muy breve del primer objetivo secundario (máximo 3 líneas).
    
    [TITULO_SEGUNDO_OBJETIVO_SECUNDARIO]
    El título del segundo objetivo secundario (solo el título del objetivo,, sin número ni descripción).
    
    [DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO]
    Una descripción muy breve del segundo objetivo secundario (máximo 3 líneas).
    
    [TITULO_TERCER_OBJETIVO_SECUNDARIO]
    El título del tercer objetivo secundario (solo el título del objetivo,, sin número ni descripción).
    
    [DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO]
    Una descripción muy breve del tercer objetivo secundario (máximo 3 líneas).
    
    Las descripciones deben ser concisas y no repetir el contenido de las generalidades del programa.
    """
    
    respuesta_objetivos = call_gpt(prompt_objetivos)
    
    titulo_primer_objetivo = extraer_seccion("TITULO_PRIMER_OBJETIVO_SECUNDARIO", respuesta_objetivos)
    descripcion_primer_objetivo = extraer_seccion("DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO", respuesta_objetivos)
    titulo_segundo_objetivo = extraer_seccion("TITULO_SEGUNDO_OBJETIVO_SECUNDARIO", respuesta_objetivos)
    descripcion_segundo_objetivo = extraer_seccion("DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO", respuesta_objetivos)
    titulo_tercer_objetivo = extraer_seccion("TITULO_TERCER_OBJETIVO_SECUNDARIO", respuesta_objetivos)
    descripcion_tercer_objetivo = extraer_seccion("DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO", respuesta_objetivos)
    
    return (
        generalidades, 
        ingreso, 
        titulo_primer_objetivo,
        descripcion_primer_objetivo,
        titulo_segundo_objetivo,
        descripcion_segundo_objetivo,
        titulo_tercer_objetivo,
        descripcion_tercer_objetivo,
        detalles
    )

# === Reemplazo de placeholders en plantilla
def replace_placeholder(document_id, placeholder, new_text):
    requests = [{
        "replaceAllText": {
            "containsText": {
                "text": placeholder,
                "matchCase": True
            },
            "replaceText": new_text
        }
    }]
    docs_service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()

# === Ensamblar y generar syllabus completo con plantilla
def generar_syllabus_completo(nombre_del_curso, nivel, objetivos_mejorados, publico, siguiente, perfil_ingreso, perfil_egreso, outline):
    anio = 2025
    
    (
        generalidades, 
        ingreso, 
        titulo_primer_objetivo,
        descripcion_primer_objetivo,
        titulo_segundo_objetivo,
        descripcion_segundo_objetivo,
        titulo_tercer_objetivo,
        descripcion_tercer_objetivo,
        detalles
    ) = generar_syllabus_partes(
        perfil_ingreso, perfil_egreso, objetivos_mejorados, outline, nombre_del_curso, anio
    )
    
    template_copy = drive_service.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": f"Syllabus - {nombre_del_curso}"}
    ).execute()
    
    document_id = template_copy["id"]
    
    replace_placeholder(document_id, "{{nombre_del_curso}}", nombre_del_curso)
    replace_placeholder(document_id, "{{anio}}", str(anio))
    replace_placeholder(document_id, "{{generalidades_del_programa}}", generalidades)
    replace_placeholder(document_id, "{{perfil_ingreso}}", ingreso)
    
    # Reemplazar los placeholders de los objetivos secundarios
    replace_placeholder(document_id, "{{titulo_primer_objetivo_secundario}}", titulo_primer_objetivo)
    replace_placeholder(document_id, "{{descripcion_primer_objetivo_secundario}}", descripcion_primer_objetivo)
    replace_placeholder(document_id, "{{titulo_segundo_objetivo_secundario}}", titulo_segundo_objetivo)
    replace_placeholder(document_id, "{{descripcion_segundo_objetivo_secundario}}", descripcion_segundo_objetivo)
    replace_placeholder(document_id, "{{titulo_tercer_objetivo_secundario}}", titulo_tercer_objetivo)
    replace_placeholder(document_id, "{{descripcion_tercer_objetivo_secundario}}", descripcion_tercer_objetivo)
    
    replace_placeholder(document_id, "{{detalles_plan_estudios}}", detalles)
        
    # Luego, dar permisos de escritura al dominio
    drive_service.permissions().create(
        fileId=document_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()
    
    return f"https://docs.google.com/document/d/{document_id}/edit"

# Modificada para aceptar el outline como parámetro
def generar_outline_csv(nombre_del_curso, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline=None):
    # Si no se proporciona un outline, generarlo
    if outline is None:
        prompt = f"""
        Eres un experto en diseño instruccional. Crea el outline de un curso llamado "{nombre_del_curso}" (nivel {nivel}) con base en estos objetivos:

        {objetivos_mejorados}

        Público objetivo: {perfil_ingreso}

        Requisitos:
        - El curso dura 3 semanas.
        - Cada semana incluye exactamente 4 clases (12 clases en total).
        - No repitas títulos ni uses “parte 1 / parte 2”.
        - Cada clase debe tener un enfoque único.

        Entrega una tabla en formato Markdown con las siguientes columnas:

        1. Semana  
        2. Clase (nombre breve y distinto)  
        3. Conceptos clave (exactamente 3, numerados, distintos entre clases)  
        4. Descripción (párrafo claro que explique qué se verá en la clase. Será usado por otro modelo para crear una presentación desde cero. Incluye contexto, ejemplos, enfoque didáctico y qué aprenderá el alumno).  
        5. Objetivos (3 objetivos claros, distintos entre sí, centrados en habilidades o conocimientos que se desarrollarán en esa clase)

        Ejemplo para “Conceptos clave”:
        1. Ciclo de vida del dato  
        2. Analítica descriptiva  
        3. KPIs de negocio

        Ejemplo para “Objetivos”:
        - Comprender las fases del ciclo de vida de los datos.  
        - Analizar un ejemplo real usando analítica descriptiva.  
        - Evaluar qué KPI es más relevante según el contexto de negocio.

        Asegúrate de que:
        - No se repitan conceptos clave entre clases.
        - Los objetivos estén bien diferenciados.
        """
        
        markdown = call_gpt(prompt)
    else:
        # Usar el outline proporcionado
        markdown = outline
    
    # Convertir Markdown a DataFrame
    lines = [line.strip() for line in markdown.splitlines() if "|" in line and not line.startswith("|---")]
    clean = "\n".join(lines)
    df = pd.read_csv(io.StringIO(clean), sep="|", engine="python", skipinitialspace=True)
    df = df.dropna(axis=1, how="all")
    df.columns = [col.strip() for col in df.columns]
    
    # Crear Google Sheets
    sheet = sheets_service.spreadsheets().create(
        body={"properties": {"title": f"Outline - {nombre_del_curso}"}},
        fields="spreadsheetId"
    ).execute()
    
    spreadsheet_id = sheet["spreadsheetId"]
    
    # Preparar datos para la API
    values = [df.columns.tolist()]
    values.extend(df.values.tolist())
    
    # Actualizar hoja
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
    
    # Dar formato
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "gridProperties": {
                        "frozenRowCount": 1
                    }
                },
                "fields": "gridProperties.frozenRowCount"
            }
        },
        {
            "repeatCell": {
                "range": {
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {
                            "red": 0.2,
                            "green": 0.2,
                            "blue": 0.2
                        },
                        "textFormat": {
                            "foregroundColor": {
                                "red": 1.0,
                                "green": 1.0,
                                "blue": 1.0
                            },
                            "bold": True
                        }
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)"
            }
        }
    ]
    
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()
    

    # Compartir
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()
    
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
