from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import current_user
from functools import wraps
import openai
import os
import re
import json
from dotenv import load_dotenv
import pandas as pd
import random
from google_sheets_helper import load_grammar_data_from_sheets
from models import db, GrammarQuizLog
from error_handler import safe_openai_request, format_error_response, get_localized_error_message, handle_database_errors
from utils.furigana import text_to_ruby_html

grammar_bp = Blueprint('grammar', __name__, url_prefix="/grammar")
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 文法構文リスト（Google Sheetsから読み込み）
grammar_dict = {}

def load_grammar():
    global grammar_dict
    grammar_sheet_id = os.getenv('GOOGLE_SHEETS_GRAMMAR_ID')
    
    for level in ["N5", "N4", "N3", "N2", "N1"]:
        # Google Sheetsからデータを読み込み
        grammar_list = load_grammar_data_from_sheets(grammar_sheet_id, level)
        
        if grammar_list is None:
            # Fallback to Excel if Google Sheets fails
            try:
                df_path = "database/JLPT grammar.xlsx"
                df = pd.read_excel(df_path, sheet_name=level)
                grammar_list = df["Grammar"].dropna().tolist()
                print(f"Excel fallback used for {level}: {len(grammar_list)} patterns loaded")
            except Exception as e:
                print(f"Excel fallback also failed for {level}: {e}")
                grammar_list = []
        
        grammar_dict[level] = grammar_list

load_grammar()

def google_login_required(f):
    """Googleログインが必要な機能用デコレーター"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('文法機能を利用するにはGoogleログインが必要です。', 'warning')
            return redirect(url_for('login'))
        
        # Google OAuthユーザーかチェック
        is_google_user = (hasattr(current_user, 'auth_type') and current_user.auth_type == 'google') or \
                        (hasattr(current_user, 'google_id') and current_user.google_id)
        
        if not is_google_user:
            flash('文法機能はGoogleログイン限定です。', 'warning')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

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
    original_ruby = ""
    model_answer_ruby = []
    casual_answer_ruby = ""

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
                
                # ログイン時のみログを保存
                if current_user.is_authenticated:
                    @handle_database_errors
                    def save_quiz_log():
                        # スコアを計算（grammarとmeaningの平均を0-100スケールに変換）
                        score = ((grammar + meaning) / 6.0) * 100 if grammar and meaning else None
                        
                        # ログを保存
                        import json
                        log = GrammarQuizLog(
                            user_id=current_user.id,
                            original_sentence=original,
                            user_translation=translation,
                            jlpt_level=level,
                            direction='en_to_ja' if direction == 'en-ja' else 'ja_to_en',
                            score=score,
                            feedback=feedback if feedback else None,
                            model_answer=json.dumps(model_answer) if model_answer else None
                        )
                        db.session.add(log)
                        db.session.commit()
                        return {"success": True}
                    
                    # ログ保存を試行（エラーが発生してもメイン機能には影響させない）
                    save_result = save_quiz_log()
                    if isinstance(save_result, dict) and "error" in save_result:
                        print(f"Grammar quiz log save error: {save_result['error']}")
                        try:
                            db.session.rollback()
                        except:
                            pass
        except Exception as e:
            message = f"Error: {str(e)}"

    else:
        # GETリクエスト時は必ず文を生成
        original = generate_example_sentence(level, direction)
        translation = ""

    
    # 日本語→英語の方向の場合のみ振り仮名を付与
    # direction が 'ja-en' または日本語が含まれる場合
    if direction == "ja-en" and original:
        try:
            original_ruby = text_to_ruby_html(original)
            if casual_answer:
                casual_answer_ruby = text_to_ruby_html(casual_answer)
            if model_answer:
                model_answer_ruby = [text_to_ruby_html(answer) for answer in model_answer]
        except Exception as e:
            # furigana機能でエラーが発生した場合は元のテキストを使用
            original_ruby = original
            casual_answer_ruby = casual_answer
            model_answer_ruby = model_answer
    elif original and any('\u4e00' <= ch <= '\u9fff' for ch in original):
        # 方向に関係なく、日本語（漢字）が含まれていれば振り仮名を付与
        try:
            original_ruby = text_to_ruby_html(original)
            if casual_answer and any('\u4e00' <= ch <= '\u9fff' for ch in casual_answer):
                casual_answer_ruby = text_to_ruby_html(casual_answer)
            if model_answer:
                model_answer_ruby = []
                for answer in model_answer:
                    if any('\u4e00' <= ch <= '\u9fff' for ch in answer):
                        ruby_answer = text_to_ruby_html(answer)
                        model_answer_ruby.append(ruby_answer)
                    else:
                        model_answer_ruby.append(answer)
        except Exception as e:
            original_ruby = original
            casual_answer_ruby = casual_answer
            model_answer_ruby = model_answer
    # No furigana needed for English-only text

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
        casual_answer=casual_answer,
        original_ruby=original_ruby,
        model_answer_ruby=model_answer_ruby,
        casual_answer_ruby=casual_answer_ruby
    )

def generate_example_sentence(level, direction):
    grammar_list = grammar_dict.get(level, [])
    if not grammar_list:
        return get_localized_error_message("feature_temporarily_disabled")
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

    def make_api_call():
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return re.split(r'→|:|\n', response.choices[0].message.content.strip())[0]
    
    # エラーハンドリング付きでAPI呼び出し
    result = safe_openai_request(make_api_call)
    
    if isinstance(result, dict) and "error" in result:
        return result["error"]  # エラーメッセージを返す
    
    return result

def score_translation(original, student_translation, direction, level):
    # For Japanese → English direction, provide scoring and examples but no feedback
    if direction == "ja-en":
        prompt = f"""
