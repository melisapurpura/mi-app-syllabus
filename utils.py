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
    prompt = f"""Mejora el perfil de ingreso para el curso de {nombre_del_curso}, tomando como base el siguiente perfil de estudiante:
{student_persona}

Este curso es de nivel {nivel} y está dirigido a:
{publico}

El siguiente curso sugerido después de este es: {siguiente_learning_unit}
(No lo menciones directamente)."""
    return call_gpt(prompt)

def generar_objetivos(nombre_del_curso, nivel, perfil_ingreso, objetivos_raw):
    prompt = f"""Basándote en los siguientes objetivos iniciales:
{objetivos_raw}

Redacta los objetivos finales del curso "{nombre_del_curso}" (nivel {nivel}), dirigido a este perfil:
{perfil_ingreso}

Devuelve un objetivo general y 5 objetivos secundarios en tabla Markdown con columnas: Número, Nombre, Descripción."""
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
    
    El curso debe tener exactamente 3 semanas, con 4 clases por semana (total 12 clases).
    Incluye columnas: Semana, Clase, Conceptos clave, Descripción, Objetivos.
    Asegúrate de numerar las clases del 1 al 12 y distribuirlas equitativamente en las 3 semanas."""
    return call_gpt(prompt)

# === Generar partes del syllabus
def generar_syllabus_partes(perfil_ingreso, perfil_egreso, objetivos_mejorados, outline, nombre_del_curso, anio):
    prompt = f"""Redacta el contenido del syllabus para el curso "{nombre_del_curso}" del año {anio}. Devuelve solo las secciones solicitadas, separadas claramente con etiquetas.

Incluye las siguientes partes:

1. [GENERALIDADES_DEL_PROGRAMA]
Parrafo corto que combine la descripción del curso, el objetivo general (en una frase) y el perfil de egreso (en otra frase).

2. [PERFIL_INGRESO]
Un parrafo corto con el perfil de ingreso.

3. [DESCRIPCION_PLAN_ESTUDIOS]
Tres párrafos muy breves. Cada uno debe comenzar con el título de un objetivo secundario (sin decir "objetivo") seguido de su descripción.

4. [DETALLES_PLAN_ESTUDIOS]
Una lista con las clases del curso. Cada clase debe tener título y una breve descripción.

Perfíl de ingreso:
{perfil_ingreso}

Perfil de egreso:
{perfil_egreso}

Objetivos:
{objetivos_mejorados}

Outline:
{outline}"""
    respuesta = call_gpt(prompt)

    def extraer_seccion(etiqueta, texto):
        patron = rf"\[{etiqueta}\]\n(.*?)(?=\n\[|\Z)"
        resultado = re.search(patron, texto, re.DOTALL)
        return resultado.group(1).strip() if resultado else ""

    generalidades = extraer_seccion("GENERALIDADES_DEL_PROGRAMA", respuesta)
    ingreso = extraer_seccion("PERFIL_INGRESO", respuesta)
    descripcion = extraer_seccion("DESCRIPCION_PLAN_ESTUDIOS", respuesta)
    detalles = extraer_seccion("DETALLES_PLAN_ESTUDIOS", respuesta)

    return generalidades, ingreso, descripcion, detalles

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

    generalidades, ingreso, descripcion, detalles = generar_syllabus_partes(
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
    replace_placeholder(document_id, "{{descripcion_plan_estudios}}", descripcion)
    replace_placeholder(document_id, "{{detalles_plan_estudios}}", detalles)

    drive_service.permissions().create(
        fileId=document_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/document/d/{document_id}/edit"

# Modificada para aceptar el outline como parámetro
def generar_outline_csv(nombre, nivel, objetivos, publico, siguiente, outline=None):
    # Si no se proporciona un outline, generarlo
    if outline is None:
        prompt = f"""
        Crea un temario tipo tabla Markdown para un curso llamado "{nombre}" (nivel {nivel}), con estos objetivos:
        {objetivos}
        
        Público objetivo: {publico}
        Curso siguiente: {siguiente}
        
        El curso debe tener exactamente 3 semanas, con 4 clases por semana (total 12 clases).
        Incluye columnas: Semana, Clase, Conceptos clave, Descripción, Objetivos.
        Asegúrate de numerar las clases del 1 al 12 y distribuirlas equitativamente en las 3 semanas.
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
        body={"properties": {"title": f"Outline - {nombre}"}},
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
