import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import io
import ssl

# 🔑 Claves API
STAGING_API_KEY = st.secrets["STAGING_API_KEY"]
PRODUCTION_API_KEY = st.secrets["PRODUCTION_API_KEY"]

# 📌 Ruta del certificado SSL
CERT_PATH = "pages/certi.pem"

# 📌 Crear un contexto SSL
SSL_CONTEXT = ssl.create_default_context()

# 📌 Configuración de la página
st.set_page_config(page_title="Case Tagger System", page_icon="📂", layout="centered")

# 📌 Estilos personalizados
st.markdown("""
    <style>
        body {
            background-color: #121212;
            color: #ffffff;
        }
        .title { 
            text-align: center; 
            font-size: 36px; 
            font-weight: bold; 
            color: #ffffff; 
        }
        .subtitle { 
            text-align: center; 
            font-size: 18px; 
            color: #cccccc; 
            margin-bottom: 20px; 
        }
        .stButton>button, .stDownloadButton>button { 
            width: 100%; 
            border-radius: 10px; 
            font-size: 16px; 
            background-color: #2196F3;
            color: white;
            border: none;
        }
        .stDownloadButton>button {
            background-color: #4CAF50;
        }
        .stTextInput>div>div>input, .stSelectbox>div>div>select, .stMultiselect>div>div>div>input {
            background-color: #333333 !important;
            color: white !important;
            border: 1px solid #555 !important;
        }
    </style>
""", unsafe_allow_html=True)

# 📌 Título Principal
st.markdown('<p class="title">📂 Case Tagger System</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Efficiently manage case records and apply or remove tags with ease.</p>', unsafe_allow_html=True)

# 📌 Toggle de entorno
use_production = st.toggle("🌍 Switch to Production Mode", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# 📌 Toggle de modo: agregar o eliminar
remove_mode = st.toggle("🧹 Switch to Remove All Tags Mode", value=False)

# 📌 Obtener etiquetas disponibles
async def get_existing_tags():
    url = "https://api.dotfile.com/v1/tags?sort=created_at&page=1&limit=100"
    headers = {"accept": "application/json", "X-DOTFILE-API-KEY": API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=SSL_CONTEXT) as response:
            if response.status == 200:
                data = await response.json()
                return {tag["label"] for tag in data["data"]}
            else:
                return set()

# 📌 Cargar etiquetas si estamos en modo agregar
if not remove_mode:
    existing_tags = asyncio.run(get_existing_tags())
    selected_tags = st.multiselect("🏷️ Select Applicable Tags:", list(existing_tags))
else:
    selected_tags = []  # No necesitas tags si vas a eliminar

# 📌 Función para agregar tags
async def add_tags_async(session, case_id, tags):
    url = f"https://api.dotfile.com/v1/cases/{case_id}/tags"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }
    payload = {"tags": tags}

    try:
        async with session.post(url, json=payload, headers=headers, ssl=SSL_CONTEXT) as response:
            response_text = await response.text()
            if response.status in [200, 201]:
                return {"Case ID": case_id, "Status": "✅ Successfully Tagged", "Response": response_text}
            else:
                return {"Case ID": case_id, "Status": f"❌ Error {response.status}", "Response": response_text}
    except Exception as e:
        return {"Case ID": case_id, "Status": "❌ Failed", "Response": str(e)}

# 📌 Función para eliminar todos los tags
async def remove_all_tags_async(session, case_id):
    url = f"https://api.dotfile.com/v1/cases/{case_id}/tags"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }

    try:
        async with session.delete(url, headers=headers, ssl=SSL_CONTEXT) as response:
            response_text = await response.text()
            if response.status in [200, 204]:
                return {"Case ID": case_id, "Status": "✅ All Tags Removed", "Response": response_text}
            else:
                return {"Case ID": case_id, "Status": f"❌ Error {response.status}", "Response": response_text}
    except Exception as e:
        return {"Case ID": case_id, "Status": "❌ Failed", "Response": str(e)}

# 📌 Procesar casos
async def process_cases(df, tags, remove=False):
    async with aiohttp.ClientSession() as session:
        if remove:
            tasks = [remove_all_tags_async(session, str(row["case_id"]).strip()) for _, row in df.iterrows() if pd.notna(row["case_id"])]
        else:
            tasks = [add_tags_async(session, str(row["case_id"]).strip(), tags) for _, row in df.iterrows() if pd.notna(row["case_id"])]
        
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# 📌 Cargar archivo
uploaded_file = st.file_uploader("📂 Upload Case Data", type=["csv"], help="Upload a CSV file containing a 'case_id' column.")

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(uploaded_file, encoding="latin-1")

    if "case_id" not in df.columns:
        st.error("⚠️ The uploaded file must contain a 'case_id' column.")
    else:
        st.success(f"✅ File uploaded successfully. {len(df)} case records detected.")

        if st.button("🚀 Start Processing"):
            with st.spinner(f"{'Removing all tags' if remove_mode else 'Adding tags'} for {len(df)} cases in {'Production' if use_production else 'Staging'}..."):
                result_df = asyncio.run(process_cases(df, selected_tags, remove=remove_mode))

            st.success("✅ Processing completed.")
            st.dataframe(result_df)

            # Descarga de resultados
            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Download Report",
                data=output,
                file_name="case_tagging_results.csv",
                mime="text/csv"
            )