Original Japanese sentence: {original}
Student English translation: {student_translation}
Translation direction: Japanese → English
JLPT Level: {level}

Please evaluate and return a JSON object like this:
{{
  "grammar": 1-3,
  "meaning": 1-3,
  "model_answer": ["...", "..."],
  "casual_answer": "",
  "feedback": ""
}}

For scoring ("grammar" and "meaning"), evaluate how well the student captured the Japanese grammar structure and meaning in English.
For "model_answer", provide two natural and correct English translations as model answers.
Leave "casual_answer" and "feedback" as empty strings since this is Japanese to English practice.

Respond only with JSON.
"""
        
        def make_api_call():
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4
            )
            raw = response.choices[0].message.content
            json_text = extract_json(raw)
            return json.loads(json_text)
        
        # エラーハンドリング付きでAPI呼び出し
        result = safe_openai_request(make_api_call)
        
        if isinstance(result, dict) and "error" in result:
            return {
                "grammar": None,
                "meaning": None, 
                "model_answer": [],
                "feedback": result["error"],
                "casual_answer": ""
            }
        
        return result
    
    # Only provide full feedback for English → Japanese direction
    prompt = f"""
Original sentence: {original}
Student translation: {student_translation}
Translation direction: English → Japanese
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

    def make_api_call():
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        raw = response.choices[0].message.content
        json_text = extract_json(raw)
        return json.loads(json_text)
    
    # エラーハンドリング付きでAPI呼び出し
    result = safe_openai_request(make_api_call)
    
    if isinstance(result, dict) and "error" in result:
        return {
            "grammar": None,
            "meaning": None, 
            "model_answer": [],
            "feedback": result["error"],
            "casual_answer": ""
        }
    
    return result

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("Failed to extract JSON.")

@grammar_bp.route("/logs", methods=["GET"])
@google_login_required
def grammar_logs():
    """ユーザーの文法クイズログを表示"""
    try:
        import json
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        try:
            # 現在のユーザーのログのみを取得
            logs = GrammarQuizLog.query.filter_by(user_id=current_user.id)\
                                     .order_by(GrammarQuizLog.created_at.desc())\
                                     .paginate(page=page, per_page=per_page, error_out=False)
        except Exception as query_error:
            # PostgreSQLトランザクションをロールバック
            try:
                db.session.rollback()
            except Exception:
                pass
                
            # model_answer列がない場合は、基本的なクエリのみ実行
            try:
                logs = GrammarQuizLog.query.with_entities(
                    GrammarQuizLog.id,
                    GrammarQuizLog.user_id,
                    GrammarQuizLog.original_sentence,
                    GrammarQuizLog.user_translation,
                    GrammarQuizLog.jlpt_level,
                    GrammarQuizLog.direction,
                    GrammarQuizLog.score,
                    GrammarQuizLog.feedback,
                    GrammarQuizLog.created_at
                ).filter_by(user_id=current_user.id)\
                 .order_by(GrammarQuizLog.created_at.desc())\
                 .paginate(page=page, per_page=per_page, error_out=False)
            except Exception as fallback_error:
                # 空のページネーションオブジェクトを作成
                class FakePagination:
                    def __init__(self, page, per_page, total, items):
                        self.page = page
                        self.per_page = per_page
                        self.total = total
                        self.items = items
                        self.pages = 1
                        self.has_prev = False
                        self.has_next = False
                        self.prev_num = None
                        self.next_num = None
                    
                    def iter_pages(self):
                        return []
                
                logs = FakePagination(page=page, per_page=per_page, total=0, items=[])
        
        # ログのmodel_answerをJSONからリストに変換（安全な方法）
        processed_logs = []
        for log in logs.items:
            try:
                # logを辞書形式に変換して新しい属性を安全に追加
                log_dict = {}
                
                # SQLAlchemy objectの属性をコピー
                for attr in ['id', 'user_id', 'original_sentence', 'user_translation', 
                           'jlpt_level', 'direction', 'score', 'feedback', 'created_at']:
                    if hasattr(log, attr):
                        log_dict[attr] = getattr(log, attr)
                
                # model_answerを処理
                if hasattr(log, 'model_answer') and getattr(log, 'model_answer'):
                    try:
                        log_dict['parsed_model_answer'] = json.loads(getattr(log, 'model_answer'))
                    except json.JSONDecodeError:
                        log_dict['parsed_model_answer'] = []
                else:
                    log_dict['parsed_model_answer'] = []
                
                # 辞書を簡単なオブジェクトに変換
                class LogObject:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                
                processed_logs.append(LogObject(log_dict))
                
            except Exception as e:
                # エラーが発生したログはスキップ
                continue
        
        # logs.itemsを処理済みのリストに置き換え
        logs.items = processed_logs
        
        return render_template('grammar_logs.html', logs=logs)
    except Exception as e:
        return f"Grammar logs error: {str(e)}", 500