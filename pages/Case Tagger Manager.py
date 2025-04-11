import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import io
import ssl

# 🔑 Claves API
STAGING_API_KEY = st.secrets["STAGING_API_KEY"]
PRODUCTION_API_KEY = st.secrets["PRODUCTION_API_KEY"]

# 📌 Ruta del certificado SSL (modifícala según donde guardaste `certi.pem`)
CERT_PATH = "pages/certi.pem"

# 📌 Crear un contexto SSL con `certi.pem`
SSL_CONTEXT = ssl.create_default_context()

# 📌 Configuración de la página
st.set_page_config(page_title="Case Tagger System", page_icon="📂", layout="centered")

# 📌 Estilos personalizados para modo oscuro
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
        .stButton>button { 
            width: 100%; 
            border-radius: 10px; 
            font-size: 16px; 
            background-color: #2196F3;
            color: white;
            border: none;
        }
        .stDownloadButton>button { 
            width: 100%; 
            border-radius: 10px; 
            font-size: 16px; 
            background-color: #4CAF50; 
            color: white; 
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
st.markdown('<p class="subtitle">Efficiently manage case records and apply relevant tags with ease.</p>', unsafe_allow_html=True)

# 📌 Toggle para seleccionar entorno
use_production = st.toggle("🌍 Switch to Production Mode", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY


# 📌 Obtener etiquetas disponibles desde la API
async def get_existing_tags():
    url = "https://api.dotfile.com/v1/tags?sort=created_at&page=1&limit=100"  # 👈 Aquí aumenté el limit a 100
    headers = {"accept": "application/json", "X-DOTFILE-API-KEY": API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=SSL_CONTEXT) as response:
            if response.status == 200:
                data = await response.json()
                return {tag["label"] for tag in data["data"]}  # Retorna los tags válidos
            else:
                return set()  # Si hay error, devuelve un conjunto vacío


# 📌 Obtener las etiquetas antes de mostrar la UI
existing_tags = asyncio.run(get_existing_tags())

# 📌 Selector de etiquetas múltiples basado en los datos obtenidos
selected_tags = st.multiselect("🏷️ Select Applicable Tags:", list(existing_tags))

# 📌 Función para agregar tags a un `case_id` (procesamiento en paralelo)
async def add_tags_async(session, case_id, tags):
    url = f"https://api.dotfile.com/v1/cases/{case_id}/tags"
    headers = {"accept": "application/json", "content-type": "application/json", "X-DOTFILE-API-KEY": API_KEY}
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

# 📌 Función para procesar casos en paralelo con `asyncio.gather`
async def process_cases(df, tags):
    async with aiohttp.ClientSession() as session:
        tasks = [add_tags_async(session, str(row["case_id"]).strip(), tags) for _, row in df.iterrows() if pd.notna(row["case_id"])]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# 📌 Cargar archivo CSV
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

        if st.button("🚀 Apply Tags to Cases"):
            with st.spinner(f"Processing {len(df)} cases with selected tags in {'Production' if use_production else 'Staging'}..."):
                result_df = asyncio.run(process_cases(df, selected_tags))

            st.success("✅ Tagging process completed.")
            st.dataframe(result_df)

            # Convertir resultados a CSV para descarga
            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Download Processed Report",
                data=output,
                file_name="case_tagging_results.csv",
                mime="text/csv"
            )
