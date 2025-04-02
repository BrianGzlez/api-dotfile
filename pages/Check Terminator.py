import streamlit as st
import pandas as pd
import aiohttp
import asyncio
import io
import ssl

from datetime import datetime

STAGING_API_KEY = st.secrets["STAGING_API_KEY"]
PRODUCTION_API_KEY = st.secrets["PRODUCTION_API_KEY"]

st.set_page_config(page_title="Check Terminator 9000", page_icon="🗑️", layout="centered")

st.markdown("""
    <style>
        .title { text-align: center; font-size: 36px; font-weight: bold; color: #FFF; }
        .subtitle { text-align: center; font-size: 18px; color: #FFF; margin-bottom: 20px; }
        .stButton>button { width: 100%; border-radius: 10px; font-size: 16px; }
        .stDownloadButton>button { width: 100%; border-radius: 10px; font-size: 16px; background-color: #f44336; color: white; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="title">🗑️ Check Terminator</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Clean up checks from Dotfile with style</p>', unsafe_allow_html=True)

use_production = st.toggle("🌍 Use Production Environment", value=False)
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

SSL_CONTEXT = ssl.create_default_context()

async def delete_check_async(session, check_id):
    url = f"https://api.dotfile.com/v1/checks/{check_id}"
    headers = {
        "X-DOTFILE-API-KEY": API_KEY
    }

    try:
        async with session.delete(url, headers=headers, ssl=SSL_CONTEXT) as response:
            if response.status == 204:
                return {"Check ID": check_id, "Status": "✅ Deleted"}
            else:
                text = await response.text()
                return {"Check ID": check_id, "Status": f"❌ Error {response.status}", "Message": text}
    except Exception as e:
        return {"Check ID": check_id, "Status": "❌ Failed", "Message": str(e)}

async def process_deletions(df):
    async with aiohttp.ClientSession() as session:
        tasks = [
            delete_check_async(session, row["check_id"])
            for _, row in df.iterrows()
            if pd.notna(row["check_id"])
        ]
        results = await asyncio.gather(*tasks)
    return pd.DataFrame(results)

uploaded_file = st.file_uploader("📤 Upload CSV with Check IDs", type=["csv"], help="Must contain a column named 'check_id' with UUIDs of the checks.")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    if "check_id" not in df.columns:
        st.error("⚠️ The uploaded file must contain a column named 'check_id'.")
    else:
        st.success(f"✅ File uploaded. {len(df)} checks to process.")

        if st.button("🔥 Delete Checks Now"):
            with st.spinner("Deleting checks..."):
                result_df = asyncio.run(process_deletions(df))

            st.success("✅ Deletion process completed.")
            st.dataframe(result_df, use_container_width=True)

            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Download Deletion Results",
                data=output,
                file_name="deleted_checks_report.csv",
                mime="text/csv"
            )
