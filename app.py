import streamlit as st
from utils import generar_syllabus_completo, generar_outline_csv

st.set_page_config(page_title="Generador de Cursos", layout="centered")

st.title("🧠 Generador de Syllabus y Outline")

st.markdown("Completa los campos del curso y elige qué deseas generar.")

# === Inputs del curso ===
nombre = st.text_input("Nombre del curso")
nivel = st.selectbox("Nivel del curso", ["básico", "intermedio", "avanzado"])
publico = st.text_area("Público objetivo")
objetivos = st.text_area("Objetivos del curso")
siguiente = st.text_input("Nombre del siguiente curso sugerido", value="N/A")

# === Selección de tipo de output ===
opcion = st.radio("¿Qué deseas generar?", ["Syllabus", "Outline"])

# === Botón de acción ===
if st.button("Generar"):
    with st.spinner("Generando contenido con IA..."):
        if opcion == "Syllabus":
            link = generar_syllabus_completo(nombre, nivel, objetivos, publico, siguiente)
            st.success("✅ Syllabus generado.")
            st.markdown(f"[📄 Ver Google Docs]({link})", unsafe_allow_html=True)
        else:
            link = generar_outline_csv(nombre, nivel, objetivos, publico, siguiente)
            st.success("✅ Outline generado.")
            st.markdown(f"[📊 Ver Google Sheets]({link})", unsafe_allow_html=True)
