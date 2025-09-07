# onomatopoeia_data.py
# 日本語オノマトペデータベース

import os
from google_sheets_helper import load_onomatopoeia_data_from_sheets

# Google Sheets設定
ONOMATOPOEIA_SHEET_ID = os.getenv('ONOMATOPOEIA_SHEET_ID', '')
ONOMATOPOEIA_SHEET_NAME = 'Onomatopoeias'  # 固定シート名

# キャッシュ用変数
_onomatopoeia_cache = None
_cache_timestamp = None

# フォールバック用のローカルデータ（最小限）
ONOMATOPOEIA_LIST_FALLBACK = [
    {"word": "ワクワク", "meaning": "excited, thrilled", "category": "擬情語", "image": "present_tanoshimi.png"},
    {"word": "キラキラ", "meaning": "sparkling, glittering", "category": "擬態語", "image": "pose_shock_girl.png/money_genkin.png"},
    {"word": "ゴロゴロ", "meaning": "rumbling, rolling", "category": "擬音語", "image": "kotatsu_animal.png"}
]

def get_onomatopoeia_list():
    """オノマトペリストを取得（Google Sheets優先、キャッシュ対応）"""
    import time
    global _onomatopoeia_cache, _cache_timestamp
    
    # キャッシュの有効期限（30秒）
    CACHE_DURATION = 30
    current_time = time.time()
    
    # デバッグログ
    print(f"DEBUG: ONOMATOPOEIA_SHEET_ID = {ONOMATOPOEIA_SHEET_ID}")
    print(f"DEBUG: ONOMATOPOEIA_SHEET_NAME = {ONOMATOPOEIA_SHEET_NAME}")
    
    # キャッシュが有効な場合はそれを返す
    if (_onomatopoeia_cache is not None and 
        _cache_timestamp is not None and 
        (current_time - _cache_timestamp) < CACHE_DURATION):
        print("DEBUG: キャッシュからデータを取得")
        return _onomatopoeia_cache
    
    if ONOMATOPOEIA_SHEET_ID:
        print("DEBUG: Google Sheetsからデータを読み込み中...")
        # Google Sheetsから読み込み
        sheets_data = load_onomatopoeia_data_from_sheets(ONOMATOPOEIA_SHEET_ID, ONOMATOPOEIA_SHEET_NAME)
        if sheets_data:
            print(f"DEBUG: Google Sheetsから{len(sheets_data)}個のデータを取得")
            # ウキウキをチェック
            ukiuki = next((item for item in sheets_data if item['word'] == 'ウキウキ'), None)
            if ukiuki:
                print(f"DEBUG: ウキウキの意味 = {ukiuki['meaning']}")
            # キャッシュに保存
            _onomatopoeia_cache = sheets_data
            _cache_timestamp = current_time
            return sheets_data
        else:
            print("DEBUG: Google Sheetsからの読み込みに失敗")
    else:
        print("DEBUG: ONOMATOPOEIA_SHEET_IDが設定されていません")
    
    # フォールバック：ローカルデータを使用
    print("DEBUG: フォールバックローカルデータを使用")
    fallback_data = ONOMATOPOEIA_LIST_FALLBACK
    # フォールバックデータもキャッシュ
    _onomatopoeia_cache = fallback_data
    _cache_timestamp = current_time
    return fallback_data

def get_random_onomatopoeia():
    """ランダムにオノマトペを1つ選択"""
    import random
    onomatopoeia_list = get_onomatopoeia_list()
    return random.choice(onomatopoeia_list)

def get_onomatopoeia_by_category(category):
    """指定されたカテゴリのオノマトペリストを取得"""
    onomatopoeia_list = get_onomatopoeia_list()
    return [item for item in onomatopoeia_list if item["category"] == category]

def get_all_categories():
    """全カテゴリのリストを取得"""
    return ["擬音語", "擬態語", "擬情語"]

def clear_onomatopoeia_cache():
    """オノマトペキャッシュをクリア（管理者用）"""
    global _onomatopoeia_cache, _cache_timestamp
    _onomatopoeia_cache = None
    _cache_timestamp = None
    print("オノマトペキャッシュをクリアしました")