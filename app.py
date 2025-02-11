import streamlit as st
import pandas as pd
import requests
import time
import os
from datetime import datetime, timezone
import io
import certifi

# Configuración de la página
st.set_page_config(page_title="Case Processor", page_icon="📄", layout="centered")

# Inyectar CSS para estilos personalizados
st.markdown("""
    <style>
    /* Estilos generales para el contenedor principal */
    .main-container {
         background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
         padding: 2rem;
         border-radius: 15px;
         box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
         margin: 1rem;
    }
    /* Estilos para el login */
    .login-container {
         background: #fff;
         padding: 2rem;
         border-radius: 15px;
         box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
         max-width: 400px;
         margin: 5rem auto;
         text-align: center;
    }
    .login-container h2 {
         margin-bottom: 1.5rem;
         color: #333;
    }
    input[type="password"] {
         border: 1px solid #ccc;
         padding: 0.75rem;
         border-radius: 5px;
         font-size: 1rem;
         width: 100%;
         box-sizing: border-box;
         margin-bottom: 1rem;
    }
    .stButton button {
         background-color: #4CAF50;
         color: white;
         border: none;
         padding: 0.75rem 1.5rem;
         border-radius: 5px;
         cursor: pointer;
         font-size: 1rem;
    }
    .stButton button:hover {
         background-color: #45a049;
    }
    </style>
    """, unsafe_allow_html=True)

# 🔑 Cargar claves desde los secretos (variables de entorno)
ACCESS_KEY = os.getenv("ACCESS_KEY")
STAGING_API_KEY = os.getenv("STAGING_API_KEY")
PRODUCTION_API_KEY = os.getenv("PRODUCTION_API_KEY")

# Verificar que las claves existen
if not all([ACCESS_KEY, STAGING_API_KEY, PRODUCTION_API_KEY]):
    st.error("❌ API keys are missing. Please configure them in GitHub Secrets.")
    st.stop()

# Usamos session_state para guardar el estado del login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Si no se ha autenticado, mostramos la pantalla de login
if not st.session_state.logged_in:
    st.markdown("""
        <div class="login-container">
            <h2>🔐 Acceso Seguro</h2>
            <p>Ingresa la clave de acceso para continuar</p>
        </div>
        """, unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=True):
        user_key = st.text_input("", type="password", placeholder="Ingrese su clave de acceso")
        submitted = st.form_submit_button("Ingresar")
        if submitted:
            if user_key == ACCESS_KEY:
                st.session_state.logged_in = True
                st.success("✅ Acceso concedido")
                st.experimental_rerun()
            else:
                st.error("❌ Clave incorrecta. Intente de nuevo.")
    st.stop()

# Una vez autenticado, ocultamos el menú lateral (sidebar)
hide_sidebar_style = """
    <style>
    [data-testid="stSidebar"] {
        display: none;
    }
    </style>
"""
st.markdown(hide_sidebar_style, unsafe_allow_html=True)

# Ruta del certificado para verificación SSL
CERT_PATH = certifi.where()

# Opciones de estado permitidas
STATUS_OPTIONS = ["approved", "rejected", "closed", "draft", "open"]

# Toggle para seleccionar entorno (se muestra en el área principal ahora)
use_production = st.toggle("Use Production Environment", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# Función para actualizar el estado de los casos
def update_case_status(df, selected_status):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }

    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    results = []
    progress_bar = st.progress(0)
    total_cases = len(df)

    for idx, row in df.iterrows():
        case_id = row.get("case_id")
        if pd.notna(case_id):
            try:
                if selected_status == "closed":
                    # Paso 1: Crear revisión
                    url_review = f"https://api.dotfile.com/v1/cases/{case_id}/reviews"
                    review_payload = {
                        "status": "closed",
                        "comment": "Closing the case as per review process",
                        "reviewed_at": reviewed_at
                    }
                    response_review = requests.post(url_review, json=review_payload, headers=headers, verify=CERT_PATH)

                    if response_review.status_code == 201:
                        # Paso 2: Cerrar el caso
                        time.sleep(2)
                        url_close = f"https://api.dotfile.com/v1/cases/{case_id}"
                        close_payload = {"status": "closed"}
                        response_close = requests.patch(url_close, json=close_payload, headers=headers, verify=CERT_PATH)
                        success = response_close.status_code == 200
                        status = "Success" if success else f"Error {response_close.status_code}"
                    else:
                        success = False
                        status = f"Error {response_review.status_code} (Review Failed)"
                else:
                    # Actualización directa para otros estados
                    url_patch = f"https://api.dotfile.com/v1/cases/{case_id}"
                    payload = {"status": selected_status}
                    response = requests.patch(url_patch, json=payload, headers=headers, verify=CERT_PATH)
                    success = response.status_code == 200
                    status = "Success" if success else f"Error {response.status_code}"

                results.append({"Case ID": case_id, "Status": status})

            except Exception as e:
                results.append({"Case ID": case_id, "Status": "Failed", "Response": str(e)})

        progress_bar.progress((idx + 1) / total_cases)

    progress_bar.empty()
    return pd.DataFrame(results)

# Contenedor principal con estilo personalizado
with st.container():
    st.markdown("<div class='main-container'>", unsafe_allow_html=True)
    st.title("Case Processor")

    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)

        if "case_id" not in df.columns:
            st.error("The uploaded file must contain a 'case_id' column.")
        else:
            st.success("File uploaded successfully.")

            # Dropdown para seleccionar el nuevo estado
            selected_status = st.selectbox("Select the new case status:", STATUS_OPTIONS, index=0)

            if st.button("Process Cases"):
                with st.spinner(f"Updating cases to status: {selected_status} in {'Production' if use_production else 'Staging'}, please wait..."):
                    result_df = update_case_status(df, selected_status)

                st.success(f"Processing completed. Cases updated to {selected_status}.")
                st.dataframe(result_df, use_container_width=True)

                # Convertir resultados a CSV para descarga
                output = io.BytesIO()
                result_df.to_csv(output, index=False)
                output.seek(0)

                st.download_button(
                    label="Download Processed Results",
                    data=output,
                    file_name=f"case_results_{selected_status}.csv",
                    mime="text/csv"
                )
    st.markdown("</div>", unsafe_allow_html=True)
