import os
import requests
import json
import time
import re
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
import urllib.parse

# --- 設定區 ---
SPREADSHEET_ID = '1jb7MZ5w00zNs3T_I7lxT24nEChudAUnUnpXLm77sOXU' 
SHEET_NAME = '品牌名單'          

def get_gspread_service():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    secret_data = os.getenv("GCP_SERVICE_ACCOUNT")
    if not secret_data:
        raise ValueError("❌ 找不到環境變數 GCP_SERVICE_ACCOUNT")
    service_account_info = json.loads(secret_data)
    creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return build('sheets', 'v4', credentials=creds)

def serper_request(query):
    url = "https://google.serper.dev/search"
    api_key = os.getenv("SERPER_API_KEY")
    payload = json.dumps({"q": query, "gl": "tw", "hl": "zh-tw", "num": 10})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        return response.json().get("organic", [])
    except Exception as e:
        print(f"❌ Serper API 請求失敗: {e}")
        return []

def clean_company_name(raw_title):
    # 移除標題雜質，保留最純粹的名稱
    name = re.sub(r'^(投標廠商|公司名稱|廠商名稱|公司抬頭|基本資料|公司簡介)[:：\s]+', '', raw_title)
    name = name.split(' - ')[0].split(' | ')[0].split('｜')[0].split(' : ')[0].strip()
    name = re.sub(r'[\(（].*?[\)）]', '', name).strip()
    name = re.sub(r'(台灣標案網|台灣公司網|104人力銀行|1111人力銀行|搜尋公司列表).*$', '', name).strip()
    return name

def check_business_status(page_text):
    """
    檢查頁面文字內容，判斷是否為營業中
    """
    # 判斷是否包含停業相關關鍵字
    inactive_keywords = ["停業以外之非營業中", "廢止", "歇業", "解散"]
    for k in inactive_keywords:
        if k in page_text:
            return False
    # 如果看到「營業中」或沒有看到明顯停業字眼，暫且視為可用
    return True

def get_info_from_twincn_url(url):
    """
    進入內頁提取：1. 營業狀態 2. 電話
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
    # 精細的電話正則：支持 (02) 1234-5678, 02 1234 5678, 02-12345678 #123 等所有格式
    phone_pattern = r'\(?0\d{1,2}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}(?:\s?#\d+)?'
    
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            page_text = soup.get_text(separator=' ')
            
            # 1. 檢查營業狀態
            if not check_business_status(page_text):
                return "已停業", None
            
            # 2. 抓取電話
            phone_match = re.search(phone_pattern, page_text)
            phone = phone_match.group().strip() if phone_match else "查無資料"
            return "營業中", phone
    except Exception as e:
        print(f"❌ 讀取內頁失敗 {url}: {e}")
    
    return "連線錯誤", None

def search_company_info(brand_name):
    print(f"🔎 搜尋品牌: {brand_name}")
    results = serper_request(f"{brand_name} twincn")
    
    last_official_title = ""
    
    if results:
        for item in results:
            link = item.get("link", "")
            title = item.get("title", "")
            
            # 只處理台灣公司網的內頁連結
            if "twincn.com/item.aspx?no=" in link:
                current_title = clean_company_name(title)
                print(f"🌐 檢查內頁: {current_title} ({link})")
                
                status, phone = get_info_from_twincn_url(link)
                
                if status == "營業中":
                    return current_title, phone
                elif status == "已停業":
                    last_official_title = "已停業"
                    print(f"⚠️ 該項目已停業，跳過並尋找下一個...")
                    continue
        
    return last_official_title if last_official_title else "查無品牌", "查無資料"

def main():
    service = get_gspread_service()
    sheet = service.spreadsheets()
    range_to_read = f"{SHEET_NAME}!A2:K"
    
    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_to_read).execute()
        rows = result.get('values', [])
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return

    for i, row in enumerate(rows):
        while len(row) < 11: row.append("")
        brand_name = row[2].strip()      # C欄 (品牌名)
        status = row[7].strip()          # H欄 (狀態)
        existing_title = row[9].strip()  # J欄 (公司抬頭)
        
        # 僅處理 狀態為「已分配」且 J 欄尚未正確填寫的資料
        if status == "已分配" and not existing_title:
            if not brand_name: continue
            
            official_title, phone = search_company_info(brand_name)
            
            row_num = i + 2
            update_range = f"{SHEET_NAME}!J{row_num}:K{row_num}"
            update_body = {"values": [[official_title, phone]]}
            
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption="RAW",
                body=update_body
            ).execute()
            
            print(f"✅ 完成回填: {brand_name} -> {official_title} | {phone}")
            time.sleep(1.2) # 避開 Rate Limit

    print("🏁 處理結束。")

if __name__ == "__main__":
    main()
