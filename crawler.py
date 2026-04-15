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

def extract_phone(text):
    """
    通用電話提取：支持括號, 空格, #分機, 橫槓
    """
    if not text: return None
    # 正則：找 0 開頭，中間容許括號、空格、橫槓，最後容許 #分機
    phone_pattern = r'\(?0\d{1,2}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}(?:\s?#\d+)?'
    match = re.search(phone_pattern, text)
    return match.group().strip() if match else None

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
    
    found_inactive = False
    
    if results:
        for item in results:
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            title = item.get("title", "")
            
            if "twincn.com/item.aspx?no=" in link:
                current_title = clean_company_name(title)
                
                # --- 策略 1: 先看 Snippet 是否有電話且是否停業 ---
                if "停業" in snippet or "廢止" in snippet or "歇業" in snippet:
                    print(f"⚠️ Snippet 顯示已停業: {current_title}")
                    found_inactive = True
                    continue
                
                snippet_phone = extract_phone(snippet)
                if snippet_phone:
                    print(f"✨ 從摘要直接抓到電話: {snippet_phone}")
                    return current_title, snippet_phone
                
                # --- 策略 2: Snippet 沒電話，點進內頁看 ---
                print(f"🌐 摘要無電話，進入內頁: {link}")
                status, page_phone = get_info_from_twincn_page(link)
                
                if status == "營業中" and page_phone:
                    return current_title, page_phone
                elif status == "已停業":
                    found_inactive = True
                    continue

    # 最後回傳邏輯
    final_title = "已停業" if found_inactive else "查無品牌"
    return final_title, "查無資料"

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
        brand_name = row[2].strip()
        status = row[7].strip()
        existing_title = row[9].strip()
        
        if status == "已分配" and not existing_title:
            if not brand_name: continue
            
            official_title, phone = search_company_info(brand_name)
            
            row_num = i + 2
            update_range = f"{SHEET_NAME}!J{row_num}:K{row_num}"
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption="RAW",
                body={"values": [[official_title, phone]]}
            ).execute()
            
            print(f"✅ 完成: {brand_name} -> {official_title} | {phone}")
            time.sleep(1)

if __name__ == "__main__":
    main()
