import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import io
import ssl
import requests
import os

# 🔑 Claves API
STAGING_API_KEY = "dotkey.m8sQPi2Qy5Q2bpmwgg_Gm.cPQDV1HQoFV7fWDE2SJpEp"
PRODUCTION_API_KEY = "dotkey.07B-0lDHMLl-1gWaVcwGS.pt17cpqXQMuqQ9o9vwVvcH"

# 📌 Configuración de la página
st.set_page_config(page_title="Case Assignee Updater", page_icon="📂", layout="centered")

# 📌 Estilos personalizados
st.markdown("""
    <style>
        .title { text-align: center; font-size: 36px; font-weight: bold; color: #FFF; }
        .subtitle { text-align: center; font-size: 18px; color: #FFF; margin-bottom: 20px; }
        .stButton>button { width: 100%; border-radius: 10px; font-size: 16px; }
        .stDownloadButton>button { width: 100%; border-radius: 10px; font-size: 16px; background-color: #4CAF50; color: white; }
    </style>
""", unsafe_allow_html=True)

# 📌 Título Principal
st.markdown('<p class="title">📂 Case Assignee Updater</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Automatically assign cases to a selected user</p>', unsafe_allow_html=True)

# 📌 Toggle para seleccionar entorno
use_production = st.toggle("🌍 Use Production Environment", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# ✅ Solución alternativa: No usar verify personalizado y dejar que requests use su bundle por defecto
def fetch_users():
    url = "https://api.dotfile.com/v1/users?page=1&limit=100"
    headers = {"accept": "application/json", "X-DOTFILE-API-KEY": API_KEY}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()["data"]
        return {user["email"]: user["id"] for user in data}
    except requests.exceptions.SSLError:
        st.error("❌ SSL certificate error. Please ensure that your system certificates are up to date.")
        return {}
    except Exception as e:
        st.error(f"❌ Failed to fetch users: {str(e)}")
        return {}

users_dict = fetch_users()

# 📌 Crear un contexto SSL genérico para aiohttp
SSL_CONTEXT = ssl.create_default_context()

# 📌 Función para actualizar el assignee_id de un `case_id`
async def update_assignee_async(session, case_id, assignee_id):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }
    url_patch = f"https://api.dotfile.com/v1/cases/{case_id}"
    payload = {"assignee_id": assignee_id}

    try:
        async with session.patch(url_patch, json=payload, headers=headers, ssl=SSL_CONTEXT) as response:
            return {"Case ID": case_id, "Status": "✅ Success" if response.status == 200 else f"❌ Error {response.status}"}
    except Exception as e:
        return {"Case ID": case_id, "Status": "❌ Failed", "Response": str(e)}

# 📌 Función para procesar todos los cases en paralelo
async def process_assignees(df, assignee_id):
    async with aiohttp.ClientSession() as session:
        tasks = [update_assignee_async(session, row["case_id"], assignee_id) for _, row in df.iterrows() if pd.notna(row["case_id"])]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# 📌 Interfaz en Streamlit
uploaded_file = st.file_uploader("📂 Upload Case Data", type=["csv"], help="Upload a CSV file containing a 'case_id' column.")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "case_id" not in df.columns:
        st.error("⚠️ The uploaded file must contain a 'case_id' column.")
    else:
        st.success(f"✅ File uploaded successfully. {len(df)} cases detected.")

        # 📌 Dropdown para seleccionar el email del assignee
        if users_dict:
            selected_email = st.selectbox("📧 Select the assignee by email:", list(users_dict.keys()))
            assignee_id = users_dict[selected_email]

            if st.button("🚀 Update Assignees"):
                with st.spinner(f"Updating assignees to '{selected_email}' in {'Production' if use_production else 'Staging'}..."):
                    result_df = asyncio.run(process_assignees(df, assignee_id))

                st.success(f"✅ Processing completed. Assignees updated to **{selected_email}**.")
                st.dataframe(result_df, use_container_width=True)

                # 📌 Convertir resultados a CSV para descarga
                output = io.BytesIO()
                result_df.to_csv(output, index=False)
                output.seek(0)

                # 📌 Botón de descarga
                st.download_button(
                    label="📥 Download Processed Results",
                    data=output,
                    file_name=f"assignee_update_results_{selected_email}.csv",
                    mime="text/csv"
                )
        else:
            st.error("❌ Unable to fetch users. Please check the API key or internet connection.")
