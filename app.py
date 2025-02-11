import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timezone
import io
import certifi



# API Keys for Different Environments
STAGING_API_KEY = "dotkey.m8sQPi2Qy5Q2bpmwgg_Gm.cPQDV1HQoFV7fWDE2SJpEp"
PRODUCTION_API_KEY = "dotkey.07B-0lDHMLl-1gWaVcwGS.pt17cpqXQMuqQ9o9vwVvcH"

CERT_PATH = certifi.where()

# Allowed status values (based on API validation)
STATUS_OPTIONS = ["approved", "rejected", "closed", "draft", "open"]

# Streamlit UI - Minimalist & Professional
st.set_page_config(page_title="Case Processor", page_icon="📄", layout="centered")

st.markdown(
    """
    <style>
        body { font-family: 'Arial', sans-serif; }
        .title { text-align: center; font-size: 28px; font-weight: bold; color: #333; }
        .subtitle { text-align: center; font-size: 18px; color: #666; margin-bottom: 30px; }
        .stButton button { width: 100%; background-color: #2C3E50; color: white; border-radius: 5px; }
        .stDownloadButton button { width: 100%; background-color: #1A5276; color: white; border-radius: 5px; }
    </style>
    <div class="title">Automated Case Processor</div>
    <div class="subtitle">Upload a CSV file with <code>case_id</code> and choose the desired status.</div>
    """,
    unsafe_allow_html=True
)

# Toggle to switch between Staging & Production
use_production = st.toggle("Use Production Environment", value=False)

# Select API Key based on Environment
API_KEY = PRODUCTION_API_KEY if use_production else STAGING_API_KEY

# Function to update case status
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
                    # Step 1: Create Review
                    url_review = f"https://api.dotfile.com/v1/cases/{case_id}/reviews"
                    review_payload = {
                        "status": "closed",
                        "comment": "Closing the case as per review process",
                        "reviewed_at": reviewed_at
                    }
                    response_review = requests.post(url_review, json=review_payload, headers=headers, verify=CERT_PATH)

                    if response_review.status_code == 201:
                        # Step 2: Close the Case
                        time.sleep(2)  # Prevents race conditions
                        url_close = f"https://api.dotfile.com/v1/cases/{case_id}"
                        close_payload = {"status": "closed"}
                        response_close = requests.patch(url_close, json=close_payload, headers=headers, verify=CERT_PATH)
                        success = response_close.status_code == 200
                        status = "Success" if success else f"Error {response_close.status_code}"
                    else:
                        success = False
                        status = f"Error {response_review.status_code} (Review Failed)"

                else:
                    # Direct PATCH for other statuses
                    url_patch = f"https://api.dotfile.com/v1/cases/{case_id}"
                    payload = {"status": selected_status}
                    response = requests.patch(url_patch, json=payload, headers=headers, verify=CERT_PATH)
                    success = response.status_code == 200
                    status = "Success" if success else f"Error {response.status_code}"

                results.append({"Case ID": case_id, "Status": status})

                # Display notification with auto-disappear after 3s
                if success:
                    st.toast(f"✅ Case {case_id} updated successfully to {selected_status}", icon="🎉")
                else:
                    st.toast(f"❌ Case {case_id} failed: {status}", icon="⚠️")

                time.sleep(3)  # Delay to allow the notification to disappear

            except Exception as e:
                results.append({"Case ID": case_id, "Status": "Failed", "Response": str(e)})
                st.toast(f"❌ Case {case_id} encountered an error: {e}", icon="⚠️")
                time.sleep(3)

        progress_bar.progress((idx + 1) / total_cases)

    progress_bar.empty()
    return pd.DataFrame(results)

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    if "case_id" not in df.columns:
        st.error("The uploaded file must contain a 'case_id' column.")
    else:
        st.success("File uploaded successfully.")

        # Dropdown to select status
        selected_status = st.selectbox("Select the new case status:", STATUS_OPTIONS, index=0)

        if st.button("Process Cases"):
            with st.spinner(f"Updating cases to status: {selected_status} in {'Production' if use_production else 'Staging'}, please wait..."):
                result_df = update_case_status(df, selected_status)

            st.success(f"Processing completed. Cases updated to {selected_status}.")
            st.dataframe(result_df, use_container_width=True)

            # Convert results to CSV for download
            output = io.BytesIO()
            result_df.to_csv(output, index=False)
            output.seek(0)

            # Show download button
            st.download_button(
                label="Download Processed Results",
                data=output,
                file_name=f"case_results_{selected_status}.csv",
                mime="text/csv",
                use_container_width=True
            )
