import streamlit as st
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
        Actúa como un **diseñador instruccional experto y un tutor experimentado** con profunda experiencia en tecnología,
        negocios y analítica de datos. Tu tarea es generar **TODO el contenido detallado y final de una clase compuesta por 20 slides**,
        **aplicando los principios de la ciencia del aprendizaje (LearnLM)** para maximizar la comprensión, la retención
        y la aplicación práctica por parte del estudiante. Fomenta el **aprendizaje activo**, la **curiosidad** y la **reflexión**.
        Gestiona la **carga cognitiva** presentando la información de forma clara y estructurada.
        Cada slide debe contener lo siguiente:

        1. TÍTULO en mayúsculas
        2. TEXTO COMPLETO explicativo (mínimo 5–7 líneas), listo para presentación, sin frases genéricas ni instrucciones. El texto debe estar completo y no depender de intervención humana.
        3. Un EJEMPLO o caso de uso empresarial ROBUSTO: menciona empresas reales o escenarios de alto valor que generen un *aha moment* al estudiante. Incluye métricas, resultados o decisiones estratégicas.
        - El caso de uso debe incluir un link funcional y verificable como fuente. Si no hay fuente real, no lo uses.
        4. Un TIP o recomendación práctica basada en experiencia real.
        5. Un RECURSO VISUAL sugerido (describe qué se debe mostrar: gráfico, dashboard, proceso, etc.)

        ESTRUCTURA DE LOS 20 SLIDES:

        1. Bienvenida y título de la clase  
        2. Objetivos de aprendizaje  
        3. Relevancia del tema en el mundo actual (con fuente real si das datos)  
        4. Dolor empresarial que resuelve el tema  
        5. Concepto clave 1: definición clara y utilidad  
        6. Concepto clave 1: clasificaciones, componentes o tipos  
        7. Concepto clave 1: caso de uso real con métricas o impacto + link  
        8. Concepto clave 2: qué es, cómo funciona, rol en la empresa  
        9. Concepto clave 2: herramientas del mercado con comparación concreta  
        10. Concepto clave 2: otro ejemplo con link  
        11. Proceso paso a paso para implementar lo aprendido  
        12. Errores comunes cometidos por empresas y cómo evitarlos  
        13. Mitos vs realidades que confunden a los líderes  
        14. Beneficios tangibles para (costo, ROI, crecimiento)  
        15. Tips de implementación efectivos en la práctica o tips en general  
        16. KPIs o métricas clave para evaluar éxito  
        17. Cómo gestionar resistencia al cambio al aplicar este tema  
        18. Preguntas reflexivas para el alumno y su contexto  
        19. Actividad práctica   
        20. Cierre con resumen y llamada a la acción 

        Contexto:

        - Título de la clase: {clase_info['titulo']}
        - Descripción: {clase_info['descripcion']}
        - Objetivos: {clase_info['objetivos']}
        - Conceptos clave: {clase_info['conceptos']}
        - Perfil del estudiante: {perfil_estudiante}
        - Industria de enfoque: {industria}

        No uses frases como “puedes incluir” o “se recomienda mostrar”. Escribe el contenido real final como si fuera a presentarse en un aula o sesión empresarial. Evita repeticiones y asegura profundidad en cada slide.
        """
    st.session_state["modo_actual"] = "clases"
    return call_gemini(prompt)


def generar_documento_clases_completo(nombre_doc: str, clases_info: list, perfil_estudiante: str, industria: str) -> list:
    docs_links = []
    partes = [clases_info[:6], clases_info[6:]]

    for parte_idx, parte in enumerate(partes, 1):
        # Crear documento vacío
        documento = drive_service.files().create(
            body={"name": f"{nombre_doc} - Parte {parte_idx}", "mimeType": "application/vnd.google-apps.document"},
            fields="id"
        ).execute()
        document_id = documento["id"]

        # Insertar clase por clase en orden
        cursor_index = 1  # se va actualizando manualmente
        for i, clase in enumerate(parte, 1):
            try:
                contenido_clase = generar_clase_con_prompt(clase, perfil_estudiante, industria)
            except Exception as e:
                contenido_clase = f"[ERROR al generar esta clase]: {e}"

            texto = f"\n\nCLASE {i + (parte_idx - 1) * 6}: {clase['titulo']}\n\n{contenido_clase.strip()}\n"

            docs_service.documents().batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": cursor_index},
                                "text": texto
                            }
                        }
                    ]
                }
            ).execute()

            # Actualiza la posición para el siguiente insert
            cursor_index += len(texto)

        # Dar permisos de edición en dominio
        drive_service.permissions().create(
            fileId=document_id,
            body={"type": "domain", "role": "writer", "domain": "datarebels.mx"},
            fields="id"
        ).execute()

        docs_links.append(f"https://docs.google.com/document/d/{document_id}/edit")

    return docs_links
