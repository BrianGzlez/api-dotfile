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

# Inyección de CSS personalizado
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
    /* Estilos para la barra lateral */
    [data-testid="stSidebar"] .css-1d391kg { 
         background: linear-gradient(135deg, #e0eafc, #cfdef3);
         padding: 1rem;
         border-radius: 10px;
    }
    /* Estilos para el recuadro del login */
    .login-box {
         padding: 1rem;
         border: 1px solid #ddd;
         border-radius: 10px;
         background-color: #fff;
         box-shadow: 0 2px 4px rgba(0,0,0,0.1);
         margin-bottom: 1rem;
    }
    /* Estilo para el input de contraseña */
    input[type="password"] {
         border: 1px solid #ccc;
         padding: 0.5rem;
         border-radius: 5px;
         font-size: 1rem;
         width: 100%;
         box-sizing: border-box;
    }
    </style>
    """, unsafe_allow_html=True)

# 🔑 Cargar claves desde los secretos de GitHub (variables de entorno)
ACCESS_KEY = os.getenv("ACCESS_KEY")
STAGING_API_KEY = os.getenv("STAGING_API_KEY")
PRODUCTION_API_KEY = os.getenv("PRODUCTION_API_KEY")

# Verificar que las claves existen
if not all([ACCESS_KEY, STAGING_API_KEY, PRODUCTION_API_KEY]):
    st.error("❌ API keys are missing. Please configure them in GitHub Secrets.")
    st.stop()

# Interfaz de login en la barra lateral
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #333;'>🔐 Secure Access</h2>", unsafe_allow_html=True)
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    user_key = st.text_input("Enter Access Key:", type="password", placeholder="Your secure key")
    st.markdown("</div>", unsafe_allow_html=True)

if user_key != ACCESS_KEY:
    st.sidebar.warning("❌ Incorrect Key")
    st.stop()
else:
    st.sidebar.success("✅ Access Granted")

# Ruta del certificado para verificación SSL
CERT_PATH = certifi.where()

# Opciones de estado permitidas
STATUS_OPTIONS = ["approved", "rejected", "closed", "draft", "open"]

# Toggle para seleccionar entorno
use_production = st.toggle("Use Production Environment", value=False)

# Seleccionar API Key basada en el entorno
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

            # Dropdown para seleccionar estado
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

                # Botón de descarga
                st.download_button(
                    label="Download Processed Results",
                    data=output,
                    file_name=f"case_results_{selected_status}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    st.markdown("</div>", unsafe_allow_html=True)
