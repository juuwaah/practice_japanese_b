import gspread
from google.auth import exceptions
import pandas as pd
import os

def get_google_sheets_client():
    """Google Sheets APIクライアントを取得"""
    try:
        # サービスアカウントキーファイルのパスを環境変数から取得
        credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'japaneseapp-466108-327bc89dfc8e.json')
        
        # gspreadでサービスアカウント認証
        gc = gspread.service_account(filename=credentials_path)
        return gc
    except Exception as e:
        print(f"Google Sheets認証エラー: {e}")
        return None

def load_vocab_data_from_sheets(sheet_id, sheet_name):
    """Google SheetsからJLPT語彙データを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            return None
            
        # スプレッドシートを開く
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # データを取得してDataFrameに変換
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 空の行を削除
        df = df.dropna(subset=["Kanji", "Word", "Meaning", "Type"])
        
        return df
        
    except Exception as e:
        print(f"Google Sheetsデータ読み込みエラー: {e}")
        return None

def load_grammar_data_from_sheets(sheet_id, sheet_name):
    """Google SheetsからJLPT文法データを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            return None
            
        # スプレッドシートを開く
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # データを取得してDataFrameに変換
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Grammar列から空でない値のリストを取得
        grammar_list = df["Grammar"].dropna().tolist()
        
        return grammar_list
        
    except Exception as e:
        print(f"Google Sheets文法データ読み込みエラー: {e}")
        return None

def load_youtube_listening_data_from_sheets(sheet_id, sheet_name):
    """Google SheetsからYouTubeリスニングデータを読み込み"""
    try:
        gc = get_google_sheets_client()
        if gc is None:
            return None
            
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
            return None
        
        # 空の行を削除
        df = df.dropna(subset=['id', 'quiz_num', 'level', 'title', 'video_id', 'question'])
        
        result = df.to_dict('records')
        return result
        
    except Exception as e:
        print(f"Google Sheetsリスニングクイズデータ読み込みエラー: {e}")
        return None