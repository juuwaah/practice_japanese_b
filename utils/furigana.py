import openai
import os
import time
from error_handler import safe_openai_request

# GPTを使用してひらがな読みを生成
FURIGANA_AVAILABLE = True
print("DEBUG: Using GPT-based hiragana reading generation")

# キャッシュとレート制限対策
_furigana_cache = {}
_last_request_time = 0

def text_to_ruby_html(text):
    """
    Convert Japanese text with hiragana reading in parentheses using OpenAI GPT.
    Format: 元の文（ひらがなのよみ）
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
        # GPTプロンプト（括弧形式でシンプルに）
        prompt = f"""以下の日本語文の後に、全体をひらがなに直したものを括弧内に追加してください。

文: {text}

形式: 元の文（ひらがなの読み）

例:
入力: 彼は学校で勉強した。
出力: 彼は学校で勉強した。（かれはがっこうでべんきょうした。）

変換結果のみ返してください:"""

        def make_furigana_request():
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # シンプルなタスクなので安価なモデル
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 一貫性を保つ
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        
        print("DEBUG: Calling GPT for furigana generation...")
        result = safe_openai_request(make_furigana_request)
        _last_request_time = time.time()  # リクエスト時間を記録
        
        if isinstance(result, dict) and "error" in result:
            print(f"DEBUG: GPT furigana error: {result['error']}")
            return text  # エラーの場合は元のテキストを返す
            
        print(f"DEBUG: GPT raw result: {result}")
        
        # 結果を清浄化（余計な文字や改行を除去）
        if result:
            # 先頭・末尾の空白や改行を除去
            result = result.strip()
            # 「出力:」や「変換結果:」などの余計な文字を除去
            prefixes_to_remove = ["出力:", "変換結果:", "結果:", "答え:"]
            for prefix in prefixes_to_remove:
                if result.startswith(prefix):
                    result = result[len(prefix):].strip()
                    break
            # バッククォートで囲まれている場合は除去
            if result.startswith("```") and result.endswith("```"):
                result = result[3:-3].strip()
            if result.startswith("`") and result.endswith("`"):
                result = result[1:-1].strip()
        
        print(f"DEBUG: GPT cleaned result: {result}")
        
        # 結果をキャッシュに保存
        if result:
            _furigana_cache[text] = result
        
        # キャッシュサイズ制限（メモリ使用量を抑制）
        if len(_furigana_cache) > 100:
            # 古いエントリを削除（簡易的にキャッシュをクリア）
            _furigana_cache.clear()
            print("DEBUG: Furigana cache cleared due to size limit")
        
        return result if result else text
        
    except Exception as e:
        print(f"DEBUG: Exception in GPT text_to_ruby_html: {e}")
        import traceback
        traceback.print_exc()
        return text 