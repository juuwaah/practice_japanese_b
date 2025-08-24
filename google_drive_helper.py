"""
Google Drive API Helper for Blog Posts
"""

import os
import json
from datetime import datetime
import re
from typing import List, Dict, Optional

# Try to import Google APIs, but handle failures gracefully
try:
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    GOOGLE_APIS_AVAILABLE = True
    print("Google APIs loaded successfully")
except Exception as e:
    print(f"Warning: Google APIs not available: {e}")
    GOOGLE_APIS_AVAILABLE = False
    build = None
    service_account = None

# Google Drive設定
BLOG_FOLDER_ID = '1dm9jGD2qXzLVcW7JbOnjL_tg9eqM6PZS'
SERVICE_ACCOUNT_FILE = 'japaneseapp-466108-327bc89dfc8e.json'  # 既存のサービスアカウントファイル

def get_drive_service():
    """Google Drive APIサービスを取得"""
    if not GOOGLE_APIS_AVAILABLE:
        print("Google APIs not available - using mock data")
        return None
        
    try:
        # 環境変数からサービスアカウント情報を取得（Railway用）
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if service_account_json:
            # 環境変数から認証情報を取得（本番環境）
            service_account_info = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/drive.readonly',
                       'https://www.googleapis.com/auth/documents.readonly']
            )
            print("Using Google service account from environment variable")
        elif os.path.exists(SERVICE_ACCOUNT_FILE):
            # ローカル開発用：ファイルから認証情報を取得
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=['https://www.googleapis.com/auth/drive.readonly',
                       'https://www.googleapis.com/auth/documents.readonly']
            )
            print("Using Google service account from file")
        else:
            print(f"ERROR: No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON env var or place {SERVICE_ACCOUNT_FILE}")
            return None
        
        drive_service = build('drive', 'v3', credentials=credentials)
        return drive_service
    except Exception as e:
        print(f"ERROR: Failed to initialize Google Drive service: {e}")
        return None

def get_docs_service():
    """Google Docs APIサービスを取得"""
    if not GOOGLE_APIS_AVAILABLE:
        print("Google APIs not available - using mock data")
        return None
        
    try:
        # 環境変数からサービスアカウント情報を取得（Railway用）
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if service_account_json:
            # 環境変数から認証情報を取得（本番環境）
            service_account_info = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/drive.readonly',
                       'https://www.googleapis.com/auth/documents.readonly']
            )
            print("Using Google service account from environment variable")
        elif os.path.exists(SERVICE_ACCOUNT_FILE):
            # ローカル開発用：ファイルから認証情報を取得
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=['https://www.googleapis.com/auth/drive.readonly',
                       'https://www.googleapis.com/auth/documents.readonly']
            )
            print("Using Google service account from file")
        else:
            print(f"ERROR: No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON env var or place {SERVICE_ACCOUNT_FILE}")
            return None
        
        docs_service = build('docs', 'v1', credentials=credentials)
        return docs_service
    except Exception as e:
        print(f"ERROR: Failed to initialize Google Docs service: {e}")
        return None

def get_blog_documents() -> List[Dict]:
    """ブログフォルダ内のGoogleドキュメントを取得"""
    drive_service = get_drive_service()
    if not drive_service:
        # Return mock data for testing when APIs aren't available
        if not GOOGLE_APIS_AVAILABLE:
            return [
                {
                    'id': 'mock-doc-1',
                    'title': '日本語学習のコツ - Japanese Learning Tips',
                    'created_at': '2024-01-15T10:00:00Z',
                    'modified_at': '2024-01-16T14:30:00Z',
                    'created_date': '2024年01月15日',
                    'modified_date': '2024年01月16日'
                },
                {
                    'id': 'mock-doc-2',
                    'title': 'JLPT対策のポイント - JLPT Study Points',
                    'created_at': '2024-01-10T09:00:00Z',
                    'modified_at': '2024-01-10T09:00:00Z',
                    'created_date': '2024年01月10日',
                    'modified_date': '2024年01月10日'
                }
            ]
        return []
    
    try:
        # フォルダ内のGoogleドキュメントを検索
        query = f"'{BLOG_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
        results = drive_service.files().list(
            q=query,
            orderBy='modifiedTime desc',
            fields='files(id, name, modifiedTime, createdTime)'
        ).execute()
        
        documents = results.get('files', [])
        
        # ドキュメント情報を整形
        blog_posts = []
        for doc in documents:
            blog_posts.append({
                'id': doc['id'],
                'title': doc['name'],
                'created_at': doc.get('createdTime', ''),
                'modified_at': doc.get('modifiedTime', ''),
                'created_date': format_date(doc.get('createdTime', '')),
                'modified_date': format_date(doc.get('modifiedTime', ''))
            })
        
        print(f"Found {len(blog_posts)} blog documents")
        return blog_posts
        
    except Exception as e:
        print(f"ERROR: Failed to get blog documents: {e}")
        return []

