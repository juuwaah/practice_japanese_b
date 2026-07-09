# routes/vocab.py
import os
import pandas as pd
import random
import openai
import json
from flask import Blueprint, render_template, request, session
import re
from google_sheets_helper import load_vocab_data_from_sheets

vocab_bp = Blueprint("vocab", __name__, url_prefix="/vocab")

def get_main_reading(word):
    if isinstance(word, str):
        return word.split('・')[0]
    return word

def generate_vocab_quiz(level):
    # 1. Load data from Google Sheets for the selected level
    sheet_id = os.getenv('GOOGLE_SHEETS_ID')
    df = load_vocab_data_from_sheets(sheet_id, level)
    if df is None:
        # Fallback to Excel if Google Sheets fails
        try:
            df = pd.read_excel("database/JLPT vocabulary.xlsx", sheet_name=level)
            df = df.dropna(subset=["Kanji", "Word", "Meaning", "Type"])
        except Exception as e:
            print(f"Excel fallback also failed: {e}")
            return None
    else:
        df = df.dropna(subset=["Kanji", "Word", "Meaning", "Type"])
    # 2. Randomly select correct answer and 3 distractors of the same Type
    row = df.sample(1).iloc[0]
    meaning = row["Meaning"]
    word = row["Word"]
    kanji = row["Kanji"]
    word_type = row["Type"]
    # Get 3 distractors (different words, same Type)
    same_type_df = df[(df["Word"] != word) & (df["Type"] == word_type)]
    if len(same_type_df) >= 3:
        distractor_rows = same_type_df.sample(3)
    else:
        # If not enough same type, get remaining from different types
        distractor_rows = same_type_df
        remaining_needed = 3 - len(same_type_df)
        if remaining_needed > 0:
            other_rows = df[df["Word"] != word].sample(remaining_needed)
            distractor_rows = pd.concat([distractor_rows, other_rows])
    
    distractors = distractor_rows[["Word", "Kanji"]].values.tolist()
    # options: [(word, kanji), ...]
    options = [[word, kanji]] + distractors
    random.shuffle(options)
    # ひらがな（漢字）の形に変換 - 辞書形のまま表示
    options_display = [f"{w}（{k}）" if pd.notna(k) and str(k).strip() else f"{w}" for w, k in options]
    # 4. Use GPT to generate a Japanese sentence with the blank already in place
    prompt = f"""
あなたは日本語教師です。以下の単語を使って、語彙クイズの自然な日本語の文を1つ作ってください。
- 単語: {kanji}（{word}）
- この単語は品詞グループ「{word_type}」です。
- 文はJLPT {level}レベルの学習者向けに簡単にしてください。
- 単語の該当箇所は必ず '＿＿' で空欄にしてください。
- 【重要】空欄には単語の辞書形（原形）をそのまま入れてください。動詞は活用させず、形容詞も語尾変化させずに使ってください。
- 動詞なら「〜する」「〜た」などの活用形ではなく、辞書形のまま使える文脈にしてください。
- 形容詞なら「〜い」「〜な」の語尾変化をさせずに使える文脈にしてください。
- 名詞の場合はそのまま使ってください。
- 単語は文中で1回だけ使い、他の語と混同しないようにしてください。
- 空欄以外の場所に正解の単語やその一部が絶対に現れないようにしてください。
- 文中で使う漢字は必ず「{level}までに習う漢字」だけにしてください。それ以外の難しい漢字はひらがなで書いてください。
- 選択肢や問題文には「・」や不自然な記号を絶対に含めないでください。
- 出力は日本語の例文1文のみ。他の情報や選択肢リスト、ヒントなどは絶対に含めないでください。
"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # 5. 生成文のバリデーション: 答えやその一部が空欄以外に現れていないか、記号が含まれていないか
    max_attempts = 5
    for _ in range(max_attempts):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        quiz_sentence = response.choices[0].message.content
        if isinstance(quiz_sentence, str):
            quiz_sentence = quiz_sentence.strip().replace("\n", "")
        else:
            quiz_sentence = ""
        # 空欄部分以外に正解語やその一部が含まれていないかチェック
        blank_pattern = r'＿＿'
        # 正解語の分割（例：「運転する」→["運転", "する"]）
        answer_parts = re.findall(r'[\u4e00-\u9fff]+|[ぁ-んァ-ンー]+|[a-zA-Z]+', word)
        # 空欄以外の部分を抽出
        sentence_wo_blank = re.sub(blank_pattern, '', quiz_sentence)
        # どれかのパーツが空欄以外に現れていればNG
        has_answer_part = any(part and part in sentence_wo_blank for part in answer_parts)
        # 「・」や不自然な記号が含まれていればNG
        has_bad_symbol = '・' in quiz_sentence
        if not has_answer_part and not has_bad_symbol:
            break
    else:
        # 何度やってもダメなら最後の生成文を使う
        pass
    # 正解も辞書形のまま表示
    answer_display = f"{word}（{kanji}）" if pd.notna(kanji) and str(kanji).strip() else word
    return {
        "question": f"Q: {meaning}\n{quiz_sentence}",
        "options": options_display,
        "answer": answer_display,
        "kanji": kanji,
        "word": word,
        "meaning": meaning,
        "sentence": quiz_sentence
    }

def safe_strip(val):
    return val.strip() if isinstance(val, str) else ""

def generate_feedback_and_examples(word, kanji, meaning, level, quiz_sentence, options):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = (
        f"""
