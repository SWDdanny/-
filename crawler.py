import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googlesearch import search

# 設定區
SPREADSHEET_ID = '1jb7MZ5w00zNs3T_I7lxT24nEChudAUnUnpXLm77sOXU'
SHEET_NAME = '品牌名單'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_service():
    """連線 Google Sheets API"""
    if "GCP_SERVICE_ACCOUNT" in os.environ:
        # GitHub 環境：從 Secret 讀取
        info = json.loads(os.environ["GCP_SERVICE_ACCOUNT"])
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # 本機環境：從檔案讀取
        creds = service_account.Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def crawl_twincn(brand_name):
    """搜尋 Google 並抓取台灣公司網資料"""
    query = f"{brand_name} 台灣公司 site:twincn.com"
    try:
        # pause=5.0 避免被 Google 封鎖，stop=3 只看前三個結果
        for url in search(query, num_results=3, lang="zh-TW", pause=5.0):
            if "twincn.com" in url:
                headers = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get(url, headers=headers, timeout=10)
                resp.encoding = 'utf-8'
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 抓取抬頭
                title = soup.find('h1').text.strip() if soup.find('h1') else ""
                # 抓取電話 (尋找 02-12345678 格式)
                phone_match = re.search(r'0\d{1,2}-\d{6,8}', soup.get_text())
                phone = phone_match.group() if phone_match else ""
                
                return title, phone
    except Exception as e:
        print(f"搜尋錯誤: {e}")
    return None, None

def main():
    service = get_service()
    sheet = service.spreadsheets()
    
    # 讀取整張表
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:K").execute()
    values = result.get('values', [])
    if not values: return

    for i, row in enumerate(values):
        if i == 0: continue # 跳過標題
        if len(row) < 8: continue # 欄位不足跳過
        
        brand_name = row[2] # C欄
        status = row[7]     # H欄
        
        # 判斷：狀態是已分配 且 J欄(Index 9)是空的
        is_assigned = (status == "已分配")
        is_empty = len(row) <= 9 or row[9] == "" or row[9] == "查無資料"
        
        if is_assigned and is_empty:
            print(f"🔍 正在抓取: {brand_name}")
            official_title, phone = crawl_twincn(brand_name)
            
            # 更新 J 欄與 K 欄
            update_range = f"{SHEET_NAME}!J{i+1}:K{i+1}"
            body = {'values': [[official_title or "查無資料", phone or "查無資料"]]}
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID, range=update_range,
                valueInputOption="USER_ENTERED", body=body).execute()
            
            print(f"✅ 更新成功: {brand_name} -> {official_title}")
            time.sleep(10) # 抓完一筆休息 10 秒，保護帳號

if __name__ == "__main__":
    main()
