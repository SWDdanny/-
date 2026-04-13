import os, json, time, re, requests, urllib.parse
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googlesearch import search  # 引入 Google 搜尋

# --- 設定區 ---
SPREADSHEET_ID = '1jb7MZ5w00zNs3T_I7lxT24nEChudAUnUnpXLm77sOXU'
SHEET_NAME = '品牌名單' 
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_service():
    info_str = os.environ.get("GCP_SERVICE_ACCOUNT")
    if info_str:
        return build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_info(json.loads(info_str), scopes=SCOPES))
    return build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_file('service_account.json', scopes=SCOPES))

def get_twincn_url_via_google(brand_name):
    """透過 Google 搜尋找到該品牌在台灣公司網的詳細頁面"""
    query = f"site:twincn.com {brand_name} 公司基本資料"
    try:
        # 只取搜尋結果的第一筆
        for url in search(query, num_results=1, lang="zh-TW"):
            if "item.aspx" in url:
                return url
    except Exception as e:
        print(f"DEBUG: Google 搜尋失敗 -> {e}")
    return None

def fetch_details_from_twincn(target_url):
    """根據 URL 進入台灣公司網抓取電話與正式名稱"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(target_url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 抓取抬頭
        h1 = soup.find('h1')
        title = h1.text.strip().replace("公司基本資料", "").strip() if h1 else "未知公司"
        
        # 抓取電話 (從 Meta 標籤或表格抓取)
        phone = "查無電話"
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            content = meta_desc.get('content', '')
            phone_match = re.search(r'電話:([\d-]+)', content)
            if phone_match:
                phone = phone_match.group(1)
        
        # 備援：如果 Meta 沒抓到，改抓表格內容
        if phone == "查無電話":
            page_text = soup.get_text()
            phone_match = re.search(r'0\d{1,2}-\d{6,9}', page_text)
            if phone_match:
                phone = phone_match.group()

        return title, phone
    except Exception as e:
        print(f"DEBUG: 進入頁面抓取出錯 -> {e}")
        return None, None

def main():
    print("🚀 程式啟動 (Google 搜尋優化版)...")
    service = get_service()
    sheet = service.spreadsheets()
    
    try:
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:K").execute()
        values = result.get('values', [])
    except Exception as e:
        print(f"❌ 讀取 Sheet 失敗: {e}")
        return

    if not values: return
    header = values[0]
    col_brand, col_status = -1, -1
    for idx, col in enumerate(header):
        if "品牌名稱" in col: col_brand = idx
        if "狀態" in col: col_status = idx

    for i, row in enumerate(values):
        if i == 0: continue
        
        status = row[col_status] if len(row) > col_status else ""
        brand = row[col_brand] if len(row) > col_brand else ""
        # 檢查 J 欄 (Index 9) 是否已有資料
        has_data = len(row) > 9 and row[9].strip() != "" and row[9] != "查無資料"
        
        if status == "已分配" and brand and not has_data:
            print(f"🔎 處理中: {brand}...")
            
            # 第一步：先用 Google 找正確的頁面網址
            target_url = get_twincn_url_via_google(brand)
            
            if target_url:
                # 第二步：進入該網址爬取資料
                official_title, phone = fetch_details_from_twincn(target_url)
                
                if official_title:
                    update_range = f"{SHEET_NAME}!J{i+1}:K{i+1}"
                    body = {'values': [[official_title, phone]]}
                    sheet.values().update(
                        spreadsheetId=SPREADSHEET_ID, range=update_range,
                        valueInputOption="USER_ENTERED", body=body
                    ).execute()
                    print(f"✅ 已回填: {official_title} / {phone}")
                    time.sleep(5) # 稍微延長等待，避免 Google 封鎖
                    continue

            # 若完全找不到
            print(f"⚠️ 無法找到 {brand} 的資料")
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!J{i+1}",
                valueInputOption="USER_ENTERED", body={'values': [["查無資料"]]}
            ).execute()
            time.sleep(2)

    print("🏁 程式執行完畢。")

if __name__ == "__main__":
    main()
