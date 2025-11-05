import streamlit as st
import json
import pandas as pd
import io
import re
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# =========================
# 🔐 CONFIGURACIÓN GOOGLE OAUTH
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]

# === Helper: flujo de autorización ===
def _build_flow():
    client_config = {
        "web": {
            "client_id": st.secrets["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": st.secrets["GOOGLE_OAUTH_CLIENT_SECRET"],
            "redirect_uris": [st.secrets["GOOGLE_OAUTH_REDIRECT_URI"]],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = st.secrets["GOOGLE_OAUTH_REDIRECT_URI"]
    return flow


def get_google_creds():
    # 1️⃣ Ya autenticado
    if "google_creds" in st.session_state:
        creds_dict = st.session_state["google_creds"]
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(requests.Request())
            st.session_state["google_creds"] = json.loads(creds.to_json())
            return creds

    # 2️⃣ Si vengo del callback de Google (url con ?code=...)
    params = st.query_params
    if "code" in params:
        flow = _build_flow()
        full_url = st.secrets["GOOGLE_OAUTH_REDIRECT_URI"]
        if params:
            q = "&".join([f"{k}={v[0] if isinstance(v, list) else v}" for k, v in params.items()])
            full_url = f"{full_url}?{q}"
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials
        st.session_state["google_creds"] = json.loads(creds.to_json())
        st.query_params.clear()
        return creds

    # 3️⃣ Mostrar botón de autorización si no hay sesión
    st.subheader("🔐 Conecta tu cuenta de Google Drive/Docs/Sheets")
    if st.button("Conectar con Google"):
        flow = _build_flow()
        auth_url, state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true"
        )
        st.session_state["oauth_state"] = state
        st.markdown(f"[Haz clic aquí para autorizar tu cuenta de Google]({auth_url})")
        st.stop()

    st.stop()


def build_services():
    creds = get_google_creds()
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)
    return docs_service, drive_service, sheets_service


# === Inicializamos los servicios globales ===
docs_service, drive_service, sheets_service = build_services()

# =========================
# 🤖 GEMINI API
# =========================
def call_gemini(prompt: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": st.secrets["GEMINI_API_KEY"]}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 3000},
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    if response.status_code == 200:
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    else:
        st.error(f"Error en API Gemini: {response.status_code} - {response.text}")
        raise Exception("Fallo la llamada a Gemini con API Key.")


# =========================
# 🧠 PROMPTING Y LÓGICA DE GENERACIÓN
# =========================
@st.cache_data(show_spinner=False)
def generar_datos_generales(nombre_del_curso, nivel, publico, student_persona, siguiente, objetivos_raw):
    prompt = f"""
    Eres un experto en diseño instruccional y un tutor experimentado, aplicando los principios de la ciencia del aprendizaje
    para crear experiencias educativas efectivas y atractivas. Tu objetivo es generar un syllabus y outline
    que fomenten el aprendizaje activo, gestionen la carga cognitiva del estudiante y adapten el contenido
    a sus necesidades, inspirando curiosidad y profundizando la metacognición.

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
    titulo1 = extraer("TITULO_PRIMER_OBJETIVO_SECUNDARIO")
    desc1 = extraer("DESCRIPCION_PRIMER_OBJETIVO_SECUNDARIO")
    titulo2 = extraer("TITULO_SEGUNDO_OBJETIVO_SECUNDARIO")
    desc2 = extraer("DESCRIPCION_SEGUNDO_OBJETIVO_SECUNDARIO")
    titulo3 = extraer("TITULO_TERCER_OBJETIVO_SECUNDARIO")
    desc3 = extraer("DESCRIPCION_TERCER_OBJETIVO_SECUNDARIO")

    return perfil_ingreso, objetivos, perfil_egreso, outline, titulo1, desc1, titulo2, desc2, titulo3, desc3


# === REEMPLAZO DE PLACEHOLDERS EN LA PLANTILLA ===
def replace_placeholder(document_id, placeholder, new_text):
    requests = [{
        "replaceAllText": {
            "containsText": {"text": placeholder, "matchCase": True},
            "replaceText": new_text
        }
    }]
    docs_service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()


# =========================
# 📄 GENERACIÓN DE SYLLABUS Y OUTLINE
# =========================
TEMPLATE_ID = "1I2jMQ1IjmG6_22dC7u6LYQfQzlND4WIvEusd756LFuo"

def generar_syllabus_completo(nombre_del_curso, nivel, objetivos_mejorados, publico, siguiente,
                               perfil_ingreso, perfil_egreso, outline,
                               titulo1, desc1, titulo2, desc2, titulo3, desc3):
    anio = 2025

    def pedir_seccion(etiqueta, instruccion):
        prompt = f"""
        Como experto en diseño instruccional y aplicando los principios de LearnLM, genera el siguiente contenido:
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
    detalles = pedir_seccion("DETALLES_PLAN_ESTUDIOS", "Escribe la lista de 12 clases, cada una con título y una breve descripción, NO usar negritas en markdown.")

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

    return f"https://docs.google.com/document/d/{document_id}/edit"


def generar_outline_csv(nombre_del_curso, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline):
    lines = [line.strip() for line in outline.splitlines() if "|" in line and not line.startswith("|---")]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|", engine="python", skipinitialspace=True)
    df = df.dropna(axis=1, how="all")
    df.columns = [col.strip() for col in df.columns]

    # 🔧 Limpieza robusta de datos antes de enviar
    df = df.fillna("")
    df = df.astype(str)
    df = df.applymap(lambda x: re.sub(r"[\r\n\t]", " ", x))

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

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

