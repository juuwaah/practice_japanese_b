import gspread
from google.auth import exceptions
import pandas as pd
import os
import json
import tempfile

def get_google_sheets_client():
    """Google Sheets APIクライアントを取得"""
    try:
        # 1. 環境変数からJOSN文字列を取得（Railway環境用）
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if service_account_json:
            # JSON文字列を辞書に変換
            try:
                credentials_dict = json.loads(service_account_json)
                # gspreadで辞書から認証
                gc = gspread.service_account_from_dict(credentials_dict)
                print("環境変数からGoogle Sheets認証成功")
                return gc
            except json.JSONDecodeError as e:
                print(f"環境変数のJSONパースエラー: {e}")
            except Exception as e:
                print(f"環境変数からの認証エラー: {e}")
        
        # 2. ファイルベース認証（ローカル開発用）
        credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'japaneseapp-466108-327bc89dfc8e.json')
        
        if os.path.exists(credentials_path):
            gc = gspread.service_account(filename=credentials_path)
            print("ファイルからGoogle Sheets認証成功")
            return gc
        else:
            print(f"認証ファイルが見つかりません: {credentials_path}")
        
    except Exception as e:
        print(f"Google Sheets認証エラー: {e}")
    
    return None

def load_vocab_data_from_sheets(sheet_id, sheet_name):
    """Google SheetsからJLPT語彙データを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            print(f"Google Sheets認証に失敗しました。語彙データ({sheet_name})の読み込みをスキップします。")
            return None
            
        # スプレッドシートを開く
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # データを取得してDataFrameに変換
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 空の行を削除
        df = df.dropna(subset=["Kanji", "Word", "Meaning", "Type"])
        
        print(f"Google Sheetsから語彙データ({sheet_name})を正常に読み込みました（{len(df)}件）")
        return df
        
    except Exception as e:
        print(f"Google Sheetsデータ読み込みエラー({sheet_name}): {e}")
        return None

def load_grammar_data_from_sheets(sheet_id, sheet_name):
    """Google SheetsからJLPT文法データを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            print(f"Google Sheets認証に失敗しました。文法データ({sheet_name})の読み込みをスキップします。")
            return None
            
        # スプレッドシートを開く
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # データを取得してDataFrameに変換
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Grammar列から空でない値のリストを取得
        grammar_list = df["Grammar"].dropna().tolist()
        
        print(f"Google Sheetsから文法データ({sheet_name})を正常に読み込みました（{len(grammar_list)}件）")
        return grammar_list
        
    except Exception as e:
        print(f"Google Sheets文法データ読み込みエラー({sheet_name}): {e}")
        return None

def load_youtube_listening_data_from_sheets(sheet_id, sheet_name):
    """Google SheetsからYouTubeリスニングデータを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            print("Google Sheets認証に失敗しました。フォールバックデータを返します。")
            return get_fallback_listening_data()
            
        # スプレッドシートを開く
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # データを取得してDataFrameに変換
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 必要な列が存在するかチェック
        required_columns = ['id', 'quiz_num', 'level', 'title', 'video_id', 'start', 'end', 'question', 'opt1', 'opt2', 'opt3', 'opt4', 'correct', 'explanation', 'explanation_time']
        optional_columns = ['channel_link']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"必要な列が見つかりません: {missing_columns}")
            return get_fallback_listening_data()
        
        # 空の行を削除
        df = df.dropna(subset=['id', 'quiz_num', 'level', 'title', 'video_id', 'question'])
        
        result = df.to_dict('records')
        print(f"Google SheetsからYouTubeリスニングデータを正常に読み込みました（{len(result)}件）")
        return result
        
    except Exception as e:
        print(f"Google Sheetsリスニングクイズデータ読み込みエラー: {e}")
        return get_fallback_listening_data()

def get_fallback_listening_data():
    """Google Sheets読み込み失敗時のフォールバックデータ"""
    print("フォールバックのサンプルYouTubeリスニングデータを使用します")
    
    # サンプルデータを返す（実際の運用では空のリストまたは最小限のデータ）
    fallback_data = [
        {
            'id': 'sample001',
            'quiz_num': 1,
            'level': 'N5',
            'title': 'Sample YouTube Listening Quiz',
            'video_id': 'dQw4w9WgXcQ',  # Rick Roll video ID (safe sample)
            'start': 0,
            'end': 30,
            'question': 'このビデオの内容について、正しい答えを選んでください。',
            'opt1': '選択肢1',
            'opt2': '選択肢2', 
            'opt3': '選択肢3',
            'opt4': '選択肢4',
            'correct': '1',
            'explanation': 'これはサンプルの説明です。Google Sheetsから読み込めない場合のフォールバックデータです。',
            'explanation_time': '',
            'channel_link': 'https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw'
        }
    ]
    
    return fallback_data

def load_onomatopoeia_data_from_sheets(sheet_id, sheet_name):
    """Google Sheetsからオノマトペデータを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            print(f"Google Sheets認証に失敗しました。オノマトペデータ({sheet_name})の読み込みをスキップします。")
            return None
            
        # スプレッドシートを開く
        sheet = gc.open_by_key(sheet_id)
        worksheet = sheet.worksheet(sheet_name)
        
        # データを取得（ヘッダー付き）
        records = worksheet.get_all_records()
        
        # オノマトペリストに変換
        onomatopoeia_list = []
        for record in records:
            if record.get('word') and record.get('meaning'):  # 必須フィールドをチェック
                onomatopoeia_item = {
                    'word': str(record.get('word', '')).strip(),
                    'meaning': str(record.get('meaning', '')).strip(),
                    'category': str(record.get('category', '擬音語')).strip()
                }
                
                # ref_link列が存在する場合は追加
                ref_link = record.get('ref_link', '').strip()
                if ref_link:
                    onomatopoeia_item['ref_link'] = ref_link
                    
                onomatopoeia_list.append(onomatopoeia_item)
        
        print(f"オノマトペデータ読み込み成功: {len(onomatopoeia_list)}個")
        return onomatopoeia_list
        
    except Exception as e:
        print(f"オノマトペデータ読み込みエラー: {e}")
        return None