import pandas as pd
import re
from utils import call_gemini, docs_service, drive_service, sheets_service


def leer_outline_desde_sheets(sheet_url: str) -> list:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    spreadsheet_id = match.group(1) if match else None
    if not spreadsheet_id:
        raise ValueError("URL de Google Sheets no válida")

    sheet_data = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range="A1:G100"
    ).execute()
    values = sheet_data.get("values", [])

    headers = values[0]
    rows = values[1:]
    clases = []
    for row in rows:
        if len(row) < 7:
            continue
        clase = {
            "numero": row[0],
            "titulo": row[1],
            "conceptos": row[2],
            "objetivos": [row[3], row[4], row[5]],
            "descripcion": row[6]
        }
        clases.append(clase)
    return clases


def generar_clase_con_prompt(clase_info: dict, perfil_estudiante: str, industria: str) -> str:
    prompt = f"""
Actúa como un diseñador instruccional experto con experiencia en tecnología, negocios y analítica de datos.
Tu tarea es escribir TODO el contenido detallado para cada uno de los 25 slides de una clase, asegurándote de que sea claro, profesional, atractivo y útil para estudiantes en contextos empresariales.

📘 Datos base:
Título de la clase: {clase_info['titulo']}
Descripción de la clase: {clase_info['descripcion']}
Conceptos clave: {clase_info['conceptos']}
Objetivos:
- {clase_info['objetivos'][0]}
- {clase_info['objetivos'][1]}
- {clase_info['objetivos'][2]}
Industria de enfoque: {industria}
Perfil del estudiante:
{perfil_estudiante}

🧱 ESTRUCTURA DE SLIDES (25 total)
INTRODUCCIÓN (Slides 1–4):
- Bienvenida y título de la clase
- Objetivos de aprendizaje
- Relevancia del tema (dato o tendencia)
- Dolor empresarial que resuelve el tema

DESARROLLO (Slides 5–20):
- Concepto clave 1 (definición práctica)
- Caso de uso real (empresa 1)
- Tipos o clasificaciones del concepto
- Concepto clave 2 (cómo funciona)
- Herramientas del mercado (comparación)
- Caso de uso en otra industria
- Pasos para aplicarlo
- Errores comunes
- Mitos vs realidad
- Beneficios para el negocio
- Tips de implementación
- KPIs para medir éxito
- Gestión de resistencia al cambio
- Historia de éxito empresarial
- Preguntas de reflexión
- Conexión con el rol del alumno

ACTIVIDAD PRÁCTICA (Slide 21)
- Dinámica: aplicar el tema a un reto propio (con instrucciones claras)

CIERRE Y CONCLUSIÓN (Slides 22–24)
- Resumen de conceptos clave
- Llamado a la acción
- Cita o frase final inspiradora

RECURSOS (Slide 25)
- Lecturas, herramientas, videos o sitios sugeridos
"""
    return call_gemini(prompt)


def generar_documento_clases_completo(nombre_doc: str, clases_info: list, perfil_estudiante: str, industria: str) -> str:
    contenido_total = ""
    for i, clase in enumerate(clases_info, 1):
        contenido_clase = generar_clase_con_prompt(clase, perfil_estudiante, industria)
        contenido_total += f"\n\n# CLASE {i}: {clase['titulo']}\n\n{contenido_clase}\n"

    documento = drive_service.files().create(
        body={"name": nombre_doc, "mimeType": "application/vnd.google-apps.document"},
        fields="id"
    ).execute()
    document_id = documento["id"]

    docs_service.documents().batchUpdate(
        documentId=document_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": contenido_total
                    }
                }
            ]
        }
    ).execute()

    drive_service.permissions().create(
        fileId=document_id,
        body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
        fields="id"
    ).execute()

    return f"https://docs.google.com/document/d/{document_id}/edit"
