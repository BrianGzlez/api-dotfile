import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import io
import ssl
import requests

# 🔑 API Keys
STAGING_API_KEY = "dotkey.m8sQPi2Qy5Q2bpmwgg_Gm.cPQDV1HQoFV7fWDE2SJpEp"
PRODUCTION_API_KEY = "dotkey.07B-0lDHMLl-1gWaVcwGS.pt17cpqXQMuqQ9o9vwVvcH"

# ⚙️ Configuración
st.set_page_config(page_title="Note Creator", page_icon="📝", layout="centered")

st.markdown("""
    <style>
        .title { text-align: center; font-size: 36px; font-weight: bold; color: #FFF; }
        .subtitle { text-align: center; font-size: 18px; color: #FFF; margin-bottom: 20px; }
        .stButton>button, .stDownloadButton>button {
            width: 100%; border-radius: 10px; font-size: 16px;
        }
        .stDownloadButton>button {
            background-color: #4CAF50; color: white;
        }
        .stTextArea>div>textarea {
            background-color: #333 !important;
            color: white !important;
        }
    </style>
""", unsafe_allow_html=True)

# 🧾 Título principal
st.markdown('<p class="title">📝 Dotfile Note Creator</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Create custom notes for multiple cases</p>', unsafe_allow_html=True)

# 🌐 Environment toggle
use_production = st.toggle("🌍 Use Production Environment", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# ✍️ Nota personalizada
note_content = st.text_area("✍️ Note content", height=100)

# ✅ SSL Context confiable
SSL_CONTEXT = ssl.create_default_context()

# 📌 Función para crear una nota
async def create_note(session, case_id, content):
    url = "https://api.dotfile.com/v1/notes"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }
    payload = {
        "case_id": case_id,
        "content": content
    }

    try:
        async with session.post(url, json=payload, headers=headers, ssl=SSL_CONTEXT) as response:
            status = response.status
            resp_text = await response.text()

            if status in [200, 201]:
                return {"case_id": case_id, "status": "✅ Success"}
            else:
                return {"case_id": case_id, "status": f"❌ Error {status}", "response": resp_text}
    except Exception as e:
        return {"case_id": case_id, "status": "❌ Failed", "response": str(e)}

# 🧮 Proceso en paralelo
async def process_notes(df, note):
    async with aiohttp.ClientSession() as session:
        tasks = [
            create_note(session, str(row["case_id"]).strip(), note)
            for _, row in df.iterrows() if pd.notna(row["case_id"])
        ]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# 📤 Subida del archivo CSV
uploaded_file = st.file_uploader("📂 Upload CSV File", type=["csv"], help="CSV must contain a 'case_id' column.")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "case_id" not in df.columns:
        st.error("❌ CSV must contain a column named 'case_id'.")
    elif not note_content.strip():
        st.warning("⚠️ Please enter the note content above.")
    else:
        st.success(f"✅ {len(df)} cases detected in uploaded file.")

        if st.button("🚀 Create Notes"):
            with st.spinner(f"Posting notes in {'Production' if use_production else 'Staging'}..."):
                result_df = asyncio.run(process_notes(df, note_content))

            st.success("✅ Notes created.")
            st.dataframe(result_df, use_container_width=True)

            # 📥 Descargar CSV
            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Download Results CSV",
                data=output,
                file_name="note_results.csv",
                mime="text/csv"
            )
