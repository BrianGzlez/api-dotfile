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
SSL_CONTEXT = ssl.create_default_context()

# ⚙️ Page config
st.set_page_config(page_title="Document Check Creator", page_icon="📝", layout="centered")

# 🎨 Custom styles
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

# 📝 Title
st.markdown('<p class="title">📝 Document Check Creator</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Easily create Document Checks in bulk for multiple individuals using Dotfile\'s API.</p>', unsafe_allow_html=True)

# 🌐 Environment toggle
use_production = st.toggle("🌍 Use Production Mode", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# 📌 Create the check
async def create_check(session, individual_id):
    url = "https://api.dotfile.com/v1/checks/document"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "X-DOTFILE-API-KEY": API_KEY
    }
    payload = {
        "settings": {
            "document_analysis": {
                "automatic_rejection": True,
                "automatic_approval": True,
                "parameters": { "model": "registration_certificate" }
            },
            "fraud_analysis": { "enabled": False }
        },
        "individual_id": individual_id
    }

    try:
        async with session.post(url, json=payload, headers=headers, ssl=SSL_CONTEXT) as response:
            response_text = await response.text()
            return {
                "individual_id": individual_id,
                "status_code": response.status,
                "success": response.status in [200, 201],
                "response": response_text
            }
    except Exception as e:
        return {
            "individual_id": individual_id,
            "status_code": "error",
            "success": False,
            "response": str(e)
        }

# 📌 Bulk process all individuals
async def process_checks(df):
    async with aiohttp.ClientSession() as session:
        tasks = [create_check(session, str(row["individual_id"]).strip()) for _, row in df.iterrows() if pd.notna(row["individual_id"])]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

# 📤 Upload file
uploaded_file = st.file_uploader("📂 Upload Excel File", type=["xlsx"], help="Make sure it contains a column named 'individual_id'.")

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"⚠️ Error reading file: {e}")
        st.stop()

    if "individual_id" not in df.columns:
        st.error("❌ The file must contain a column named 'individual_id'.")
    else:
        st.success(f"✅ File uploaded successfully. {len(df)} individuals found.")

        if st.button("🚀 Create Document Checks"):
            with st.spinner(f"Creating checks for {len(df)} individuals in {'Production' if use_production else 'Staging'}..."):
                results_df = asyncio.run(process_checks(df))

            st.success("✅ All checks processed.")
            st.dataframe(results_df)

            # Download button
            output = io.BytesIO()
            results_df.to_csv(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Download Report",
                data=output,
                file_name="document_check_results.csv",
                mime="text/csv"
            )
