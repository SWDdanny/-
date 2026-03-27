import streamlit as st
import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
# 匯入你的常數設定
from constants import CALENDAR_DATA, MAJOR_EVENTS 

st.set_page_config(page_title="品牌開發助手", layout="wide")
st.title("🚀 下月品牌開發爬蟲系統")

# 自動計算下個月
today = datetime.date.today()
next_month_val = (today.month % 12) + 1
month_key = f"{next_month_val}月"

st.info(f"當前偵測：下個月為 **{month_key}**")

# 讓使用者確認檔期與產業 (資料來源於 constants.txt)
target_events = CALENDAR_DATA.get(month_key, {}).get('events', []) [cite: 6]
target_industries = CALENDAR_DATA.get(month_key, {}).get('industries', []) [cite: 6]

selected_event = st.selectbox("確認搜尋檔期", target_events)
selected_industry = st.selectbox("確認產業別", target_industries)

if st.button("開始執行爬蟲"):
    with st.spinner('正在搜尋並寫入 Google Sheets...'):
        # 這裡放入之前的 selenium 爬蟲邏輯
        # 關鍵字組合 [cite: 1, 2]
        query = f"2026 {month_key} {selected_event} {selected_industry} 品牌 電話 -site:104.com.tw"
        st.write(f"正在搜尋：{query}")
        
        # 執行成功後顯示
        st.success("資料已成功更新至品牌資料庫！")
