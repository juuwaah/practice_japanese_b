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

# フォールバック用のローカルデータ
ONOMATOPOEIA_LIST_FALLBACK = [
    # 擬音語 - 音の真似（30個）
    {"word": "ゴロゴロ", "meaning": "rumbling, rolling", "category": "擬音語"},
    {"word": "パチパチ", "meaning": "crackling, clapping", "category": "擬音語"},
    {"word": "ザーザー", "meaning": "pouring rain", "category": "擬音語"},
    {"word": "ピンポン", "meaning": "ding-dong", "category": "擬音語"},
    {"word": "ガタガタ", "meaning": "rattling, chattering", "category": "擬音語"},
    {"word": "ドンドン", "meaning": "bang bang, rapidly", "category": "擬音語"},
    {"word": "チクタク", "meaning": "tick-tock", "category": "擬音語"},
    {"word": "ブーブー", "meaning": "honking, buzzing", "category": "擬音語"},
    {"word": "パタパタ", "meaning": "flapping, pattering", "category": "擬音語"},
    {"word": "ジャージャー", "meaning": "gushing water", "category": "擬音語"},
    {"word": "ピューピュー", "meaning": "whistling wind", "category": "擬音語"},
    {"word": "ガチャガチャ", "meaning": "clattering", "category": "擬音語"},
    {"word": "ペラペラ", "meaning": "fluttering pages", "category": "擬音語"},
    {"word": "ドキンドキン", "meaning": "strong heartbeat", "category": "擬音語"},
    {"word": "ザクザク", "meaning": "crunching", "category": "擬音語"},
    {"word": "プルプル", "meaning": "vibrating phone", "category": "擬音語"},
    {"word": "カチカチ", "meaning": "clicking", "category": "擬音語"},
    {"word": "ビューン", "meaning": "whooshing", "category": "擬音語"},
    {"word": "ポンポン", "meaning": "tapping lightly", "category": "擬音語"},
    {"word": "シューシュー", "meaning": "hissing steam", "category": "擬音語"},
    {"word": "コンコン", "meaning": "knocking", "category": "擬音語"},
    {"word": "ピーピー", "meaning": "beeping", "category": "擬音語"},
    {"word": "バタバタ", "meaning": "flapping, busy noise", "category": "擬音語"},
    {"word": "ジリジリ", "meaning": "sizzling", "category": "擬音語"},
    {"word": "プシュー", "meaning": "air releasing", "category": "擬音語"},
    {"word": "カラカラ", "meaning": "dry rattling", "category": "擬音語"},
    {"word": "ペタペタ", "meaning": "sticky sounds", "category": "擬音語"},
    {"word": "グルグル", "meaning": "spinning sound", "category": "擬音語"},
    {"word": "ドサドサ", "meaning": "thumping down", "category": "擬音語"},
    {"word": "チャリンチャリン", "meaning": "jingling coins", "category": "擬音語"},
    
    # 擬態語 - 様子・動きの真似（40個）
    {"word": "キラキラ", "meaning": "sparkling, glittering", "category": "擬態語"},
    {"word": "フワフワ", "meaning": "fluffy, soft", "category": "擬態語"},
    {"word": "ツルツル", "meaning": "smooth, slippery", "category": "擬態語"},
    {"word": "ザラザラ", "meaning": "rough, grainy", "category": "擬態語"},
    {"word": "ヌルヌル", "meaning": "slimy, slippery", "category": "擬態語"},
    {"word": "サラサラ", "meaning": "smooth flowing", "category": "擬態語"},
    {"word": "ベタベタ", "meaning": "sticky", "category": "擬態語"},
    {"word": "カサカサ", "meaning": "dry, rustling", "category": "擬態語"},
    {"word": "モチモチ", "meaning": "chewy, soft", "category": "擬態語"},
    {"word": "パリパリ", "meaning": "crispy", "category": "擬態語"},
    {"word": "プリプリ", "meaning": "bouncy, fresh", "category": "擬態語"},
    {"word": "コリコリ", "meaning": "crunchy texture", "category": "擬態語"},
    {"word": "ふらふら", "meaning": "unsteady, dizzy", "category": "擬態語"},
    {"word": "よろよろ", "meaning": "staggering", "category": "擬態語"},
    {"word": "すたすた", "meaning": "walking briskly", "category": "擬態語"},
    {"word": "のろのろ", "meaning": "moving slowly", "category": "擬態語"},
    {"word": "てくてく", "meaning": "walking steadily", "category": "擬態語"},
    {"word": "ぴょんぴょん", "meaning": "hopping", "category": "擬態語"},
    {"word": "ひらひら", "meaning": "fluttering gently", "category": "擬態語"},
    {"word": "ゆらゆら", "meaning": "swaying gently", "category": "擬態語"},
    {"word": "くるくる", "meaning": "spinning", "category": "擬態語"},
    {"word": "ぐらぐら", "meaning": "shaking, wobbly", "category": "擬態語"},
    {"word": "びっしり", "meaning": "densely packed", "category": "擬態語"},
    {"word": "ぎっしり", "meaning": "tightly packed", "category": "擬態語"},
    {"word": "さっぱり", "meaning": "refreshing, clean", "category": "擬態語"},
    {"word": "すっきり", "meaning": "clear, refreshed", "category": "擬態語"},
    {"word": "ばっちり", "meaning": "perfectly", "category": "擬態語"},
    {"word": "しっかり", "meaning": "firmly, properly", "category": "擬態語"},
    {"word": "ぽっかり", "meaning": "floating alone", "category": "擬態語"},
    {"word": "ふっくら", "meaning": "plump, soft", "category": "擬態語"},
    {"word": "つやつや", "meaning": "glossy, shiny", "category": "擬態語"},
    {"word": "ぴかぴか", "meaning": "shining, spotless", "category": "擬態語"},
    {"word": "ぺたぺた", "meaning": "sticking", "category": "擬態語"},
    {"word": "ちらちら", "meaning": "flickering", "category": "擬態語"},
    {"word": "ぼんやり", "meaning": "vaguely, dimly", "category": "擬態語"},
    {"word": "はっきり", "meaning": "clearly", "category": "擬態語"},
    {"word": "ぐっすり", "meaning": "sleeping soundly", "category": "擬態語"},
    {"word": "うとうと", "meaning": "dozing", "category": "擬態語"},
    {"word": "こっそり", "meaning": "secretly", "category": "擬態語"},
    {"word": "そっと", "meaning": "gently, quietly", "category": "擬態語"},
    
    # 擬情語 - 感情・心理状態の真似（30個）
    {"word": "ワクワク", "meaning": "excited, thrilled", "category": "擬情語"},
    {"word": "ドキドキ", "meaning": "heart pounding", "category": "擬情語"},
    {"word": "ウキウキ", "meaning": "cheerful, buoyant", "category": "擬情語"},
    {"word": "ルンルン", "meaning": "happy, in good mood", "category": "擬情語"},
    {"word": "イライラ", "meaning": "irritated, frustrated", "category": "擬情語"},
    {"word": "ムカムカ", "meaning": "annoyed, nauseous", "category": "擬情語"},
    {"word": "ドキッと", "meaning": "startled", "category": "擬情語"},
    {"word": "ハラハラ", "meaning": "nervous, worried", "category": "擬情語"},
    {"word": "ソワソワ", "meaning": "restless, fidgety", "category": "擬情語"},
    {"word": "ビクビク", "meaning": "timid, fearful", "category": "擬情語"},
    {"word": "ホッと", "meaning": "relieved", "category": "擬情語"},
    {"word": "ガッカリ", "meaning": "disappointed", "category": "擬情語"},
    {"word": "ムシムシ", "meaning": "humid, stuffy", "category": "擬情語"},
    {"word": "ジメジメ", "meaning": "damp, gloomy", "category": "擬情語"},
    {"word": "カリカリ", "meaning": "irritable, on edge", "category": "擬情語"},
    {"word": "ピリピリ", "meaning": "tense, on edge", "category": "擬情語"},
    {"word": "ゾクゾク", "meaning": "thrilling, shivering", "category": "擬情語"},
    {"word": "ブルブル", "meaning": "shivering, trembling", "category": "擬情語"},
    {"word": "ヒヤヒヤ", "meaning": "anxious, worried", "category": "擬情語"},
    {"word": "ドキンと", "meaning": "heart skipping", "category": "擬情語"},
    {"word": "モヤモヤ", "meaning": "frustrated, unclear", "category": "擬情語"},
    {"word": "スッキリ", "meaning": "refreshed, clear", "category": "擬情語"},
    {"word": "ゆったり", "meaning": "relaxed, leisurely", "category": "擬情語"},
    {"word": "のんびり", "meaning": "carefree, relaxed", "category": "擬情語"},
    {"word": "ぼーっと", "meaning": "absent-minded", "category": "擬情語"},
    {"word": "しんみり", "meaning": "moved, touched", "category": "擬情語"},
    {"word": "じーん", "meaning": "deeply moved", "category": "擬情語"},
    {"word": "うっとり", "meaning": "enchanted, dreamy", "category": "擬情語"},
    {"word": "にっこり", "meaning": "smiling warmly", "category": "擬情語"}
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