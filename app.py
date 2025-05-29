import streamlit as st
from utils import (
    generar_syllabus_completo,
    generar_outline_csv,
    generar_datos_generales
)

# Configuración de la página de Streamlit
st.set_page_config(page_title="Generador de Syllabus", layout="centered")
st.title("🧠 Generador de Syllabus y Outline")
st.markdown("Completa los campos del curso para generar automáticamente el syllabus y el outline.")

# === Inputs del curso ===
nombre = st.text_input("Nombre del curso")
nivel = st.selectbox("Nivel del curso", ["básico", "intermedio", "avanzado"])
publico = st.text_area("Público objetivo")
objetivos_raw = st.text_area("Objetivos del curso")
siguiente = st.text_input("Nombre del siguiente curso sugerido", value="N/A")

# Variable fija para definir al estudiante tipo que tomará el curso
student_persona = (
    "Usuario de negocios quiere construir productos de datos pero:\n"
    "- No tiene el hábito o modelo de trabajo mental de tomar decisiones basadas en datos.\n"
    "- No tiene conocimiento suficiente para traducir sus problemas a productos de datos.\n"
    "- No tiene habilidades técnicas para manipular data.\n"
    "- No colabora activamente con equipos de data.\n"
    "- Tiene poco tiempo y necesita soluciones prácticas que le ayuden a avanzar ya."
)

# === Botón de acción principal ===
if st.button("Generar Syllabus y Outline"):
    with st.spinner("Generando contenido con IA..."):
        try:
            # Esta función hace una sola llamada a GPT para generar todo de una vez
            perfil_ingreso, objetivos_mejorados, perfil_egreso, outline = generar_datos_generales(
                nombre, nivel, publico, student_persona, siguiente, objetivos_raw
            )

            # Generar syllabus con los datos obtenidos
            link_syllabus = generar_syllabus_completo(
                nombre, nivel, objetivos_mejorados, publico, siguiente,
                perfil_ingreso, perfil_egreso, outline
            )

            # Generar el outline CSV, reutilizando el mismo outline
            link_outline = generar_outline_csv(nombre, nivel, objetivos_mejorados, perfil_ingreso, siguiente, outline)

            # Mostrar ambos enlaces generados
            st.success("✅ Syllabus y Outline generados correctamente.")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"[📄 Ver Syllabus en Google Docs]({link_syllabus})", unsafe_allow_html=True)
            with col2:
                st.markdown(f"[📊 Ver Outline en Google Sheets]({link_outline})", unsafe_allow_html=True)

        except Exception as e:
            # Mostrar error si algo sale mal
            st.error(f"Ha ocurrido un error durante la generación: {str(e)}")
            st.info("Verifica que todos los campos estén completos y que la plantilla tenga los placeholders correctos.")
            st.info("Placeholders necesarios en la plantilla: {{titulo_primer_objetivo_secundario}}, {{descripcion_primer_objetivo_secundario}}, {{titulo_segundo_objetivo_secundario}}, {{descripcion_segundo_objetivo_secundario}}, {{titulo_tercer_objetivo_secundario}}, {{descripcion_tercer_objetivo_secundario}}")
