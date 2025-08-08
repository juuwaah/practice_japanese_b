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
    import re
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
    # 2. Extract allowed kanji for this level
    allowed_kanji = set(''.join(df["Kanji"].dropna().astype(str).tolist()))
    allowed_kanji_str = ''.join(sorted(allowed_kanji))
    # 3. Randomly select correct answer and 3 distractors of the same Type
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

def generate_level_appropriate_question(kanji, hiragana_list, meaning, level):
    """GPTを使ってレベルに応じた問題文を生成"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # レベルに応じた問題テンプレート
    templates_by_level = {
        'N5': [
            "なつは＿＿＿＿を飲んだ方がいいです。",
            "この＿＿＿＿はとても美味しいです。",
            "＿＿＿＿に行って買い物をします。",
            "＿＿＿＿を見て勉強します。",
            "＿＿＿＿が大好きです。",
            "＿＿＿＿で友達と会います。",
            "＿＿＿＿を食べて元気になります。",
            "＿＿＿＿があります。"
        ],
        'N4': [
            "＿＿＿＿に向かって計画を立てます。",
            "＿＿＿＿を調べて詳しく知ります。",
            "＿＿＿＿に参加して楽しみます。",
            "＿＿＿＿を確認して安心します。",
            "＿＿＿＿を準備して待ちます。",
            "＿＿＿＿を説明して理解してもらいます。",
            "＿＿＿＿を選んで買います。",
            "＿＿＿＿を決めて進めます。"
        ],
        'N3': [
            "＿＿＿＿について話し合って決めます。",
            "＿＿＿＿を調査して問題を解決します。",
            "＿＿＿＿を改善して良くします。",
            "＿＿＿＿を検討して最適な方法を選びます。",
            "＿＿＿＿を実現して目標を達成します。",
            "＿＿＿＿を解決して安心します。",
            "＿＿＿＿を分析して結果を出します。",
            "＿＿＿＿を評価して良し悪しを判断します。"
        ],
        'N2': [
            "＿＿＿＿を検証して正しさを確認します。",
            "＿＿＿＿を最適化して効率を上げます。",
            "＿＿＿＿を統合して一つのシステムにします。",
            "＿＿＿＿を構築して新しい仕組みを作ります。",
            "＿＿＿＿を確立して制度を整えます。",
            "＿＿＿＿を促進して発展を進めます。",
            "＿＿＿＿を維持して状態を保ちます。",
            "＿＿＿＿を向上させて能力を高めます。"
        ],
        'N1': [
            "＿＿＿＿を革新して新しい技術を生み出します。",
            "＿＿＿＿を確立して理論を完成させます。",
            "＿＿＿＿を推進して政策を実行します。",
            "＿＿＿＿を実現して理想を達成します。",
            "＿＿＿＿を構築して関係を深めます。",
            "＿＿＿＿を確立して地位を固めます。",
            "＿＿＿＿を促進して発展を加速させます。",
            "＿＿＿＿を維持して安定を保ちます。"
        ]
    }
    
    templates = templates_by_level.get(level, templates_by_level['N5'])
    template = random.choice(templates)
    
    prompt = f"""
Create a Japanese vocabulary quiz question for JLPT {level} level learners using the following word:

Kanji: {kanji}
Reading options: {hiragana_list}
Meaning: {meaning}

【Requirements】
- Create a natural sentence using the template: {template}
- Choose the most appropriate reading for the context
- The sentence should be suitable for JLPT {level} level
- Use hiragana for the target word in the sentence
- Make sure the sentence makes sense and is grammatically correct

【Output format】
Sentence: [Complete sentence with the target word in hiragana]
Correct reading: [The reading used in the sentence]

Return only the output.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        print('GPT OUTPUT:', result)
        
        # 結果を解析
        lines = result.split('\n')
        question = ""
        correct_reading = ""
        
        for line in lines:
            if line.startswith('Sentence:'):
                question = line.replace('Sentence:', '').strip()
            elif line.startswith('Correct reading:'):
                correct_reading = line.replace('Correct reading:', '').strip()
        
        # デフォルト値の設定
        if not question:
            question = template.replace("＿＿＿＿", hiragana_list.split('・')[0] if '・' in hiragana_list else hiragana_list)
        if not correct_reading:
            correct_reading = hiragana_list.split('・')[0] if '・' in hiragana_list else hiragana_list
        
        return question, correct_reading
        
    except Exception as e:
        # GPTが失敗した場合のフォールバック
        print(f"GPT error: {e}")
        fallback_reading = hiragana_list.split('・')[0] if '・' in hiragana_list else hiragana_list
        fallback_question = template.replace("＿＿＿＿", fallback_reading)
        return fallback_question, fallback_reading

