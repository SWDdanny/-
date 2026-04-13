import os, json, time, re, requests, urllib.parse
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 設定區 ---
SPREADSHEET_ID = '1jb7MZ5w00zNs3T_I7lxT24nEChudAUnUnpXLm77sOXU'
SHEET_NAME = '品牌名單' 
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_service():
    info_str = os.environ.get("GCP_SERVICE_ACCOUNT")
    if info_str:
        return build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_info(json.loads(info_str), scopes=SCOPES))
    return build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_file('service_account.json', scopes=SCOPES))

def search_twincn_directly(brand_name):
    """直接使用台灣公司網內建搜尋，不透過 Google"""
    encoded_name = urllib.parse.quote(brand_name)
    search_url = f"https://www.twincn.com/L_search.aspx?q={encoded_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print(f"DEBUG: 正在台灣公司網搜尋 -> {brand_name}")
    try:
        resp = requests.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 尋找第一個搜尋結果連結
        link = soup.select_one('td a[href^="item.aspx"]')
        if not link:
            print(f"DEBUG: 台灣公司網內找不到 {brand_name}")
            return None, None
            
        target_url = "https://www.twincn.com/" + link['href']
        print(f"DEBUG: 找到公司頁面 -> {target_url}")
        
        # 進入詳細頁面
        item_resp = requests.get(target_url, headers=headers, timeout=15)
        item_resp.encoding = 'utf-8'
        item_soup = BeautifulSoup(item_resp.text, 'html.parser')
        
        # 抓取抬頭 (H1)
        h1 = item_soup.find('h1')
        title = h1.text.strip().replace("公司基本資料", "") if h1 else "未知公司"
        
        # 抓取電話
        page_content = item_soup.get_text()
        phone_match = re.search(r'0\d{1,2}-\d{6,9}', page_content)
        phone = phone_match.group() if phone_match else "查無電話"
        
        return title, phone
    except Exception as e:
        print(f"DEBUG: 爬蟲出錯 -> {e}")
        return None, None

def main():
    print("🚀 程式啟動...")
    service = get_service()
    sheet = service.spreadsheets()
    
    try:
        # 1. 讀取資料
        print(f"📂 正在讀取工作表: {SHEET_NAME}")
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!A:K").execute()
        values = result.get('values', [])
    except Exception as e:
        print(f"❌ 讀取 Sheet 失敗！請檢查工作表名稱是否真的叫 '{SHEET_NAME}'。錯誤: {e}")
        return

    if not values:
        print("⚠️ Sheet 是空的。")
        return

    header = values[0]
    print(f"📊 標題列偵測: {header}")

    # 找到關鍵欄位索引 (強制轉為字串避免空格問題)
    col_brand, col_status = -1, -1
    for idx, col in enumerate(header):
        if "品牌名稱" in col: col_brand = idx
        if "狀態" in col: col_status = idx

    if col_brand == -1 or col_status == -1:
        print(f"❌ 找不到必要欄位！目前標題包含: {header}")
        return

    for i, row in enumerate(values):
        if i == 0: continue # 跳過標題
        
        # 確保資料列長度足夠
        status = row[col_status] if len(row) > col_status else ""
        brand = row[col_brand] if len(row) > col_brand else ""
        # 檢查 J 欄 (Index 9) 是否已有資料
        has_title = len(row) > 9 and row[9].strip() != "" and row[9] != "查無資料"
        
        if status == "已分配" and brand and not has_title:
            print(f"🔎 處理中: {brand} (第 {i+1} 行)")
            official_title, phone = search_twincn_directly(brand)
            
            if official_title:
                # 只更新 J 和 K 欄，不准動到前面！
                update_range = f"{SHEET_NAME}!J{i+1}:K{i+1}"
                body = {'values': [[official_title, phone]]}
                sheet.values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=update_range,
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
                print(f"✅ 已回填: {official_title}")
            
            time.sleep(3) # 稍微停頓

    print("🏁 程式執行完畢。")

if __name__ == "__main__":
    main()
