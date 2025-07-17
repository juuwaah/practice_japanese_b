from flask import Blueprint, render_template, request
import openai
import os
import re
import json
from dotenv import load_dotenv
import pandas as pd
import random
# from utils.furigana import text_to_ruby_html  # 削除

grammar_bp = Blueprint('grammar', __name__, url_prefix="/grammar")
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 文法構文リスト（Excelから読み込み）
grammar_dict = {}

def load_grammar():
    global grammar_dict
    df_path = "database/JLPT grammar.xlsx"
    for level in ["N5", "N4", "N3", "N2", "N1"]:
        df = pd.read_excel(df_path, sheet_name=level)
        grammar_list = df["Grammar"].dropna().tolist()
        grammar_dict[level] = grammar_list

load_grammar()

@grammar_bp.route("/", methods=["GET", "POST"])
def grammar_index():
    original = ""
    translation = ""
    grammar = None
    meaning = None
    model_answer = []
    feedback = ""
    message = ""
    casual_answer = ""
    # original_ruby = ""
    # model_answer_ruby = []
    # casual_answer_ruby = ""

    level = "N5"
    direction = "en-ja"

    if request.method == "POST":
        action = request.form.get("action")
        level = request.form.get("level", level)
        direction = request.form.get("direction", direction)
        translation = request.form.get("translation", "")

        try:
            if action == "generate":
                original = generate_example_sentence(level, direction)
                translation = ""
            elif action == "score":
                original = request.form.get("original", "")
                if not original or original.lower() == "none":
                    raise ValueError("Please generate an example sentence first.")
                result = score_translation(original, translation, direction, level)
                grammar = result.get("grammar")
                meaning = result.get("meaning")
                model_answer = result.get("model_answer", [])
                feedback = result.get("feedback", "")
                casual_answer = result.get("casual_answer", "")
        except Exception as e:
            message = f"Error: {str(e)}"

    else:
        # GETリクエスト時は必ず文を生成
        original = generate_example_sentence(level, direction)
        translation = ""

    # ルビ付与処理 削除

    return render_template("grammar.html",
        directions={"en-ja": "English → Japanese", "ja-en": "Japanese → English"},
        original=original,
        translation=translation,
        grammar=grammar,
        meaning=meaning,
        model_answer=model_answer,
        feedback=feedback,
        message=message,
        direction=direction,
        level=level,
        casual_answer=casual_answer
        # original_ruby=original_ruby,
        # model_answer_ruby=model_answer_ruby,
        # casual_answer_ruby=casual_answer_ruby
    )

def generate_example_sentence(level, direction):
    grammar_list = grammar_dict.get(level, [])
    if not grammar_list:
        raise ValueError(f"No grammar for level {level}")
    selected_grammar = random.choice(grammar_list)

    if direction == "en-ja":
        # 英語→日本語: 英語文のみを生成
        prompt = f'''
Create one short English sentence that could naturally be translated into Japanese using the grammar pattern "{selected_grammar}" (JLPT {level}).
- Do not include any Japanese in the sentence.
- Output only the English sentence.
'''
    else:
        # 日本語→英語: 日本語文のみを生成
        prompt = f'''
「{selected_grammar}」（JLPT {level}）という文法パターンを使った短い自然な日本語の例文を1つ作ってください。
- 英語や説明は含めず、日本語の文のみを出力してください。
- 文中で使う漢字は必ず「{level}までに習う漢字」だけにしてください。それ以外の難しい漢字はひらがなで書いてください。
'''

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return re.split(r'→|:|\n', response.choices[0].message.content.strip())[0]

def score_translation(original, student_translation, direction, level):
    prompt = f"""
Original sentence: {original}
Student translation: {student_translation}
Translation direction: {"English → Japanese" if direction == "en-ja" else "Japanese → English"}
JLPT Level: {level}

Please evaluate and return a JSON object like this:
{{
  "grammar": 1-3,
  "meaning": 1-3,
  "model_answer": ["...", "..."],
  "casual_answer": "...",
  "feedback": "Brief advice in English. Consider that the messages are for students, so use \"you\", not \"the student\"."
}}

For scoring ("grammar" and "meaning"), do NOT consider kanji usage at all. Do not penalize or reward for using or not using kanji. Only evaluate the grammar and meaning.
For "model_answer", provide two natural and correct translations as model answers, using kanji and vocabulary appropriate for JLPT {level} (e.g., for N5 use simple kanji and more hiragana, for N1 you can use advanced kanji).
For "casual_answer", rewrite the original sentence in very casual, relaxed, everyday Japanese as if between friends, avoiding polite or formal expressions. Use a natural, conversational tone. Follow these instructions and examples:

---
以下の文章を、友達同士の砕けた日常会話っぽい自然な日本語に言い換えてください。
丁寧語やかしこまった表現は避け、リラックスした口調でお願いします。

例：
「これは私が生まれた街ですが、特に愛着は感じません。」
→「ここ、生まれた街ではあるんだけど、正直あんまり愛着とかはないかな。」

「あまり難しい言葉を使わないでください」
→「あんまりむずかしい言葉は使わないでほしいな〜。」

「これは封建制度の限界の代表例です」
→「これ、いわゆる封建制度の限界ってやつの典型だね。」
---

Respond only with JSON.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    raw = response.choices[0].message.content
    json_text = extract_json(raw)
    return json.loads(json_text)

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("Failed to extract JSON.")