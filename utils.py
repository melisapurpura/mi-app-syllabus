import streamlit as st
import json
import tempfile
import pandas as pd
import io
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === Cargar secretos
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
    json.dump(json.loads(st.secrets["SERVICE_ACCOUNT_JSON"]), f)
    SERVICE_ACCOUNT_FILE = f.name

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

docs_service = build("docs", "v1", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)
sheets_service = build("sheets", "v4", credentials=creds)

# ID de tu plantilla de syllabus
TEMPLATE_ID = "1I2jMQ1IjmG6_22dC7u6LYQfQzlND4WIvEusd756LFuo"

def call_gpt(prompt):
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def generar_syllabus_completo(nombre, nivel, objetivos, publico, siguiente):
    prompt = f"""
Redacta un syllabus completo para el curso "{nombre}", de nivel {nivel}, orientado a este público:
{publico}

Objetivos:
{objetivos}

El curso prepara para: {siguiente}

Incluye:
1. Generalidades del programa (descripción, objetivo general, perfil de egreso)
2. Perfil de ingreso
3. Descripción del plan de estudios (3 objetivos secundarios como subtítulos)
4. Detalles del plan de estudios (lista de clases con títulos y descripciones).
"""
    texto = call_gpt(prompt)

    # Duplicar plantilla
    template_copy = drive_service.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": f"Syllabus - {nombre}"}
    ).execute()
    document_id = template_copy["id"]

    # Insertar texto en el documento
    docs_service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": texto}}]}
    ).execute()

    # Compartir con el dominio
    drive_service.permissions().create(
        fileId=document_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/document/d/{document_id}/edit"

def generar_outline_csv(nombre, nivel, objetivos, publico, siguiente):
    prompt = f"""
Crea un temario tipo tabla Markdown para un curso llamado "{nombre}" (nivel {nivel}), con estos objetivos:
{objetivos}

Público objetivo: {publico}
Curso siguiente: {siguiente}

Incluye columnas: Semana, Clase, Conceptos clave, Descripción, Objetivos
"""
    markdown = call_gpt(prompt)

    # Convertir tabla Markdown a DataFrame
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
    values = [df.columns.tolist()] + df.values.tolist()

    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    # Compartir con dominio
    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
