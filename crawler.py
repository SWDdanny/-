import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googlesearch import search

# --- 設定區 ---
SPREADSHEET_ID = '1jb7MZ5w00zNs3T_I7lxT24nEChudAUnUnpXLm77sOXU'
SHEET_NAME = '品牌名單' 
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_service():
    service_account_info = os.environ.get("GCP_SERVICE_ACCOUNT")
    if service_account_info:
        info = json.loads(service_account_info)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def crawl_twincn(brand_name):
    # 增加關鍵字精準度
    query = f"{brand_name} 台灣公司網 twincn"
    print(f"🔍 搜尋關鍵字: {query}")
    
    try:
        # 增加搜尋數量到 5，並增加停頓時間
        urls = search(query, num_results=5, lang="zh-TW", sleep_interval=5)
        
        target_url = None
        for url in urls:
            print(f"🔗 找到網址: {url}")
            if "twincn.com/item.aspx" in url or "twincn.com/L_item.aspx" in url:
                target_url = url
                break
        
        if target_url:
            print(f"🎯 目標鎖定: {target_url}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            resp = requests.get(target_url, headers=headers, timeout=15)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. 抓取正式抬頭 (twincn 的公司名稱通常在 h1 或特定 table 內)
            company_title = ""
            h1_tag = soup.find('h1')
            if h1_tag:
                company_title = h1_tag.text.strip().replace("公司基本資料", "")
            
            # 2. 抓取電話
            phone = ""
            # 台灣公司網的電話通常在一個包含「電話」字眼的 <td> 或是文本中
            page_text = soup.get_text()
            phone_match = re.search(r'0\d{1,2}-\d{6,8}', page_text)
            if phone_match:
                phone = phone_match.group()
            
            return company_title, phone
        else:
            print("⚠️ 搜尋結果中沒看到 twincn 的頁面")
            return None, None
    except Exception as e:
        print(f"❌ 搜尋過程發生錯誤: {e}")
        return None, None

def main():
    service = get_service()
    sheet = service.spreadsheets()
    range_name = f"{SHEET_NAME}!A:K"
    
    print("📂 正在讀取 Google Sheets...")
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
    values = result.get('values', [])

    if not values:
        print("❌ 試算表是空的")
        return

    # 找到欄位索引
    header = values[0]
    try:
        col_brand = header.index("品牌名稱")
        col_status = header.index("狀態")
    except ValueError:
        st.error("找不到 '品牌名稱' 或 '狀態' 欄位，請檢查標題列")
        return

    for i, row in enumerate(values):
        if i == 0: continue
        if len(row) <= col_status: continue
        
        brand_name = row[col_brand]
        status = row[col_status]
        
        # 檢查 J 欄 (索引 9) 是否已有資料
        already_has_data = len(row) > 9 and row[9] != "" and row[9] != "查無資料"
        
        if status == "已分配" and not already_has_data:
            print(f"🚀 開始處理品牌: {brand_name}")
            official_title, phone = crawl_twincn(brand_name)
            
            # 回填
            update_range = f"{SHEET_NAME}!J{i+1}:K{i+1}"
            fill_title = official_title if official_title else "查無資料"
            fill_phone = phone if phone else "查無資料"
            
            body = {'values': [[fill_title, fill_phone]]}
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID, range=update_range,
                valueInputOption="USER_ENTERED", body=body).execute()
            
            print(f"📊 結果: {fill_title} / {fill_phone}")
            time.sleep(10) # 雲端執行建議拉長間隔，防止被 Google 封鎖

if __name__ == "__main__":
    main()
