import openai
import os
from error_handler import safe_openai_request

# GPTを使用してふりがなを生成
FURIGANA_AVAILABLE = True
print("DEBUG: Using GPT-based furigana generation")

def text_to_ruby_html(text):
    """
    Convert Japanese text to HTML with <ruby> tags using OpenAI GPT for furigana generation.
    """
    print(f"DEBUG: GPT text_to_ruby_html called with: '{text}'")
    
    if not text or not text.strip():
        print("DEBUG: Empty text, returning as is")
        return text
    
    try:
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
        
        if isinstance(result, dict) and "error" in result:
            print(f"DEBUG: GPT furigana error: {result['error']}")
            return text  # エラーの場合は元のテキストを返す
            
        print(f"DEBUG: GPT furigana result: {result}")
        return result
        
    except Exception as e:
        print(f"DEBUG: Exception in GPT text_to_ruby_html: {e}")
        import traceback
        traceback.print_exc()
        return text 