def generate_english_feedback(kanji, reading, meaning, level):
    """英語でのフィードバックを生成"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""
Create feedback for a Japanese vocabulary quiz answer in English.

Word: {kanji} ({reading})
Meaning: {meaning}
Level: JLPT {level}

【Requirements】
- Explain why this answer is correct
- Explain why other options are incorrect
- Keep it concise and educational
- Use simple English suitable for language learners
- When showing the correct answer, display it as: [reading] ([kanji of the word])

【Output format】
Correct answer: [reading] ([kanji])
Explanation: [Why this is correct and others are wrong]

Return only the output.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        return result
        
    except Exception as e:
        # GPTが失敗した場合のフォールバック
        print(f"GPT feedback error: {e}")
        return f"Correct answer: {reading} ({kanji})\nExplanation: {reading} means '{meaning}' and fits naturally in this context. Other options are grammatically correct but don't match the meaning of this sentence."

def generate_english_example_sentences(kanji, reading, meaning, level):
    """英語での例文を生成"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""
Create 2 example sentences using this Japanese word for JLPT {level} level learners.

Word: {kanji} ({reading})
Meaning: {meaning}

【Requirements】
- Create 2 different example sentences
- Use hiragana for the target word
- Make sentences simple and suitable for JLPT {level} level
- Each sentence should be one line and concise

【Output format】
1. [First example sentence]
2. [Second example sentence]

Return only the output.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        
        # 結果を解析
        lines = result.split('\n')
        example_sentences = []
        
        for line in lines:
            line = line.strip()
            if line and (line.startswith('1.') or line.startswith('2.') or line.startswith('1．') or line.startswith('2．')):
                # 番号を除去
                sentence = line.split('.', 1)[1] if '.' in line else line.split('．', 1)[1] if '．' in line else line
                sentence = sentence.strip()
                if sentence:
                    example_sentences.append(sentence)
        
        # 例文が取得できない場合のフォールバック
        if not example_sentences:
            example_sentences = [
                f"{reading} means {meaning}.",
                f"This {reading} is very important."
            ]
        
        return '\n'.join(example_sentences)
        
    except Exception as e:
        # GPTが失敗した場合のフォールバック
        print(f"GPT example error: {e}")
        return f"{reading} means {meaning}.\nThis {reading} is very important."

def select_contextual_distractors(question, other_words):
    """問題文の文脈に適した選択肢を選ぶ"""
    context_keywords = {
        '飲': ['飲み物', '水', 'お茶', 'ジュース', 'コーヒー'],
        '美味しい': ['食べ物', '料理', '果物', '飲み物'],
        '買い物': ['店', '場所', '建物', '街'],
        '勉強': ['本', '教科書', '辞書', '資料'],
        '大好き': ['物', '食べ物', '映画', '音楽', 'スポーツ'],
        '友達': ['場所', '店', 'カフェ', '公園'],
        '元気': ['食べ物', '飲み物', '薬', '栄養'],
        'ある': ['物', '場所', '建物', '店'],
        '計画': ['目標', '将来', '仕事', '旅行'],
        '調': ['情報', '資料', '本', '辞書'],
        '参加': ['会議', 'イベント', 'クラブ', '活動'],
        '確認': ['予約', '時間', '場所', '内容'],
        '準備': ['食事', '会議', '旅行', '試験'],
        '説明': ['内容', '方法', '理由', '状況'],
        '選': ['商品', '服', '本', '映画'],
        '決': ['時間', '場所', '方法', '予算'],
        '話し合': ['問題', '計画', '将来', '予算'],
        '調査': ['問題', '状況', '原因', '結果'],
        '改善': ['方法', '品質', '効率', '環境'],
        '検討': ['案', '計画', '提案', '方法'],
        '実現': ['目標', '計画', '夢', '理想'],
        '解決': ['問題', '課題', '紛争', '困難'],
        '分析': ['データ', '結果', '状況', '市場'],
        '評価': ['結果', '成果', '作品', '能力'],
        '検証': ['仮説', '理論', 'データ', '結果'],
        '最適化': ['システム', '方法', 'プロセス', '効率'],
        '統合': ['システム', '情報', 'データ', '機能'],
        '構築': ['システム', '関係', 'ネットワーク', 'チーム'],
        '確立': ['制度', '方法', 'システム', '関係'],
        '促進': ['活動', '発展', '成長', '交流'],
        '維持': ['状態', '関係', '品質', '健康'],
        '向上': ['能力', '品質', '技術', '効率'],
        '革新': ['技術', '方法', 'システム', '製品'],
        '推進': ['政策', '計画', '活動', '改革']
    }
    
    selected_distractors = []
    
    # 問題文からキーワードを抽出して適切な選択肢を選ぶ
    for keyword, related_words in context_keywords.items():
        if keyword in question:
            # 関連する語彙を優先的に選択
            related_candidates = []
            for _, word_row in other_words.iterrows():
                word_hiragana = str(word_row['Word']) if pd.notna(word_row['Word']) else ""
                word_meaning = str(word_row['Meaning']) if pd.notna(word_row['Meaning']) else ""
                if word_hiragana and word_meaning and any(related in word_meaning for related in related_words):
                    related_candidates.append(word_hiragana)
            
            # 関連する語彙から選択
            if len(related_candidates) >= 3:
                selected_distractors = random.sample(related_candidates, 3)
                break
            elif len(related_candidates) > 0:
                selected_distractors = related_candidates
                # 残りはランダムに選択
                remaining = [w for w in other_words['Word'].tolist() if w not in selected_distractors]
                if len(remaining) >= (3 - len(selected_distractors)):
                    selected_distractors.extend(random.sample(remaining, 3 - len(selected_distractors)))
                else:
                    selected_distractors.extend(remaining)
                break
    
    # キーワードが見つからない場合はランダムに選択
    if not selected_distractors:
        if len(other_words) >= 3:
            selected_distractors = other_words.sample(3)['Word'].dropna().tolist()
        else:
            selected_distractors = other_words['Word'].dropna().tolist()
    
    return selected_distractors

