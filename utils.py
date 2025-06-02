import streamlit as st
import json
import tempfile
import pandas as pd
import io
import re
import requests

from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Google Services Setup ===
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

# === Gemini API ===
def call_gemini(prompt: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": st.secrets["GEMINI_API_KEY"]}
    data = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    if response.status_code == 200:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    else:
        st.error(f"Error en API Gemini: {response.status_code} - {response.text}")
        raise Exception("Fallo la llamada a Gemini con API Key.")

# === Prompting y generación de datos del curso ===
@st.cache_data(show_spinner=False)
def generar_datos_generales(nombre_del_curso, nivel, publico, student_persona, siguiente, objetivos_raw):
    prompt = f"""
Actúa como experto en diseño instruccional.

Con base en los siguientes datos:
- Curso: {nombre_del_curso}
- Nivel: {nivel}
- Público objetivo: {publico}
- Perfil base del estudiante: {student_persona}
- Objetivos iniciales: {objetivos_raw}
- Curso sugerido posterior: {siguiente} (no lo menciones directamente)

Devuélveme lo siguiente, separado por etiquetas:

[PERFIL_INGRESO]
...
[OBJETIVOS]
...
[PERFIL_EGRESO]
...
[OUTLINE]
...

Los siguientes campos corresponden a los tres objetivos secundarios clave más importantes. Usa frases claras, distintas y útiles para el diseño del curso:

[TITULO_PRIMER_OBJETIVO_SECUNDARIO]
...

[DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO]
...

[TITULO_SEGUNDO_OBJETIVO_SECUNDARIO]
...

[DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO]
...

[TITULO_TERCER_OBJETIVO_SECUNDARIO]
...

[DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO]
...

El outline debe incluir exactamente 12 clases (4 por semana durante 3 semanas) y estar en formato de tabla Markdown con estas columnas:

| Clase | Título | Conceptos Clave | Objetivo 1 | Objetivo 2 | Objetivo 3 | Descripción |

Cada objetivo debe escribirse así dentro de la celda (una línea por campo):

Título: Analizar datos estructurados  
Descripción: El estudiante será capaz de identificar patrones y relaciones...
"""
    respuesta = call_gemini(prompt)

    def extraer(etiqueta):
        patron = rf"\[{etiqueta}\]\n(.*?)(?=\[|\Z)"
        r = re.search(patron, respuesta, re.DOTALL)
        return r.group(1).strip() if r else ""

    perfil_ingreso = extraer("PERFIL_INGRESO")
    objetivos = extraer("OBJETIVOS")
    perfil_egreso = extraer("PERFIL_EGRESO")
    outline = extraer("OUTLINE")

    # Nuevos campos: objetivos secundarios
    titulo1 = extraer("TITULO_PRIMER_OBJETIVO_SECUNDARIO")
    desc1 = extraer("DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO")
    titulo2 = extraer("TITULO_SEGUNDO_OBJETIVO_SECUNDARIO")
    desc2 = extraer("DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO")
    titulo3 = extraer("TITULO_TERCER_OBJETIVO_SECUNDARIO")
    desc3 = extraer("DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO")

    return perfil_ingreso, objetivos, perfil_egreso, outline, titulo1, desc1, titulo2, desc2, titulo3, desc3

# === Placeholder replacement ===
def replace_placeholder(document_id, placeholder, new_text):
    requests = [{
        "replaceAllText": {
            "containsText": {"text": placeholder, "matchCase": True},
            "replaceText": new_text
        }
    }]
    docs_service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()

# === Generación del syllabus usando objetivos directamente ===
def generar_syllabus_completo(nombre_del_curso, nivel, objetivos_mejorados, publico, siguiente,
                               perfil_ingreso, perfil_egreso, outline,
                               titulo1, desc1, titulo2, desc2, titulo3, desc3):
    anio = 2025

    def pedir_seccion(etiqueta, instruccion):
        prompt = f"""
Curso: {nombre_del_curso}
Año: {anio}
Nivel: {nivel}
Objetivos: {objetivos_mejorados}
Perfil de ingreso: {perfil_ingreso}
Perfil de egreso: {perfil_egreso}
Outline:
{outline}

Devuelve únicamente el contenido para la sección: [{etiqueta}]
{instruccion}
"""
        respuesta = call_gemini(prompt)
        return respuesta.strip()

    generalidades = pedir_seccion("GENERALIDADES_DEL_PROGRAMA", "Redacta un párrafo breve que combine descripción general del curso, su objetivo y el perfil de egreso.")
    ingreso = pedir_seccion("PERFIL_INGRESO", "Redacta un párrafo claro y directo del perfil de ingreso del estudiante.")
    detalles = pedir_seccion("DETALLES_PLAN_ESTUDIOS", "Escribe la lista de 12 clases, cada una con título y una breve descripción.")

    template_copy = drive_service.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": f"Syllabus - {nombre_del_curso}"}
    ).execute()
    document_id = template_copy["id"]

    replace_placeholder(document_id, "{{nombre_del_curso}}", nombre_del_curso)
    replace_placeholder(document_id, "{{anio}}", str(anio))
    replace_placeholder(document_id, "{{generalidades_del_programa}}", generalidades)
    replace_placeholder(document_id, "{{perfil_ingreso}}", ingreso)
    replace_placeholder(document_id, "{{detalles_plan_estudios}}", detalles)

    replace_placeholder(document_id, "{{titulo_primer_objetivo_secundario}}", titulo1)
    replace_placeholder(document_id, "{{descripcion_primer_objetivo_secundario}}", desc1)
    replace_placeholder(document_id, "{{titulo_segundo_objetivo_secundario}}", titulo2)
    replace_placeholder(document_id, "{{descripcion_segundo_objetivo_secundario}}", desc2)
    replace_placeholder(document_id, "{{titulo_tercer_objetivo_secundario}}", titulo3)
    replace_placeholder(document_id, "{{descripcion_tercer_objetivo_secundario}}", desc3)

    drive_service.permissions().create(
        fileId=document_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/document/d/{document_id}/edit"

# === Exportar outline a Google Sheets ===
def generar_outline_csv(nombre_del_curso, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline):
    lines = [line.strip() for line in outline.splitlines() if "|" in line and not line.startswith("|---")]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|", engine="python", skipinitialspace=True)
    df = df.dropna(axis=1, how="all")
    df.columns = [col.strip() for col in df.columns]

    sheet = sheets_service.spreadsheets().create(
        body={"properties": {"title": f"Outline - {nombre_del_curso}"}},
        fields="spreadsheetId"
    ).execute()
    spreadsheet_id = sheet["spreadsheetId"]

    values = [df.columns.tolist()] + df.values.tolist()
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    # Formato estético
    requests = [
        {"updateSheetProperties": {
            "properties": {"gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }},
        {"repeatCell": {
            "range": {"startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True}
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"
        }}
    ]
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()

    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
