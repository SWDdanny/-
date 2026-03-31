import streamlit as st
import pandas as pd
import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from constants import CALENDAR_DATA

# --- 設定區 ---
# 確保檔名與資料夾內的一模一樣
SERVICE_ACCOUNT_FILE = 'service_account.json' 
SPREADSHEET_ID = '1CIjHi8dImHdLmNdzSMXh0qf1pE1KZHFBszS4SDdqVOg'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

st.set_page_config(page_title="品牌開發全功能系統", layout="wide")

def get_service():
    """建立連線，增加錯誤檢查"""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"找不到檔案: {SERVICE_ACCOUNT_FILE}")
            return None
        
        # 這裡會驗證 JWT 簽章
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('sheets', 'v4', credentials=creds, cache_discovery=False)
    except Exception as e:
        st.error(f"金鑰認證失敗，請重新下載 JSON 檔。錯誤內容: {e}")
        return None

def read_sheet_data():
    service = get_service()
    if not service: return pd.DataFrame()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range="data!A:F").execute()
        values = result.get('values', [])
        if len(values) > 1:
            return pd.DataFrame(values[1:], columns=values[0])
    except Exception as e:
        st.warning(f"讀取失敗（可能工作表是空的）: {e}")
    return pd.DataFrame(columns=["日期", "月份", "檔期", "產業", "品牌名稱", "聯絡資訊"])

def append_to_sheet(row):
    service = get_service()
    if service:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="data!A1",
            valueInputOption="USER_ENTERED",
            body={'values': [row]}
        ).execute()

# --- UI 介面 ---
st.title("🔍 品牌開發自動化系統")

st.markdown("### 1️⃣ 執行搜尋並存入")
today = datetime.date.today()
next_month = (today.month % 12) + 1
month_key = f"{next_month}月"

target_data = CALENDAR_DATA.get(month_key, {"events": [], "industries": []})

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    sel_event = st.selectbox("選擇當月檔期", target_data["events"])
with col2:
    sel_industry = st.selectbox("選擇目標產業", target_data["industries"])
with col3:
    st.write(" ")
    if st.button("🚀 開始搜尋並同步", use_container_width=True):
        with st.spinner('同步中...'):
            new_brand = f"搜尋品牌_{datetime.datetime.now().strftime('%H%M%S')}"
            new_row = [str(today), month_key, sel_event, sel_industry, new_brand, "02-1234-5678"]
            try:
                append_to_sheet(new_row)
                st.success(f"✅ 成功存入: {new_brand}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"寫入失敗: {e}")

st.divider()

st.markdown("### 2️⃣ 品牌名單即時查找")
@st.cache_data(ttl=10)
def get_cached_df():
    return read_sheet_data()

df = get_cached_df()
if not df.empty:
    search = st.text_input("🔍 快速篩選:")
    if search:
        df = df[df.apply(lambda row: row.astype(str).str.contains(search).any(), axis=1)]
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("目前資料庫尚無資料。")
