import streamlit as st
import json
import tempfile
import pandas as pd
import io
import re
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from functools import lru_cache

# === Configuración inicial optimizada ===
# Creamos cliente OpenAI moderno
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Preparamos credenciales para Google APIs
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

# === Función base de GPT con modelo optimizado y token limitado ===
def call_gpt(prompt, max_tokens=1000):
    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()

# === Función optimizada que genera todo en una sola llamada ===
@st.cache_data(show_spinner=False)
def generar_datos_generales(nombre_del_curso, nivel, publico, student_persona, siguiente, objetivos_raw):
    prompt = f"""
Diseña un curso con base en:
Curso: {nombre_del_curso}. Nivel: {nivel}. Público: {publico}. Perfil: {student_persona}. Objetivos: {objetivos_raw}. Curso sugerido posterior: {siguiente} (no lo menciones).

Devuélveme:
[PERFIL_INGRESO]
[OBJETIVOS]
[PERFIL_EGRESO]
[OUTLINE]

El outline debe tener 12 clases (4 por semana por 3 semanas), sin títulos repetidos ni numeraciones, con 3 conceptos clave únicos por clase, descripción clara y 3 objetivos distintos por clase.
"""
    respuesta = call_gpt(prompt, max_tokens=1000)

    def extraer(etiqueta):
        patron = rf"\[{etiqueta}\]\n(.*?)(?=\[|\Z)"
        r = re.search(patron, respuesta, re.DOTALL)
        return r.group(1).strip() if r else ""

    perfil_ingreso = extraer("PERFIL_INGRESO")
    objetivos = extraer("OBJETIVOS")
    perfil_egreso = extraer("PERFIL_EGRESO")
    outline = extraer("OUTLINE")

    return perfil_ingreso, objetivos, perfil_egreso, outline

# === Reemplazo de placeholders en plantilla de syllabus ===
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

# === Ensamblar y generar syllabus completo con plantilla ===
def generar_syllabus_completo(nombre_del_curso, nivel, objetivos_mejorados, publico, siguiente, perfil_ingreso, perfil_egreso, outline):
    anio = 2025

    prompt = f"""
Para el curso "{nombre_del_curso}" ({anio}), genera:

[GENERALIDADES_DEL_PROGRAMA]
Parrafo que combine descripción del curso, objetivo general y perfil de egreso.

[PERFIL_INGRESO]
Parrafo del perfil de ingreso.

[DETALLES_PLAN_ESTUDIOS]
Lista de 12 clases con título y descripción breve.

Datos base:
Ingreso: {perfil_ingreso}
Egreso: {perfil_egreso}
Objetivos: {objetivos_mejorados}
Outline:
{outline}
"""
    secciones = call_gpt(prompt, max_tokens=1200)

    def extraer(etiqueta):
        patron = rf"\[{etiqueta}\]\n(.*?)(?=\[|\Z)"
        r = re.search(patron, secciones, re.DOTALL)
        return r.group(1).strip() if r else ""

    generalidades = extraer("GENERALIDADES_DEL_PROGRAMA")
    ingreso = extraer("PERFIL_INGRESO")
    detalles = extraer("DETALLES_PLAN_ESTUDIOS")

    prompt_obj = f"""
De los objetivos:
{objetivos_mejorados}

Elige los 3 más importantes y devuelve:
[TITULO_PRIMER_OBJETIVO_SECUNDARIO]
[DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO]
[TITULO_SEGUNDO_OBJETIVO_SECUNDARIO]
[DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO]
[TITULO_TERCER_OBJETIVO_SECUNDARIO]
[DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO]
"""
    objetivos_res = call_gpt(prompt_obj, max_tokens=600)

    def extraer_obj(etiqueta):
        patron = rf"\[{etiqueta}\]\n(.*?)(?=\[|\Z)"
        r = re.search(patron, objetivos_res, re.DOTALL)
        return r.group(1).strip() if r else ""

    titulo1 = extraer_obj("TITULO_PRIMER_OBJETIVO_SECUNDARIO")
    desc1 = extraer_obj("DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO")
    titulo2 = extraer_obj("TITULO_SEGUNDO_OBJETIVO_SECUNDARIO")
    desc2 = extraer_obj("DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO")
    titulo3 = extraer_obj("TITULO_TERCER_OBJETIVO_SECUNDARIO")
    desc3 = extraer_obj("DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO")

    template_copy = drive_service.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": f"Syllabus - {nombre_del_curso}"}
    ).execute()
    document_id = template_copy["id"]

    replace_placeholder(document_id, "{{nombre_del_curso}}", nombre_del_curso)
    replace_placeholder(document_id, "{{anio}}", str(anio))
    replace_placeholder(document_id, "{{generalidades_del_programa}}", generalidades)
    replace_placeholder(document_id, "{{perfil_ingreso}}", ingreso)
    replace_placeholder(document_id, "{{titulo_primer_objetivo_secundario}}", titulo1)
    replace_placeholder(document_id, "{{descripcion_primer_objetivo_secundario}}", desc1)
    replace_placeholder(document_id, "{{titulo_segundo_objetivo_secundario}}", titulo2)
    replace_placeholder(document_id, "{{descripcion_segundo_objetivo_secundario}}", desc2)
    replace_placeholder(document_id, "{{titulo_tercer_objetivo_secundario}}", titulo3)
    replace_placeholder(document_id, "{{descripcion_tercer_objetivo_secundario}}", desc3)
    replace_placeholder(document_id, "{{detalles_plan_estudios}}", detalles)

    drive_service.permissions().create(
        fileId=document_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/document/d/{document_id}/edit"

# === Crear y exportar Outline a Google Sheets ===
def generar_outline_csv(nombre_del_curso, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline):
    # Convertimos el outline Markdown a DataFrame (solo líneas con '|')
    lines = [line.strip() for line in outline.splitlines() if "|" in line and not line.startswith("|---")]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|", engine="python", skipinitialspace=True)
    df = df.dropna(axis=1, how="all")
    df.columns = [col.strip() for col in df.columns]

    # Crear hoja de cálculo y poblarla
    sheet = sheets_service.spreadsheets().create(
        body={"properties": {"title": f"Outline - {nombre_del_curso}"}},
        fields="spreadsheetId"
    ).execute()
    spreadsheet_id = sheet["spreadsheetId"]

    # Insertar los datos
    values = [df.columns.tolist()] + df.values.tolist()
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    # Aplicar formato (cabecera congelada y color gris)
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

    # Compartir archivo con dominio autorizado
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
