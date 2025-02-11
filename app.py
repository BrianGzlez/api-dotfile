import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timezone
import io
import certifi

# 🔑 Cargar claves desde los secretos de Streamlit
ACCESS_KEY = st.secrets["ACCESS_KEY"]
STAGING_API_KEY = st.secrets["STAGING_API_KEY"]
PRODUCTION_API_KEY = st.secrets["PRODUCTION_API_KEY"]

# Configuración de la página
st.set_page_config(page_title="Case Processor", page_icon="📄", layout="centered")

# Título de la aplicación
st.title("📄 Case Processor")
st.write("Automate the status update of cases securely and efficiently.")

# UI para ingresar clave de acceso
st.sidebar.title("🔐 Secure Access")
user_key = st.sidebar.text_input("Enter Access Key:", type="password")

if user_key != ACCESS_KEY:
    st.sidebar.warning("❌ Incorrect Key")
    st.stop()

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

# Interfaz en Streamlit
uploaded_file = st.file_uploader("📂 Upload CSV File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "case_id" not in df.columns:
        st.error("⚠️ The uploaded file must contain a 'case_id' column.")
    else:
        st.success("✅ File uploaded successfully.")

        # Dropdown para seleccionar estado
        selected_status = st.selectbox("📝 Select the new case status:", STATUS_OPTIONS, index=0)

        if st.button("🚀 Process Cases"):
            with st.spinner(f"Updating cases to status: {selected_status} in {'Production' if use_production else 'Staging'}, please wait..."):
                result_df = update_case_status(df, selected_status)

            st.success(f"✅ Processing completed. Cases updated to {selected_status}.")
            st.dataframe(result_df, use_container_width=True)

            # Convertir resultados a CSV para descarga
            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)

            # Botón de descarga
            st.download_button(
                label="📥 Download Processed Results",
                data=output,
                file_name=f"case_results_{selected_status}.csv",
                mime="text/csv",
                use_container_width=True
            )
