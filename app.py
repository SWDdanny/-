import streamlit as st
import pandas as pd
import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from constants import CALENDAR_DATA

# --- 設定區 ---
SERVICE_ACCOUNT_FILE = 'service_account.json' 
SPREADSHEET_ID = '1CIjHi8dImHdLmNdzSMXh0qf1pE1KZHFBszS4SDdqVOg'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

st.set_page_config(page_title="品牌開發全功能系統", layout="wide")

# --- 核心功能：Google Sheets 連線 ---
def get_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        st.error(f"❌ 錯誤：找不到 {SERVICE_ACCOUNT_FILE} 檔案！")
        return None
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def read_sheet_data():
    """讀取 Sheet 內容轉為 DataFrame"""
    service = get_service()
    if not service: return pd.DataFrame()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range="data!A:F").execute()
    values = result.get('values', [])
    if len(values) > 1:
        return pd.DataFrame(values[1:], columns=values[0])
    return pd.DataFrame(columns=["日期", "月份", "檔期", "產業", "品牌名稱", "聯絡資訊"])

def append_to_sheet(row):
    """將資料存入 Sheet"""
    service = get_service()
    if service:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="data!A1",
            valueInputOption="USER_ENTERED",
            body={'values': [row]}
        ).execute()

# --- 網頁介面 ---
st.title("🔍 品牌開發自動化系統")

# 分為左右兩欄：左邊操作，右邊顯示 (或上下分層)
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
    st.write(" ") # 調整高度
    if st.button("🚀 開始搜尋並同步", use_container_width=True):
        with st.spinner('抓取資料並同步中...'):
            # 這裡之後可以串接爬蟲代碼。目前先模擬存入 2 筆
            mock_data = [str(today), month_key, sel_event, sel_industry, f"搜尋到的品牌_{datetime.datetime.now().strftime('%S')}", "02-12345678"]
            try:
                append_to_sheet(mock_data)
                st.success("✅ 已同步至雲端！")
                st.cache_data.clear() # 強制刷新下方列表
            except Exception as e:
                st.error(f"寫入失敗：{e}")

st.divider()

st.markdown("### 2️⃣ 品牌名單即時查找")

# 使用快取讀取資料，每 30 秒自動刷新
@st.cache_data(ttl=30)
def get_cached_df():
    return read_sheet_data()

try:
    df = get_cached_df()
    search = st.text_input("🔍 輸入關鍵字查找（品牌/產業/檔期）:", placeholder="快速篩選...")
    
    if search:
        df = df[df.apply(lambda row: row.astype(str).str.contains(search).any(), axis=1)]
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"📊 目前共有 {len(df)} 筆開發紀錄")
except Exception as e:
    st.info("目前資料庫尚無內容。")
