import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import certifi
import io
import ssl
from datetime import datetime, timezone

# 🔑 Cargar claves desde los secretos de Streamlit
ACCESS_KEY = st.secrets["ACCESS_KEY"]
STAGING_API_KEY = st.secrets["STAGING_API_KEY"]
PRODUCTION_API_KEY = st.secrets["PRODUCTION_API_KEY"]

# Configuración de la página
st.set_page_config(page_title="Case Processor", page_icon="📄", layout="centered")

# Estilos personalizados
st.markdown(
    """
    <style>
        .title { text-align: center; font-size: 32px; font-weight: bold; }
        .subtitle { text-align: center; font-size: 20px; color: #666; }
        .sidebar .sidebar-content { background-color: #f8f9fa; }
        .stButton>button { width: 100%; border-radius: 10px; font-size: 16px; }
        .stDownloadButton>button { width: 100%; border-radius: 10px; font-size: 16px; background-color: #4CAF50; color: white; }
    </style>
    """,
    unsafe_allow_html=True
)

# Título principal
st.markdown('<p class="title">📄 Case Processor</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Automate the status update of cases efficiently</p>', unsafe_allow_html=True)

# UI para ingresar clave de acceso
st.sidebar.title("🔐 Secure Access")
user_key = st.sidebar.text_input("Enter Access Key:", type="password")

if user_key != ACCESS_KEY:
    st.sidebar.error("❌ Incorrect Key")
    st.stop()

st.sidebar.success("✅ Access Granted")

# Crear un contexto SSL válido
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Opciones de estado permitidas
STATUS_OPTIONS = ["approved", "rejected", "closed", "draft", "open"]

# Toggle para seleccionar entorno
use_production = st.toggle("🌍 Use Production Environment", value=False)

# Seleccionar API Key basada en el entorno
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# Función para realizar la actualización del estado de los casos de forma asíncrona
async def update_case_status_async(session, case_id, selected_status):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }
    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    try:
        if selected_status == "closed":
            # Paso 1: Crear revisión
            url_review = f"https://api.dotfile.com/v1/cases/{case_id}/reviews"
            review_payload = {
                "status": "closed",
                "comment": "Closing the case as per review process",
                "reviewed_at": reviewed_at
            }
            async with session.post(url_review, json=review_payload, headers=headers, ssl=SSL_CONTEXT) as response_review:
                if response_review.status == 201:
                    # Paso 2: Cerrar el caso
                    url_close = f"https://api.dotfile.com/v1/cases/{case_id}"
                    close_payload = {"status": "closed"}
                    async with session.patch(url_close, json=close_payload, headers=headers, ssl=SSL_CONTEXT) as response_close:
                        return {"Case ID": case_id, "Status": "✅ Success" if response_close.status == 200 else f"❌ Error {response_close.status}"}
                else:
                    return {"Case ID": case_id, "Status": f"❌ Error {response_review.status} (Review Failed)"}
        else:
            # Actualización directa para otros estados
            url_patch = f"https://api.dotfile.com/v1/cases/{case_id}"
            payload = {"status": selected_status}
            async with session.patch(url_patch, json=payload, headers=headers, ssl=SSL_CONTEXT) as response:
                return {"Case ID": case_id, "Status": "✅ Success" if response.status == 200 else f"❌ Error {response.status}"}

    except Exception as e:
        return {"Case ID": case_id, "Status": "❌ Failed", "Response": str(e)}

# Función para ejecutar múltiples solicitudes en paralelo
async def process_cases(df, selected_status):
    async with aiohttp.ClientSession() as session:
        tasks = [update_case_status_async(session, row["case_id"], selected_status) for _, row in df.iterrows() if pd.notna(row["case_id"])]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# Interfaz en Streamlit
uploaded_file = st.file_uploader("📂 Upload CSV File", type=["csv"], help="Upload a CSV file containing 'case_id' column.")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "case_id" not in df.columns:
        st.error("⚠️ The uploaded file must contain a 'case_id' column.")
    else:
        st.success("✅ File uploaded successfully.")

        # Dropdown para seleccionar estado
        selected_status = st.selectbox("📝 Select the new case status:", STATUS_OPTIONS, index=0)

        if st.button("🚀 Process Cases"):
            with st.spinner(f"Processing cases to status: {selected_status} in {'Production' if use_production else 'Staging'}..."):
                result_df = asyncio.run(process_cases(df, selected_status))

            st.success(f"✅ Processing completed. Cases updated to **{selected_status}**.")
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
                mime="text/csv"
            )
