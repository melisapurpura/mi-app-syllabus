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

# ✅ NUEVO BLOQUE: Mostrar links si ya se generaron previamente
if "link_syllabus" in st.session_state and "link_outline" in st.session_state:
    st.success("✅ Syllabus y Outline previamente generados.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"[📄 Ver Syllabus en Google Docs]({st.session_state['link_syllabus']})", unsafe_allow_html=True)
    with col2:
        st.markdown(f"[📊 Ver Outline en Google Sheets]({st.session_state['link_outline']})", unsafe_allow_html=True)

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
            perfil_ingreso, objetivos_mejorados, perfil_egreso, outline, \
            titulo1, desc1, titulo2, desc2, titulo3, desc3 = generar_datos_generales(
                nombre, nivel, publico, student_persona, siguiente, objetivos_raw
            )

            link_syllabus = generar_syllabus_completo(
                nombre, nivel, objetivos_mejorados, publico, siguiente,
                perfil_ingreso, perfil_egreso, outline,
                titulo1, desc1, titulo2, desc2, titulo3, desc3
            )

            link_outline = generar_outline_csv(
                nombre, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline
            )

            # ✅ Guardar los links para mantenerlos visibles
            st.session_state["link_syllabus"] = link_syllabus
            st.session_state["link_outline"] = link_outline

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

# === Generar clases completas ===
st.markdown("---")
st.subheader("📚 Generar contenido completo de clases")

link_outline_guardado = st.session_state.get("link_outline", None)

if st.button("Generar clases desde Outline creado"):
    if link_outline_guardado:
        with st.spinner("Generando documento con las 12 clases completas..."):
            try:
                clases_info = leer_outline_desde_sheets(link_outline_guardado)
                links_docs = generar_documento_clases_completo(
                    nombre_doc=f"Clases - {nombre}",
                    clases_info=clases_info,
                    perfil_estudiante=student_persona,
                    industria="analítica de datos"
                )
                st.success("✅ Documento(s) de clases generado(s) exitosamente.")
                for idx, link in enumerate(links_docs, 1):
                    st.markdown(f"[📝 Ver documento Parte {idx}]({link})", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Ocurrió un error: {str(e)}")
    else:
        st.warning("⚠️ Primero debes generar el syllabus y outline con el botón superior.")
        st.info("Para hacerlo, completa los campos del curso y haz clic en 'Generar Syllabus y Outline'. Luego podrás crear las clases.")