def generate_example_sentences(kanji, reading, meaning, level):
    """正解の単語を使った例文を生成"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""
次の単語を使って、日本語学習者（JLPT {level}レベル）向けの例文を2つ作ってください。

単語：{kanji}（{reading}）
意味：{meaning}

【条件】
- 日本語学習者が理解しやすい簡単な文にする
- 2つの異なる使い方や文脈で例文を作る
- ひらがなで書く（漢字は使わない）
- 各例文は1行で、短く簡潔にする

【出力形式】
1. 〇〇〇〇〇〇〇〇〇〇。
2. 〇〇〇〇〇〇〇〇〇〇。

出力のみを返してください。
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        result = response.choices[0].message.content.strip()
        
        # 結果を解析
        lines = result.split('\n')
        example_sentences = []
        
        for line in lines:
            line = line.strip()
            if line and (line.startswith('1.') or line.startswith('2.') or line.startswith('1．') or line.startswith('2．')):
                # 番号を除去
                sentence = line.split('.', 1)[1] if '.' in line else line.split('．', 1)[1] if '．' in line else line
                sentence = sentence.strip()
                if sentence:
                    example_sentences.append(sentence)
        
        # 例文が取得できない場合のフォールバック
        if not example_sentences:
            example_sentences = [
                f"{reading}は{meaning}です。",
                f"この{reading}はとても大切です。"
            ]
        
        return '\n'.join(example_sentences)
        
    except Exception as e:
        # GPTが失敗した場合のフォールバック
        print(f"GPT example error: {e}")
        return f"{reading}は{meaning}です。\nこの{reading}はとても大切です。"

def safe_strip(val):
    return val.strip() if isinstance(val, str) else ""

def generate_feedback_and_examples(word, kanji, meaning, level, quiz_sentence, options):
    # Load allowed words from Google Sheets for the selected level
    sheet_id = os.getenv('GOOGLE_SHEETS_ID')
    df = load_vocab_data_from_sheets(sheet_id, level)
    if df is None:
        # Fallback to Excel if Google Sheets fails
        try:
            df = pd.read_excel("database/JLPT vocabulary.xlsx", sheet_name=level)
        except Exception as e:
            print(f"Excel fallback failed: {e}")
            df = pd.DataFrame()  # Empty dataframe as last resort
    
    allowed_words = df["Word"].dropna().unique().tolist() if not df.empty else []
    allowed_words_str = ", ".join(allowed_words)
    # Identify all options (not just distractors)
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
                print(f"Generated quiz: {quiz}")  # Debug log
            except Exception as e:
                print(f"Error generating quiz: {e}")  # Debug log
                quiz = None
                session['current_quiz'] = None
        elif request.form.get("action") in ["submit", "answer"]:
            # Get quiz from session or reconstruct from form data
            quiz = session.get('current_quiz')
            print(f"Retrieved quiz from session: {quiz}")  # Debug log
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
                print(f"Reconstructed quiz from form data: {quiz}")  # Debug log
            
            selected_option = request.form.get("user_answer") or request.form.get("answer")
            print(f"User selected: {selected_option}, Correct answer: {quiz['answer']}")  # Debug log
            
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
                print(f"GET request - Generated new quiz: {quiz}")  # Debug log
            except Exception as e:
                print(f"GET request - Error generating quiz: {e}")  # Debug log
                quiz = None
                session['current_quiz'] = None
        else:
            print(f"GET request - Using existing quiz from session")  # Debug log
        
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