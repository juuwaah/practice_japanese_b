import openai
import os
import time
from error_handler import safe_openai_request

# GPTを使用してひらがな読みを生成
FURIGANA_AVAILABLE = True

# キャッシュとレート制限対策
_furigana_cache = {}  # Cleared for new prompt
_last_request_time = 0

def text_to_ruby_html(text):
    """
    Convert Japanese text with hiragana reading in parentheses using OpenAI GPT.
    Format: 元の文（ひらがなのよみ）
    """
    global _last_request_time
    
    if not text or not text.strip():
        return text
    
    # キャッシュチェック
    if text in _furigana_cache:
        return _furigana_cache[text]
    
    try:
        # レート制限対策：前回のリクエストから3秒待つ
        current_time = time.time()
        time_since_last = current_time - _last_request_time
        if time_since_last < 3:
            sleep_time = 3 - time_since_last
            time.sleep(sleep_time)
            
        # 最もシンプルなプロンプト
        prompt = f"""この日本語文の後ろに全文のひらがな読みを（）で追加してください:

{text}

例: 彼は今勉強しているところです → 彼は今勉強しているところです（かれはいまべんきょうしているところです）

結果:"""

        def make_furigana_request():
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        
        try:
            result = make_furigana_request()
        except Exception as e:
            return text
        
        _last_request_time = time.time()
        
        # 結果を清浄化
        if result:
            result = result.strip()
            # 余計なプレフィックスを削除
            prefixes_to_remove = ["結果:", "出力:", "変換結果:", "答え:"]
            for prefix in prefixes_to_remove:
                if result.startswith(prefix):
                    result = result[len(prefix):].strip()
                    break
        
        # キャッシュに保存
        if result:
            _furigana_cache[text] = result
        
        # キャッシュサイズ制限
        if len(_furigana_cache) > 100:
            _furigana_cache.clear()
        
        return result if result else text
        
    except Exception as e:
        return text