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

# Inyección de CSS para estilos personalizados
st.markdown(
    """
    <style>
    /* Estilos para la pantalla de login */
    .login-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        background-color: #f0f2f6;
    }
    .login-box {
        background-color: #ffffff;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        width: 100%;
        max-width: 400px;
        text-align: center;
    }
    .login-box h2 {
        margin-bottom: 1.5rem;
        color: #333;
    }
    .login-box input[type="password"] {
        width: 100%;
        padding: 0.75rem;
        margin-bottom: 1rem;
        border: 1px solid #ccc;
        border-radius: 5px;
        font-size: 1rem;
    }
    .login-box button {
        background-color: #4CAF50;
        color: #fff;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 5px;
        font-size: 1rem;
        cursor: pointer;
    }
    .login-box button:hover {
        background-color: #45a049;
    }
    /* Estilos para el contenedor principal */
    .main-container {
        background: #f5f7fa;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 2rem auto;
        max-width: 800px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Cargar claves desde variables de entorno
ACCESS_KEY = os.getenv("ACCESS_KEY")
STAGING_API_KEY = os.getenv("STAGING_API_KEY")
PRODUCTION_API_KEY = os.getenv("PRODUCTION_API_KEY")

if not all([ACCESS_KEY, STAGING_API_KEY, PRODUCTION_API_KEY]):
    st.error("❌ API keys are missing. Please configure them in your environment variables.")
    st.stop()

# Usar session_state para controlar el login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Si el usuario no está autenticado, se muestra la pantalla de login
if not st.session_state.logged_in:
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown("<h2>Acceso Seguro</h2>", unsafe_allow_html=True)
    st.write("Ingrese su clave de acceso para continuar")
    user_key = st.text_input("", type="password", placeholder="Clave de acceso")
    if st.button("Ingresar"):
        if user_key == ACCESS_KEY:
            st.session_state.logged_in = True
            st.success("✅ Acceso concedido")
            st.experimental_rerun()
        else:
            st.error("❌ Clave incorrecta. Intente de nuevo.")
    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

# Ocultar el sidebar para una interfaz más limpia una vez autenticado
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Ruta del certificado para verificación SSL
CERT_PATH = certifi.where()

# Opciones de estado permitidas
STATUS_OPTIONS = ["approved", "rejected", "closed", "draft", "open"]

# Toggle para seleccionar entorno (producción vs staging)
use_production = st.toggle("Use Production Environment", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

def update_case_status(df, selected_status):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY,
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
                        "reviewed_at": reviewed_at,
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

# Interfaz principal de la aplicación
st.markdown('<div class="main-container">', unsafe_allow_html=True)
st.title("Case Processor")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if "case_id" not in df.columns:
        st.error("El archivo debe contener una columna 'case_id'.")
    else:
        st.success("Archivo cargado correctamente.")
        selected_status = st.selectbox("Seleccione el nuevo estado del caso:", STATUS_OPTIONS, index=0)
        if st.button("Procesar casos"):
            with st.spinner(f"Actualizando casos a '{selected_status}' en {'Producción' if use_production else 'Staging'}..."):
                result_df = update_case_status(df, selected_status)
            st.success(f"Procesamiento completado. Casos actualizados a {selected_status}.")
            st.dataframe(result_df, use_container_width=True)
            
            # Preparar CSV para descarga
            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)
            st.download_button(
                label="Descargar resultados",
                data=output,
                file_name=f"case_results_{selected_status}.csv",
                mime="text/csv"
            )
st.markdown("</div>", unsafe_allow_html=True)
