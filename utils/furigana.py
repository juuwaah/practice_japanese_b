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
        # GPTプロンプト（よりシンプルで明確に）
        prompt = f"""以下の日本語文にふりがなを付けて、HTML ruby形式で返してください。

文: {text}

ルール:
1. 漢字にのみ<ruby>漢字<rt>ひらがな</rt></ruby>形式を適用
2. ひらがな・カタカナ・記号は変更しない
3. 変換結果のみ返す（説明不要）

例:
入力: 彼は学校で勉強した。
出力: <ruby>彼<rt>かれ</rt></ruby>は<ruby>学校<rt>がっこう</rt></ruby>で<ruby>勉強<rt>べんきょう</rt></ruby>した。

出力:"""

        def make_furigana_request():
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o",  # より高性能なモデルを使用
                messages=[
                    {"role": "system", "content": "あなたは日本語の漢字にひらがなの読みを付ける専門家です。正確なふりがなをHTML ruby形式で出力してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # 完全に一貫性を保つ
                max_tokens=1000
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
            # 「出力:」などの余計な文字を除去
            if result.startswith("出力:"):
                result = result[3:].strip()
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