import openai
import os
import time
from error_handler import safe_openai_request

# GPTを使用してふりがなを生成
FURIGANA_AVAILABLE = True
print("DEBUG: Using GPT-based furigana generation")

# キャッシュとレート制限対策
_furigana_cache = {}
_last_request_time = 0

def text_to_ruby_html(text):
    """
    Convert Japanese text to HTML with <ruby> tags using OpenAI GPT for furigana generation.
    """
    global _last_request_time
    print(f"DEBUG: GPT text_to_ruby_html called with: '{text}'")
    
    if not text or not text.strip():
        print("DEBUG: Empty text, returning as is")
        return text
    
    # キャッシュチェック
    if text in _furigana_cache:
        print("DEBUG: Using cached furigana result")
        return _furigana_cache[text]
    
    try:
        # レート制限対策：前回のリクエストから3秒待つ
        current_time = time.time()
        time_since_last = current_time - _last_request_time
        if time_since_last < 3:
            sleep_time = 3 - time_since_last
            print(f"DEBUG: Rate limiting - sleeping for {sleep_time:.1f} seconds")
            time.sleep(sleep_time)
        # GPTプロンプト
        prompt = f"""
日本語の文章にふりがな（ひらがな）を付けて、HTML ruby形式で出力してください。
漢字が含まれる単語のみにrubyタグを付け、ひらがなやカタカナはそのまま残してください。

入力: {text}

出力形式例: <ruby>子ども<rt>こども</rt></ruby>のころ、よく<ruby>公園<rt>こうえん</rt></ruby>で<ruby>遊<rt>あそ</rt></ruby>びました。

重要な注意:
- 漢字を含む単語のみrubyタグを付ける
- ひらがな、カタカナ、記号はそのまま出力
- rubyタグの中身は必ずひらがなにする
- 余計な説明は一切不要で、変換結果のみ出力

出力:"""

        def make_furigana_request():
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # より安価なモデルを使用
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 一貫性を保つため低く設定
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        
        print("DEBUG: Calling GPT for furigana generation...")
        result = safe_openai_request(make_furigana_request)
        _last_request_time = time.time()  # リクエスト時間を記録
        
        if isinstance(result, dict) and "error" in result:
            print(f"DEBUG: GPT furigana error: {result['error']}")
            return text  # エラーの場合は元のテキストを返す
            
        print(f"DEBUG: GPT furigana result: {result}")
        
        # 結果をキャッシュに保存
        _furigana_cache[text] = result
        
        # キャッシュサイズ制限（メモリ使用量を抑制）
        if len(_furigana_cache) > 100:
            # 古いエントリを削除（簡易的にキャッシュをクリア）
            _furigana_cache.clear()
            print("DEBUG: Furigana cache cleared due to size limit")
        
        return result
        
    except Exception as e:
        print(f"DEBUG: Exception in GPT text_to_ruby_html: {e}")
        import traceback
        traceback.print_exc()
        return text 