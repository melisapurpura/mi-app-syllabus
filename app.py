import streamlit as st
from utils import (
    generar_datos_generales,
    generar_syllabus_completo,
    generar_outline_csv
)
from generador_clases import (
    leer_outline_desde_sheets,
    generar_documento_clases_completo
)

# Configuración de la página de Streamlit
st.set_page_config(page_title="Generador de Syllabus", layout="centered")
st.title("🧠 Generador de Syllabus y Outline")
st.markdown("Completa los campos del curso para generar automáticamente el syllabus y el outline.")

# === Inputs del curso ===
nombre = st.text_input("Nombre del curso")
nivel = st.selectbox("Nivel del curso", ["básico", "intermedio", "avanzado"])
publico = st.text_area("Público objetivo (Agregar Industria)")
objetivos_raw = st.text_area("Objetivos del curso")
siguiente = st.text_input("Nombre del siguiente curso sugerido", value="N/A")

# Perfil fijo del estudiante tipo
student_persona = (
    "Usuario de negocios quiere construir productos de datos pero:\n"
    "- No tiene el hábito o modelo de trabajo mental de tomar decisiones basadas en datos.\n"
    "- No tiene conocimiento suficiente para traducir sus problemas a productos de datos.\n"
    "- No tiene habilidades técnicas para manipular data.\n"
    "- No colabora activamente con equipos de data.\n"
    "- Tiene poco tiempo y necesita soluciones prácticas que le ayuden a avanzar ya."
)

# === Acción principal: Generar syllabus y outline ===
if st.button("Generar Syllabus y Outline"):
    with st.spinner("Generando contenido con IA..."):
        try:
            # Obtener todos los datos en una sola llamada
            perfil_ingreso, objetivos_mejorados, perfil_egreso, outline, \
            titulo1, desc1, titulo2, desc2, titulo3, desc3 = generar_datos_generales(
                nombre, nivel, publico, student_persona, siguiente, objetivos_raw
            )

            # Generar el syllabus
            link_syllabus = generar_syllabus_completo(
                nombre, nivel, objetivos_mejorados, publico, siguiente,
                perfil_ingreso, perfil_egreso, outline,
                titulo1, desc1, titulo2, desc2, titulo3, desc3
            )

            # Generar el outline en Google Sheets
            link_outline = generar_outline_csv(nombre, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline)

            # Guardar en session_state
            st.session_state["link_syllabus"] = link_syllabus
            st.session_state["link_outline"] = link_outline

            # Mostrar enlaces
            st.success("✅ Syllabus y Outline generados correctamente.")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"[📄 Ver Syllabus en Google Docs]({link_syllabus})", unsafe_allow_html=True)
            with col2:
                st.markdown(f"[📊 Ver Outline en Google Sheets]({link_outline})", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Ha ocurrido un error durante la generación: {str(e)}")
            st.info("Verifica que todos los campos estén completos y que la plantilla tenga los placeholders correctos.")
            st.info("Placeholders necesarios en la plantilla: {{titulo_primer_objetivo_secundario}}, {{descripcion_primer_objetivo_secundario}}, etc.")

# === Botón para generar clases completas (2 documentos) ===
st.markdown("---")
st.subheader("📚 Generar clases (20 slides por clase, en 2 documentos separados)")

link_outline_guardado = st.session_state.get("link_outline", None)

if st.button("Generar clases desde Outline creado"):
    if link_outline_guardado:
        with st.spinner("Generando documentos..."):
            try:
                from generador_clases import leer_outline_desde_sheets, generar_documento_clases_completo

                clases_info = leer_outline_desde_sheets(link_outline_guardado)
                links_docs = generar_documento_clases_completo(
                    nombre_doc=f"Clases - {nombre}",
                    clases_info=clases_info,
                    perfil_estudiante=student_persona,
                    industria="analítica de datos"
                )

                st.success("✅ Documentos generados exitosamente.")
                st.markdown(f"[📘 Parte 1: Clases 1–6]({links_docs[0]})", unsafe_allow_html=True)
                st.markdown(f"[📘 Parte 2: Clases 7–12]({links_docs[1]})", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Ocurrió un error: {str(e)}")
    else:
        st.warning("⚠️ Primero debes generar el syllabus y outline para poder crear las clases.")
