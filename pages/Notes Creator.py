import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import io
import ssl

# 🔐 API Keys
STAGING_API_KEY = st.secrets["STAGING_API_KEY"]
PRODUCTION_API_KEY = st.secrets["PRODUCTION_API_KEY"]

# 📄 SSL certificate
CERT_PATH = "pages/certi.pem"
SSL_CONTEXT = ssl.create_default_context(cafile=CERT_PATH)

# ⚙️ Page config
st.set_page_config(page_title="Dotfile Notes Creator", page_icon="📝", layout="centered")

# 🎨 Custom styles
st.markdown("""
    <style>
        .title { text-align: center; font-size: 36px; font-weight: bold; color: #ffffff; }
        .subtitle { text-align: center; font-size: 18px; color: #cccccc; margin-bottom: 20px; }
        .stButton>button, .stDownloadButton>button {
            width: 100%; border-radius: 10px; font-size: 16px;
            background-color: #2196F3; color: white; border: none;
        }
        .stDownloadButton>button { background-color: #4CAF50; }
        .stTextInput>div>div>input, .stTextArea>div>textarea {
            background-color: #333333 !important; color: white !important;
            border: 1px solid #555 !important;
        }
    </style>
""", unsafe_allow_html=True)

# 📝 Title
st.markdown('<p class="title">📝 Dotfile Notes Creator</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Bulk-create Notes on Cases using Dotfile\'s API.</p>', unsafe_allow_html=True)

# 🌐 Environment toggle
use_production = st.toggle("🌍 Use Production Mode", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# ✍️ Custom Note
custom_note = st.text_area("✍️ Enter the note content to post on each case:", height=100)

# 🔄 Async function
async def create_note(session, case_id, note_text):
    url = "https://api.dotfile.com/v1/notes"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }
    payload = {
        "case_id": case_id,
        "content": note_text
    }
    try:
        async with session.post(url, json=payload, headers=headers, ssl=SSL_CONTEXT) as response:
            text = await response.text()
            return {
                "case_id": case_id,
                "status_code": response.status,
                "success": response.status in [200, 201],
                "response": text
            }
    except Exception as e:
        return {
            "case_id": case_id,
            "status_code": "error",
            "success": False,
            "response": str(e)
        }

# 📌 Process CSV
async def process_notes(df, note_text):
    async with aiohttp.ClientSession() as session:
        tasks = [
            create_note(session, str(row["case_id"]).strip(), note_text)
            for _, row in df.iterrows() if pd.notna(row["case_id"])
        ]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# 📤 Upload CSV
uploaded_file = st.file_uploader("📂 Upload CSV File", type=["csv"], help="The CSV file must contain a column named 'case_id'.")

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(uploaded_file, encoding="latin-1")

    if "case_id" not in df.columns:
        st.error("❌ The file must contain a column named 'case_id'.")
    elif not custom_note.strip():
        st.warning("⚠️ Please enter a note to post.")
    else:
        st.success(f"✅ File uploaded. {len(df)} case IDs found.")

        if st.button("🚀 Create Notes"):
            with st.spinner(f"Posting notes for {len(df)} cases in {'Production' if use_production else 'Staging'}..."):
                results_df = asyncio.run(process_notes(df, custom_note))

            st.success("✅ Notes posted.")
            st.dataframe(results_df)

            output = io.BytesIO()
            results_df.to_csv(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Download Report",
                data=output,
                file_name="notes_results.csv",
                mime="text/csv"
            )
