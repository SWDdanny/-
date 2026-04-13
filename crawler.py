import os
import requests
import json
import pandas as pd
import time

def search_with_serper(query):
    """
    使用 Serper.dev API 獲取 Google 搜尋結果
    """
    url = "https://google.serper.dev/search"
    api_key = os.getenv("SERPER_API_KEY")
    
    if not api_key:
        print("❌ 錯誤: 找不到環境變數 SERPER_API_KEY")
        return None

    payload = json.dumps({
        "q": query,
        "gl": "tw",    # 台灣地區
        "hl": "zh-tw", # 繁體中文
        "num": 5       # 抓取前 5 筆
    })
    
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 搜尋 '{query}' 時發生連線錯誤: {e}")
        return None

def main():
    print("🚀 程式啟動 (Serper.dev API 增強版)...")
    
    # 這裡放你的品牌清單，或者從 CSV 讀取
    brands = [
        "校園3C學購網", "ORBIS", "印花樂", "台北凱撒大飯店", 
        "達特聖克", "植村秀", "新光三越", "Bosch", "夏普", 
        "飛利浦", "大同", "Dyson", "VESTA", "TESCOM"
    ]
    
    results_list = []

    for brand in brands:
        print(f"🔎 處理中: {brand}...")
        
        search_data = search_with_serper(brand)
        
        if search_data and "organic" in search_data and len(search_data["organic"]) > 0:
            # 取得第一筆搜尋結果作為主要參考
            top_result = search_data["organic"][0]
            
            data_row = {
                "品牌名稱": brand,
                "標題": top_result.get("title"),
                "連結": top_result.get("link"),
                "摘要": top_result.get("snippet")
            }
            results_list.append(data_row)
            print(f"✅ 成功找到: {top_result.get('title')}")
        else:
            print(f"⚠️ 無法找到 {brand} 的資料")
            
        # API 呼叫雖然快，但建議還是留一點微小的間隔
        time.sleep(0.5)

    # 存檔成 CSV (如果你需要的話)
    if results_list:
        df = pd.DataFrame(results_list)
        df.to_csv("search_results.csv", index=False, encoding="utf-8-sig")
        print(f"\n🏁 任務完成！共抓取 {len(results_list)} 筆資料，已存入 search_results.csv")
    else:
        print("\n終止：沒有抓取到任何資料。")

if __name__ == "__main__":
    main()
