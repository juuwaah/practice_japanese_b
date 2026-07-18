"""
Google Drive API Helper for Blog Posts
"""

import os
import json
import time
from datetime import datetime
import re
from typing import List, Dict, Optional

# Try to import Google APIs, but handle failures gracefully
try:
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    from googleapiclient.errors import HttpError
    import httplib2
    import google_auth_httplib2
    GOOGLE_APIS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Google API libraries not installed: {e}")
    GOOGLE_APIS_AVAILABLE = False
    build = None
    service_account = None
    HttpError = None
except Exception as e:
    print(f"Warning: Google APIs not available due to system error: {e}")
    GOOGLE_APIS_AVAILABLE = False
    build = None
    service_account = None
    HttpError = None

# Google Drive設定
BLOG_FOLDER_ID = '1dm9jGD2qXzLVcW7JbOnjL_tg9eqM6PZS'
ONOMATOPOEIA_IMAGES_FOLDER_ID = '1CJllmtcGjqck2S4f1dMcfViMQPwLHgNv'  # オノマトペ画像フォルダ
SERVICE_ACCOUNT_FILE = 'japaneseapp-466108-327bc89dfc8e.json'  # 既存のサービスアカウントファイル

# Google APIへのTCP接続がハングするとgunicornワーカーごと殺されて502になるため、
# 必ずタイムアウトを設定する
HTTP_TIMEOUT_SECONDS = 10

# ブログ一覧は毎ページのサイドバーで呼ばれるため、TTL付きでキャッシュし
# API障害時は古いデータを返し続ける
BLOG_CACHE_TTL_SECONDS = 600
_blog_cache = {'data': None, 'fetched_at': 0.0}

def _load_credentials(scopes):
    """環境変数またはローカルファイルからサービスアカウント認証情報を取得"""
    service_account_json = os.getenv('GOOGLE_BLOG_SERVICE_ACCOUNT_JSON') or os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    if service_account_json:
        return service_account.Credentials.from_service_account_info(
            json.loads(service_account_json), scopes=scopes)
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        return service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=scopes)
    return None

def _build_service(api_name, api_version):
    """タイムアウト付きHTTPクライアントでGoogle APIサービスを構築"""
    if not GOOGLE_APIS_AVAILABLE:
        return None

    try:
        credentials = _load_credentials(
            scopes=['https://www.googleapis.com/auth/drive.readonly',
                   'https://www.googleapis.com/auth/documents.readonly']
        )
        if credentials is None:
            return None

        authorized_http = google_auth_httplib2.AuthorizedHttp(
            credentials, http=httplib2.Http(timeout=HTTP_TIMEOUT_SECONDS))
        return build(api_name, api_version, http=authorized_http)
    except Exception as e:
        print(f"ERROR: Failed to initialize Google {api_name} service: {e}")
        return None

def get_drive_service():
    """Google Drive APIサービスを取得"""
    return _build_service('drive', 'v3')

def get_docs_service():
    """Google Docs APIサービスを取得"""
    return _build_service('docs', 'v1')