You are a Japanese language teacher. The following is a JLPT {level} vocabulary quiz.
- The quiz sentence is: {quiz_sentence}
- The correct answer is: {word} ({kanji})
- The English meaning is: {meaning}
- The options were: {', '.join(options)}

Please:
1. Provide a full, natural English translation of the original Japanese quiz sentence (do NOT include the blank or any placeholder; translate as if the correct answer is filled in).
2. For each of the following four options, provide its English meaning:
- {options[0]}
- {options[1]}
- {options[2]}
- {options[3]}

Format:
Translation: <Full English translation of the original Japanese sentence>
Options:
- {options[0]}: <English meaning>
- {options[1]}: <English meaning>
- {options[2]}: <English meaning>
- {options[3]}: <English meaning>
"""
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    content = response.choices[0].message.content
    if not isinstance(content, str):
        return "", []
    lines = safe_strip(content).split('\n')
    translation = ""
    option_translations = []
    in_options = False
    for line in lines:
        lstr = safe_strip(line)
        if lstr.startswith("Translation:"):
            translation = safe_strip(lstr.replace("Translation:", ""))
        if lstr.startswith("Options:"):
            in_options = True
            continue
        if in_options and lstr.startswith("-"):
            option_translations.append(lstr)
    explanation = translation + ("\n" if translation and option_translations else "") + "\n".join(option_translations)
    return explanation, []

@vocab_bp.route("/", methods=["GET", "POST"])
def vocab_index():
    level = request.form.get("level", "N5")
    selected_option = None
    result = ""
    quiz = None
    explanation = None
    examples = None

    if request.method == "POST":
        if request.form.get("action") == "generate":
            try:
                quiz = generate_vocab_quiz(level)
                # Store quiz in session for retro template compatibility
                session['current_quiz'] = quiz
            except Exception as e:
                print(f"Error generating quiz: {e}")  # Debug log
                quiz = None
                session['current_quiz'] = None
        elif request.form.get("action") in ["submit", "answer"]:
            # Get quiz from session or reconstruct from form data
            quiz = session.get('current_quiz')
            if not quiz:
                # Fallback: reconstruct from form data (modern template)
                options_json = request.form.get("options", "[]")
                try:
                    options = json.loads(options_json)
                except Exception:
                    options = []
                quiz = {
                    "question": request.form.get("question", ""),
                    "options": options,
                    "answer": request.form.get("answer", ""),
                    "kanji": request.form.get("kanji", ""),
                    "word": request.form.get("word", ""),
                    "meaning": request.form.get("meaning", ""),
                    "sentence": request.form.get("sentence", "")
                }
            
            selected_option = request.form.get("user_answer") or request.form.get("answer")
            
            if selected_option == quiz["answer"]:
                result = "Correct!"
            else:
                result = f"Incorrect. The correct answer was: {quiz['answer']}"
                # Generate feedback and examples for incorrect answer
                explanation, examples = generate_feedback_and_examples(
                    quiz["word"], quiz["kanji"], quiz["meaning"], level, quiz["question"], quiz["options"]
                )
    else:
        # GETリクエスト時は既存のクイズがあればそれを使用、なければ生成
        quiz = session.get('current_quiz')
        if not quiz:
            try:
                quiz = generate_vocab_quiz(level)
                # Store quiz in session for retro template compatibility
                session['current_quiz'] = quiz
            except Exception as e:
                print(f"GET request - Error generating quiz: {e}")  # Debug log
                quiz = None
                session['current_quiz'] = None
        else:
            pass
        
    if not quiz or not isinstance(quiz, dict):
        quiz = {
            "question": None,
            "options": [],
            "answer": None
        }

    # Prepare question data for template compatibility
    question_data = None
    if quiz and quiz.get("question"):
        # For retro template - create question object with required properties
        question_data = {
            'kanji': quiz.get('kanji', ''),
            'word': quiz.get('word', ''),
            'id': 1  # Simple ID for form compatibility
        }
    
    return render_template(
        "vocab.html",
        level=level,
        question=quiz["question"] if quiz else None,  # For modern template string format
        question_data=question_data,  # For retro template object format
        options=quiz["options"] if quiz else [],
        answer=quiz["answer"] if quiz else None,
        explanation=explanation,
        examples=examples,
        selected=selected_option,
        result=result
    )