def get_document_content(document_id: str) -> Optional[Dict]:
    """Googleドキュメントの内容を取得してHTMLに変換"""
    docs_service = get_docs_service()
    if not docs_service:
        # Return mock content for testing when APIs aren't available
        if not GOOGLE_APIS_AVAILABLE:
            mock_content = {
                'mock-doc-1': {
                    'title': '日本語学習のコツ - Japanese Learning Tips',
                    'content': '''<h1>日本語学習の効果的なコツ</h1>
<p>日本語を効率よく学習するための実践的なアドバイスをご紹介します。</p>

<h2>1. 毎日の習慣作り</h2>
<p>短時間でも毎日続けることが重要です。15分の学習でも継続することで大きな効果が期待できます。</p>

<h2>2. 実践的な練習</h2>
<p>文法や単語を覚えるだけでなく、実際に使ってみることが大切です。</p>

<h2>3. 楽しみながら学習</h2>
<p>ゲームやアニメなど、興味のあるコンテンツを使って学習すると継続しやすくなります。</p>'''
                },
                'mock-doc-2': {
                    'title': 'JLPT対策のポイント - JLPT Study Points',
                    'content': '''<h1>JLPT合格のための対策ポイント</h1>
<p>日本語能力試験（JLPT）に合格するための効果的な学習方法をお伝えします。</p>

<h2>レベル別対策</h2>
<p><strong>N5・N4:</strong> 基本的な文法と語彙を確実に身につけましょう。</p>
<p><strong>N3・N2:</strong> 読解力と聴解力の向上に重点を置きましょう。</p>
<p><strong>N1:</strong> 幅広い分野の語彙と複雑な文法表現をマスターしましょう。</p>

<h2>練習問題の活用</h2>
<p>過去問や模擬試験を繰り返し解いて、出題傾向に慣れることが重要です。</p>'''
                }
            }
            return mock_content.get(document_id)
        return None
    
    try:
        # ドキュメントの内容を取得
        document = docs_service.documents().get(documentId=document_id).execute()
        
        title = document.get('title', 'Untitled')
        content = document.get('body', {}).get('content', [])
        
        # コンテンツをHTMLに変換
        html_content = convert_to_html(content)
        
        return {
            'title': title,
            'content': html_content,
            'raw_content': content
        }
        
    except Exception as e:
        print(f"ERROR: Failed to get document content for {document_id}: {e}")
        return None

def convert_to_html(content: List[Dict]) -> str:
    """GoogleドキュメントのコンテンツをHTMLに変換"""
    html = []
    
    for element in content:
        if 'paragraph' in element:
            paragraph = element['paragraph']
            p_html = convert_paragraph_to_html(paragraph)
            if p_html.strip():  # 空の段落をスキップ
                html.append(p_html)
    
    return '\n'.join(html)

def convert_paragraph_to_html(paragraph: Dict) -> str:
    """段落をHTMLに変換"""
    if not paragraph.get('elements'):
        return '<p></p>'
    
    paragraph_style = paragraph.get('paragraphStyle', {})
    named_style_type = paragraph_style.get('namedStyleType', '')
    
    # 見出しスタイルの判定
    if named_style_type == 'HEADING_1':
        tag = 'h1'
    elif named_style_type == 'HEADING_2':
        tag = 'h2'
    elif named_style_type == 'HEADING_3':
        tag = 'h3'
    elif named_style_type == 'HEADING_4':
        tag = 'h4'
    else:
        tag = 'p'
    
    # テキスト要素を処理
    text_parts = []
    for element in paragraph['elements']:
        if 'textRun' in element:
            text_run = element['textRun']
            text = text_run.get('content', '')
            text_style = text_run.get('textStyle', {})
            
            # スタイル適用
            if text_style.get('bold'):
                text = f'<strong>{text}</strong>'
            if text_style.get('italic'):
                text = f'<em>{text}</em>'
            if text_style.get('underline'):
                text = f'<u>{text}</u>'
            
            # リンクの処理
            if 'link' in text_style:
                url = text_style['link'].get('url', '')
                if url:
                    text = f'<a href="{url}" target="_blank">{text}</a>'
            
            text_parts.append(text)
    
    content_text = ''.join(text_parts).strip()
    if not content_text:
        return ''
    
    return f'<{tag}>{content_text}</{tag}>'

def format_date(date_str: str) -> str:
    """日付文字列を読みやすい形式に変換"""
    if not date_str:
        return ''
    
    try:
        # ISO形式の日付をパース
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y年%m月%d日')
    except:
        return date_str

def search_blog_posts(query: str) -> List[Dict]:
    """ブログ記事を検索"""
    all_posts = get_blog_documents()
    if not query:
        return all_posts
    
    # タイトルでの簡単な検索
    query_lower = query.lower()
    filtered_posts = [
        post for post in all_posts 
        if query_lower in post['title'].lower()
    ]
    
    return filtered_posts