def get_blog_documents() -> List[Dict]:
    """ブログフォルダ内のGoogleドキュメントを取得（TTLキャッシュ付き）"""
    now = time.time()
    if _blog_cache['data'] is not None and now - _blog_cache['fetched_at'] < BLOG_CACHE_TTL_SECONDS:
        return _blog_cache['data']

    drive_service = get_drive_service()
    if not drive_service:
        if _blog_cache['data'] is not None:
            return _blog_cache['data']
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

        _blog_cache['data'] = blog_posts
        _blog_cache['fetched_at'] = now
        return blog_posts

    except Exception as e:
        print(f"ERROR: Failed to get blog documents: {e}")
        # API障害時はTTL切れでも古いキャッシュを返し、サイドバー表示を維持する
        if _blog_cache['data'] is not None:
            return _blog_cache['data']
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
        
        # デバッグ: 最初の段落の構造を確認
        if content and len(content) > 0:
            first_element = content[0]
            if 'paragraph' in first_element:
                para = first_element['paragraph']
                if 'elements' in para and para['elements']:
                    elem = para['elements'][0]
                    if 'textRun' in elem:
                        text_run = elem['textRun']
                        if 'textStyle' in text_run:
                            pass
        
        # コンテンツをHTMLに変換
        html_content = convert_to_html(content)
        
        # Extract tags from content (##tag format)
        tags = extract_tags_from_content(html_content)
        
        return {
            'title': title,
            'content': html_content,
            'raw_content': content,
            'tags': tags
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
            
            # 段落が完全に空かチェック
            is_empty_paragraph = False
            if not paragraph.get('elements'):
                is_empty_paragraph = True
            else:
                # 全ての要素の内容をチェック
                all_content = ''
                for elem in paragraph.get('elements', []):
                    if 'textRun' in elem:
                        content = elem['textRun'].get('content', '')
                        all_content += content
                
                # 空白文字のみの段落も空として扱う
                if all_content.strip() == '' or all_content == '\n':
                    is_empty_paragraph = True
            
            if p_html.strip():
                html.append(p_html)
            elif is_empty_paragraph:
                # 空の段落は改行として追加
                html.append('<div style="height: 1em;"></div>')  # 段落間スペース
        elif 'table' in element:
            table = element['table']
            table_html = convert_table_to_html(table)
            if table_html.strip():
                html.append(table_html)
        elif 'sectionBreak' in element:
            # セクション区切りは改ページとして扱う
            html.append('<hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">')
    
    return '\n'.join(html)

def convert_paragraph_to_html(paragraph: Dict) -> str:
    """段落をHTMLに変換"""
    if not paragraph.get('elements'):
        return '<p></p>'
    
    paragraph_style = paragraph.get('paragraphStyle', {})
    named_style_type = paragraph_style.get('namedStyleType', '')
    
    # 箇条書き（bullet）の処理
    bullet = paragraph.get('bullet')
    is_bulleted = bool(bullet)
    bullet_prefix = ''
    
    if is_bulleted:
        # Googleドキュメントの箇条書き情報を取得
        nest_level = bullet.get('nestingLevel', 0)
        list_id = bullet.get('listId', '')
        
        # ネストレベルに応じたインデント
        indent_level = nest_level * 20  # 20pxずつインデント
        
        # 箇条書きのスタイルを確認
        glyph_format = bullet.get('textStyle', {}).get('weightedFontFamily', {}).get('fontFamily', '')
        glyph_symbol = bullet.get('textStyle', {}).get('foregroundColor', {})
        
        # 番号付きリストか点リストかを判定
        # Google Docsでは番号付きリストも 'bullet' として扱われる
        # glyphFormatやlistPropertiesで判定可能
        is_numbered = False
        
        # 簡易的な番号付きリスト判定（実際のAPIレスポンスに基づいて調整が必要）
        if 'DECIMAL' in str(bullet) or '1.' in str(bullet) or 'NUMBER' in str(bullet):
            is_numbered = True
        
        if is_numbered:
            # 番号付きリストの場合（簡易実装）
            bullet_symbol = '1.'  # 実際は動的に番号を計算すべき
        else:
            # 箇条書きの記号を設定
            bullet_symbol = '•'
            if nest_level == 1:
                bullet_symbol = '◦'  # 2番目のレベル
            elif nest_level >= 2:
                bullet_symbol = '▪'  # 3番目以降のレベル
            
        bullet_prefix = f'<span style="margin-left: {indent_level}px; display: inline-block; margin-right: 8px;">{bullet_symbol}</span>'
    
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
    
    # 段落レベルのスタイル処理
    paragraph_styles = []
    
    # 行間の処理
    if 'lineSpacing' in paragraph_style:
        line_spacing = paragraph_style['lineSpacing']
        if isinstance(line_spacing, dict) and 'magnitude' in line_spacing:
            spacing_value = line_spacing['magnitude']
            paragraph_styles.append(f'line-height: {spacing_value}')
    
    # 段落の前後スペース
    if 'spaceAbove' in paragraph_style:
        space_above = paragraph_style['spaceAbove'].get('magnitude', 0)
        if space_above > 0:
            paragraph_styles.append(f'margin-top: {space_above}px')
    
    if 'spaceBelow' in paragraph_style:
        space_below = paragraph_style['spaceBelow'].get('magnitude', 0)
        if space_below > 0:
            paragraph_styles.append(f'margin-bottom: {space_below}px')
    
    # テキスト揃えの処理
    alignment = paragraph_style.get('alignment', '')
    if alignment == 'CENTER':
        paragraph_styles.append('text-align: center')
    elif alignment == 'END':
        paragraph_styles.append('text-align: right')
    elif alignment == 'JUSTIFY':
        paragraph_styles.append('text-align: justify')
    
    # テキスト要素を処理
    text_parts = []
    for element in paragraph['elements']:
        if 'textRun' in element:
            text_run = element['textRun']
            text = text_run.get('content', '')
            text_style = text_run.get('textStyle', {})
            
            # デバッグ: テキストの内容をログ出力
            if '\n' in text or '\r' in text or '\u000b' in text:
                pass
            
            # スタイル適用
            span_styles = []
            
            if text_style.get('bold'):
                text = f'<strong>{text}</strong>'
            if text_style.get('italic'):
                text = f'<em>{text}</em>'
            if text_style.get('underline'):
                text = f'<u>{text}</u>'
                
            # 背景色の処理
            if 'backgroundColor' in text_style:
                bg_color = text_style['backgroundColor'].get('color', {})
                if 'rgbColor' in bg_color:
                    rgb = bg_color['rgbColor']
                    r = int(rgb.get('red', 0) * 255)
                    g = int(rgb.get('green', 0) * 255) 
                    b = int(rgb.get('blue', 0) * 255)
                    span_styles.append(f'background-color: rgb({r}, {g}, {b})')
                    
            # 文字色の処理
            if 'foregroundColor' in text_style:
                fg_color = text_style['foregroundColor'].get('color', {})
                if 'rgbColor' in fg_color:
                    rgb = fg_color['rgbColor']
                    r = int(rgb.get('red', 0) * 255)
                    g = int(rgb.get('green', 0) * 255)
                    b = int(rgb.get('blue', 0) * 255)
                    span_styles.append(f'color: rgb({r}, {g}, {b})')
                    
            # フォントサイズの処理
            if 'fontSize' in text_style:
                font_size = text_style['fontSize'].get('magnitude', 10)
                span_styles.append(f'font-size: {font_size}px')
                
            # フォントファミリーの処理
            font_family = None
            if 'weightedFontFamily' in text_style:
                font_family = text_style['weightedFontFamily'].get('fontFamily', '')
            elif 'fontFamily' in text_style:
                font_family = text_style['fontFamily']
                
            if font_family:
                # Google Fontsの場合の対応
                if font_family in ['Arial', 'Times New Roman', 'Courier New', 'Helvetica', 'Georgia', 'Verdana', 'Roboto', 'Open Sans']:
                    span_styles.append(f'font-family: "{font_family}", sans-serif')
                elif font_family in ['Times', 'serif']:
                    span_styles.append(f'font-family: "{font_family}", serif')
                elif 'Noto' in font_family or 'Gothic' in font_family or 'Mincho' in font_family or 'Hiragino' in font_family:
                    span_styles.append(f'font-family: "{font_family}", "Hiragino Sans", "Meiryo", sans-serif')
                elif 'monospace' in font_family.lower() or 'courier' in font_family.lower() or 'mono' in font_family.lower():
                    span_styles.append(f'font-family: "{font_family}", "Courier New", monospace')
                else:
                    # その他のフォントも適用
                    span_styles.append(f'font-family: "{font_family}", sans-serif')
            
            # 改行の処理（改行文字を<br>に変換）
            # Google Docsでは改行は\n以外にも\u000bで表現される場合がある
            text = text.replace('\n', '<br>')
            text = text.replace('\u000b', '<br>')  # 垂直タブ文字
            text = text.replace('\r', '<br>')      # キャリッジリターン
            
            # 連続する<br>を整理
            text = re.sub(r'(<br>\s*){2,}', '<br><br>', text)
            
            # スタイルをspanで適用
            if span_styles:
                style_str = '; '.join(span_styles)
                text = f'<span style="{style_str}">{text}</span>'
            
            # リンクの処理
            if 'link' in text_style:
                url = text_style['link'].get('url', '')
                if url:
                    text = f'<a href="{url}" target="_blank">{text}</a>'
            
            text_parts.append(text)
            
        elif 'inlineObjectElement' in element:
            # 画像やその他のインラインオブジェクトを処理
            inline_obj = element['inlineObjectElement']
            object_id = inline_obj.get('inlineObjectId', '')
            
            # 画像の場合の処理（プレースホルダーとして表示）
            if object_id:
                # Google Docs APIでは画像の実際のURLを取得するのが複雑
                # ここでは画像のプレースホルダーを表示
                image_html = f'''<div style="margin: 16px 0; padding: 20px; border: 2px dashed #ccc; text-align: center; background-color: #f9f9f9; border-radius: 8px;">
                    <p style="margin: 0; color: #666; font-size: 14px;">
                        📷 画像が挿入されています<br>
                        <small style="color: #999;">(ID: {object_id})</small>
                    </p>
                </div>'''
                text_parts.append(image_html)
    
    content_text = ''.join(text_parts).strip()
    if not content_text:
        return ''
    
    # 箇条書きの場合は bullet_prefix を追加
    if bullet_prefix:
        content_text = bullet_prefix + content_text
    
    # 段落スタイルを適用
    if paragraph_styles:
        style_str = '; '.join(paragraph_styles)
        return f'<{tag} style="{style_str}">{content_text}</{tag}>'
    else:
        return f'<{tag}>{content_text}</{tag}>'

def convert_table_to_html(table: Dict) -> str:
    """Google Docsの表をHTMLテーブルに変換"""
    if not table.get('tableRows'):
        return ''
    
    html = ['<table style="border-collapse: collapse; width: 100%; margin: 16px 0;">']
    
    for i, row in enumerate(table['tableRows']):
        html.append('<tr>')
        
        for j, cell in enumerate(row.get('tableCells', [])):
            # セルのスタイルを取得
            cell_style = cell.get('tableCellStyle', {})
            cell_styles = []
            
            # 背景色
            if 'backgroundColor' in cell_style:
                bg_color = cell_style['backgroundColor'].get('color', {})
                if 'rgbColor' in bg_color:
                    rgb = bg_color['rgbColor']
                    r = int(rgb.get('red', 0) * 255)
                    g = int(rgb.get('green', 0) * 255)
                    b = int(rgb.get('blue', 0) * 255)
                    cell_styles.append(f'background-color: rgb({r}, {g}, {b})')
            
            # 境界線
            cell_styles.extend([
                'border: 1px solid #ddd',
                'padding: 8px',
                'vertical-align: top'
            ])
            
            # セルの内容を変換
            cell_content = []
            for content_element in cell.get('content', []):
                if 'paragraph' in content_element:
                    para_html = convert_paragraph_to_html(content_element['paragraph'])
                    # テーブル内では<p>タグを除去してシンプルにする
                    if para_html.startswith('<p>') and para_html.endswith('</p>'):
                        para_html = para_html[3:-4]
                    elif para_html.startswith('<h'):
                        # 見出しタグもシンプルにする
                        para_html = re.sub(r'<h[1-6]>(.*?)</h[1-6]>', r'<strong>\1</strong>', para_html)
                    cell_content.append(para_html)
            
            cell_text = '<br>'.join(cell_content) if cell_content else '&nbsp;'
            style_str = '; '.join(cell_styles) if cell_styles else ''
            
            # ヘッダー行の判定（最初の行をヘッダーとして扱う）
            tag = 'th' if i == 0 else 'td'
            if tag == 'th':
                cell_styles.append('font-weight: bold')
                style_str = '; '.join(cell_styles)
            
            html.append(f'<{tag} style="{style_str}">{cell_text}</{tag}>')
        
        html.append('</tr>')
    
    html.append('</table>')
    return '\n'.join(html)

def extract_tags_from_content(html_content: str) -> List[str]:
    """HTMLコンテンツから##tag形式のタグを抽出"""
    if not html_content:
        return []
    
    try:
        # HTMLタグを除去してプレーンテキストを取得
        text_content = re.sub(r'<[^>]+>', '', html_content)
        
        # 最後の5行程度を確認
        lines = text_content.strip().split('\n')
        last_lines = lines[-5:] if len(lines) >= 5 else lines
        
        tags = []
        for line in last_lines:
            line = line.strip()
            # ##tag形式のタグを検索
            tag_matches = re.findall(r'##([a-zA-Z0-9_\-]+)', line)
            tags.extend(tag_matches)
        
        # 重複を除去して返す
        return list(set(tags))
        
    except Exception as e:
        print(f"Tag extraction error: {e}")
        return []

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

def get_onomatopoeia_image_url(filename: str) -> Optional[str]:
    """オノマトペ画像のGoogle Drive公開URLを取得"""
    if not filename or not GOOGLE_APIS_AVAILABLE:
        return None
    
    try:
        drive_service = get_drive_service()
        if not drive_service:
            return None
        
        # オノマトペ画像フォルダ内のファイルを検索
        results = drive_service.files().list(
            q=f"name='{filename}' and parents in '{ONOMATOPOEIA_IMAGES_FOLDER_ID}' and trashed=false",
            fields='files(id, name, webViewLink)'
        ).execute()
        
        files = results.get('files', [])
        if files:
            file_id = files[0]['id']
            # 直接表示用のURLを生成（Google Drive画像の直接リンク）
            return f"https://drive.google.com/uc?id={file_id}"
        else:
            print(f"オノマトペ画像が見つかりません: {filename}")
            return None
            
    except Exception as e:
        print(f"オノマトペ画像URL取得エラー: {e}")
        return None