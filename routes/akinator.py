import os
import random
import pandas as pd
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import openai
import re

"""
JLPT Kotoba Akinator - How to play

This app has two modes:
1. AI guesses: The user thinks of a JLPT word, and the AI (ChatGPT) asks questions to guess it. The user answers with "はい (Yes)", "いいえ (No)", "わからない (Don't know)", or "ときどき (Sometimes)". The game ends when the user presses the "正解！" button after the AI guesses correctly.
2. User guesses: The AI thinks of a JLPT word, and the user asks questions in Japanese to narrow it down. The user can guess by asking "○○ですか？", ask for a hint (ヒント), or give up (降参/こたえ).

本アプリは2つのモードがあります：
1. AIが当てる: ユーザーがJLPT単語を考え、AI（ChatGPT）が質問して当てます。ユーザーは「はい」「いいえ」「わからない」「ときどき」で答え、AIが正解を当てたら「正解！」ボタンを押して終了します。
2. あなたが当てる: AIがJLPT単語を考え、ユーザーが日本語で質問して単語を絞り込みます。「○○ですか？」で推測、ヒントや降参も使えます。
"""

akinator_bp = Blueprint('akinator', __name__, url_prefix='/akinator')

# Excelファイルのパス
VOCAB_XLSX = os.path.join(os.path.dirname(__file__), '../database/JLPT vocabulary.xlsx')

# 利用可能なJLPTレベル
JLPT_LEVELS = ['N3', 'N2', 'N1']

# 一般的な漢字読み辞書（主要なJLPT語彙）
KANJI_READINGS = {
    # 事件関連
    '事件': 'じけん', 'じけん': '事件',
    # 砂漠関連
    '砂漠': 'さばく', 'さばく': '砂漠',
    # 茶関連
    '茶': 'ちゃ', 'ちゃ': '茶', 'お茶': 'おちゃ', 'おちゃ': 'お茶',
    # 水関連
    '水': 'みず', 'みず': '水',
    # 人関連
    '人': 'ひと', 'ひと': '人',
    # 学校関連
    '学校': 'がっこう', 'がっこう': '学校',
    # 会社関連
    '会社': 'かいしゃ', 'かいしゃ': '会社',
    # 家族関連
    '家族': 'かぞく', 'かぞく': '家族',
    # 友達関連
    '友達': 'ともだち', 'ともだち': '友達',
    # 先生関連
    '先生': 'せんせい', 'せんせい': '先生',
    # 学生関連
    '学生': 'がくせい', 'がくせい': '学生',
    # 仕事関連
    '仕事': 'しごと', 'しごと': '仕事',
    # 時間関連
    '時間': 'じかん', 'じかん': '時間',
    # 場所関連
    '場所': 'ばしょ', 'ばしょ': '場所',
    # 問題関連
    '問題': 'もんだい', 'もんだい': '問題',
    # 答え関連
    '答え': 'こたえ', 'こたえ': '答え',
    # 質問関連
    '質問': 'しつもん', 'しつもん': '質問',
    # 説明関連
    '説明': 'せつめい', 'せつめい': '説明',
    # 練習関連
    '練習': 'れんしゅう', 'れんしゅう': '練習',
    # 試験関連
    '試験': 'しけん', 'しけん': '試験',
    # 宿題関連
    '宿題': 'しゅくだい', 'しゅくだい': '宿題',
    # 部屋関連
    '部屋': 'へや', 'へや': '部屋',
    # 建物関連
    '建物': 'たてもの', 'たてもの': '建物',
    # 車関連
    '車': 'くるま', 'くるま': '車',
    # 電車関連
    '電車': 'でんしゃ', 'でんしゃ': '電車',
    # 飛行機関連
    '飛行機': 'ひこうき', 'ひこうき': '飛行機',
    # 船関連
    '船': 'ふね', 'ふね': '船',
    # 動物関連
    '動物': 'どうぶつ', 'どうぶつ': '動物',
    # 植物関連
    '植物': 'しょくぶつ', 'しょくぶつ': '植物',
    # 食べ物関連
    '食べ物': 'たべもの', 'たべもの': '食べ物',
    # 飲み物関連
    '飲み物': 'のみもの', 'のみもの': '飲み物',
    # 服関連
    '服': 'ふく', 'ふく': '服',
    # 靴関連
    '靴': 'くつ', 'くつ': '靴',
    # 帽子関連
    '帽子': 'ぼうし', 'ぼうし': '帽子',
    # 鞄関連
    '鞄': 'かばん', 'かばん': '鞄',
    # 本関連
    '本': 'ほん', 'ほん': '本',
    # 新聞関連
    '新聞': 'しんぶん', 'しんぶん': '新聞',
    # 雑誌関連
    '雑誌': 'ざっし', 'ざっし': '雑誌',
    # 映画関連
    '映画': 'えいが', 'えいが': '映画',
    # 音楽関連
    '音楽': 'おんがく', 'おんがく': '音楽',
    # スポーツ関連
    'スポーツ': 'スポーツ',
    # ゲーム関連
    'ゲーム': 'ゲーム',
    # 電話関連
    '電話': 'でんわ', 'でんわ': '電話',
    # テレビ関連
    'テレビ': 'テレビ',
    # パソコン関連
    'パソコン': 'パソコン',
    # 携帯関連
    '携帯': 'けいたい', 'けいたい': '携帯',
    # カメラ関連
    'カメラ': 'カメラ',
    # 時計関連
    '時計': 'とけい', 'とけい': '時計',
    # 鍵関連
    '鍵': 'かぎ', 'かぎ': '鍵',
    # 財布関連
    '財布': 'さいふ', 'さいふ': '財布',
    # お金関連
    'お金': 'おかね', 'おかね': 'お金',
    # 切符関連
    '切符': 'きっぷ', 'きっぷ': '切符',
    # チケット関連
    'チケット': 'チケット',
    # 切手関連
    '切手': 'きって', 'きって': '切手',
    # 手紙関連
    '手紙': 'てがみ', 'てがみ': '手紙',
    # メール関連
    'メール': 'メール',
    # 住所関連
    '住所': 'じゅうしょ', 'じゅうしょ': '住所',
    # 番地関連
    '番地': 'ばんち', 'ばんち': '番地',
    # 郵便番号関連
    '郵便番号': 'ゆうびんばんごう', 'ゆうびんばんごう': '郵便番号',
    # 国関連
    '国': 'くに', 'くに': '国',
    # 県関連
    '県': 'けん', 'けん': '県',
    # 市関連
    '市': 'し', 'し': '市',
    # 町関連
    '町': 'まち', 'まち': '町',
    # 村関連
    '村': 'むら', 'むら': '村',
    # 駅関連
    '駅': 'えき', 'えき': '駅',
    # 空港関連
    '空港': 'くうこう', 'くうこう': '空港',
    # 港関連
    '港': 'みなと', 'みなと': '港',
    # 公園関連
    '公園': 'こうえん', 'こうえん': '公園',
    # 図書館関連
    '図書館': 'としょかん', 'としょかん': '図書館',
    # 博物館関連
    '博物館': 'はくぶつかん', 'はくぶつかん': '博物館',
    # 美術館関連
    '美術館': 'びじゅつかん', 'びじゅつかん': '美術館',
    # 映画館関連
    '映画館': 'えいがかん', 'えいがかん': '映画館',
    # レストラン関連
    'レストラン': 'レストラン',
    # 喫茶店関連
    '喫茶店': 'きっさてん', 'きっさてん': '喫茶店',
    # カフェ関連
    'カフェ': 'カフェ',
    # スーパー関連
    'スーパー': 'スーパー',
    # デパート関連
    'デパート': 'デパート',
    # 銀行関連
    '銀行': 'ぎんこう', 'ぎんこう': '銀行',
    # 郵便局関連
    '郵便局': 'ゆうびんきょく', 'ゆうびんきょく': '郵便局',
    # 病院関連
    '病院': 'びょういん', 'びょういん': '病院',
    # 薬局関連
    '薬局': 'やっきょく', 'やっきょく': '薬局',
    # 警察署関連
    '警察署': 'けいさつしょ', 'けいさつしょ': '警察署',
    # 消防署関連
    '消防署': 'しょうぼうしょ', 'しょうぼうしょ': '消防署',
}

def normalize_text(text):
    """
    文字種（漢字・ひらがな・カタカナ）を統一して比較用のテキストを生成
    """
    if not isinstance(text, str):
        return ""
    
    # カタカナをひらがなに変換
    text = text.translate(str.maketrans('ァ-ン', 'ぁ-ん'))
    
    # 全角英数字を半角に変換
    text = text.translate(str.maketrans('０-９Ａ-Ｚａ-ｚ', '0-9A-Za-z'))
    
    # 空白と記号を除去
    text = re.sub(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', '', text)
    
    return text.lower()

def is_correct_answer(user_guess, correct_word):
    """
    ユーザーの推測が正解かどうかを判定（文字種と漢字読みを考慮）
    """
    if not user_guess or not correct_word:
        return False
    
    # 文字種を統一して比較
    normalized_guess = normalize_text(user_guess)
    normalized_correct = normalize_text(correct_word)
    
    # 完全一致
    if normalized_guess == normalized_correct:
        return True
    
    # 部分一致（正解が含まれている場合）
    if normalized_correct in normalized_guess or normalized_guess in normalized_correct:
        return True
    
    # 漢字読み辞書でチェック
    if user_guess in KANJI_READINGS and KANJI_READINGS[user_guess] == correct_word:
        return True
    if correct_word in KANJI_READINGS and KANJI_READINGS[correct_word] == user_guess:
        return True
    
    return False

# セッション初期化
@akinator_bp.route('/', methods=['GET', 'POST'])
def akinator_index():
    if request.method == 'POST':
        role = request.form.get('role')
        level = request.form.get('level')
        if role in ['user', 'gpt'] and level in JLPT_LEVELS:
            session['akinator_role'] = role
            session['akinator_level'] = level
            session['akinator_gameover'] = False
            session['akinator_history'] = []
            # 語彙を選択
            word, meaning = select_random_noun(level)
            session['akinator_word'] = word
            session['akinator_meaning'] = meaning
            return redirect(url_for('akinator.akinator_game'))
    return render_template('akinator_select.html', levels=JLPT_LEVELS)

# ゲーム画面
@akinator_bp.route('/game', methods=['GET', 'POST'])
def akinator_game():
    if 'akinator_role' not in session or 'akinator_level' not in session:
        return redirect(url_for('akinator.akinator_index'))

    # 履歴の初期化
    if 'akinator_history' not in session or not isinstance(session['akinator_history'], list) or \
       (session['akinator_history'] and not isinstance(session['akinator_history'][0], dict)):
        session['akinator_history'] = []

    role = session['akinator_role']
    level = session['akinator_level']
    history = session['akinator_history']
    if not isinstance(history, list) or (history and not isinstance(history[0], dict)):
        history = []
        session['akinator_history'] = history

    # ChatGPTがアキネーターモード
    if role == 'gpt':
        # 最初のGET時はChatGPTから質問を出す
        if request.method == 'GET' and not history:
            prompt = build_akinator_gpt_prompt(history, level)
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": str(prompt)}],
                temperature=0.5
            )
            gpt_reply = response.choices[0].message.content
            if isinstance(gpt_reply, str):
                gpt_reply = gpt_reply.strip()
            else:
                gpt_reply = ''
            history.append({'role': 'gpt', 'text': gpt_reply})
            session['akinator_history'] = history
        # POST: ユーザーのボタン回答を受け付け
        elif request.method == 'POST' and not session.get('akinator_gameover', False):
            msg = request.form.get('message', '')
            if isinstance(msg, str):
                msg = msg.strip()
            else:
                msg = ''
            if msg:
                # ユーザーの回答を履歴に追加
                history.append({'role': 'user', 'text': msg})
                session['akinator_history'] = history
                # --- ヒントリクエスト処理 ---
                if msg == 'ヒント':
                    # ヒントの場合は理解不能判定をスキップ
                    word = session.get('akinator_word')
                    meaning = session.get('akinator_meaning')
                    hint_prompt = build_akinator_hint_prompt(history, level, word, meaning)
                    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    max_retry = 3
                    for _ in range(max_retry):
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": str(hint_prompt)}],
                            temperature=0.5
                        )
                        hint_text = response.choices[0].message.content
                        if isinstance(hint_text, str):
                            hint_text = hint_text.strip()
                        else:
                            hint_text = ''
                        # 絵文字や短すぎるヒント、疑問文、?のみ、などは再生成
                        if len(hint_text) < 6 or any(e in hint_text for e in ["⎝", "( ᐛ )", "？", "?", "(੭", "Ҩ", "╭☞", "ʕ˒", "!", "only output", "output only"]):
                            continue
                        if hint_text.endswith("？") or hint_text.endswith("?"):
                            continue
                        break
                    history.append({'role': 'gpt', 'text': f'ヒント: {hint_text}'})
                    session['akinator_history'] = history
                    return render_template('akinator.html',
                        role=role, level=level, gameover=session.get('akinator_gameover', False),
                        word=None, meaning=None, history=history)
                # 推測に「はい」と答えたらゲーム終了
                if msg == 'はい':
                    last_gpt = None
                    for m in reversed(history[:-1]):
                        if isinstance(m, dict) and 'role' in m and m['role'] == 'gpt':
                            last_gpt = m
                            break
                    if last_gpt and ('この単語は' in last_gpt['text'] or '正解？' in last_gpt['text'] or ('ですか' in last_gpt['text'] and len(last_gpt['text']) < 20)):
                        # 推測メッセージに正解メッセージを追加
                        if 'この単語は' in last_gpt['text']:
                            last_gpt['text'] += '\n（アキネーターの推測が正解です！）'
                        else:
                            last_gpt['text'] += '\n（正解です！）'
                        # session['akinator_gameover'] = True  # <-- Remove this line to keep the game running
                        session['akinator_history'] = history
                        return render_template('akinator.html',
                            role=role, level=level, gameover=False,  # <-- Keep gameover False
                            word=None, meaning=None, history=history)
                # 「正解！」が入力された場合の処理
                if msg == '正解！':
                    history.append({'role': 'gpt', 'text': 'やった！遊んでくれてありがとう！'})
                    session['akinator_gameover'] = True
                    session['akinator_history'] = history
                    return render_template('akinator.html',
                        role=role, level=level, gameover=True,
                        word=None, meaning=None, history=history)
                # まだ続く場合は次の質問/推測
                prompt = build_akinator_gpt_prompt(history, level)
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": str(prompt)}],
                    temperature=0.5
                )
                gpt_reply = response.choices[0].message.content
                if isinstance(gpt_reply, str):
                    gpt_reply = gpt_reply.strip()
                else:
                    gpt_reply = ''
                history.append({'role': 'gpt', 'text': gpt_reply})
                session['akinator_history'] = history
        return render_template('akinator.html',
            role=role, level=level, gameover=session.get('akinator_gameover', False),
            word=None, meaning=None, history=history)

    # あなたがアキネーターモード（従来通り）
    if request.method == 'POST' and not session.get('akinator_gameover', False):
        msg = request.form.get('message', '')
        if isinstance(msg, str):
            msg = msg.strip()
        else:
            msg = ''
        if msg:
            if not isinstance(history, list) or (history and not isinstance(history[0], dict)):
                history = []
                session['akinator_history'] = history
            # --- ヒントリクエスト処理（ユーザーがアキネーターの場合も対応） ---
            if msg == 'ヒント':
                word = session.get('akinator_word')
                meaning = session.get('akinator_meaning')
                hint_prompt = build_akinator_hint_prompt(history, level, word, meaning)
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                max_retry = 3
                for _ in range(max_retry):
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": str(hint_prompt)}],
                        temperature=0.5
                    )
                    hint_text = response.choices[0].message.content
                    if isinstance(hint_text, str):
                        hint_text = hint_text.strip()
                    else:
                        hint_text = ''
                    if len(hint_text) < 6:
                        continue
                    if hint_text.endswith("？") or hint_text.endswith("?"):
                        continue
                    break
                history.append({'role': 'gpt', 'text': f'ヒント: {hint_text}'})
                session['akinator_history'] = history
                return render_template('akinator.html',
                    role=session['akinator_role'],
                    level=session['akinator_level'],
                    gameover=session.get('akinator_gameover', False),
                    word=session.get('akinator_word'),
                    meaning=session.get('akinator_meaning'),
                    history=history
                )
            # --- 正解！ボタン処理 ---
            if msg == '正解！':
                history.append({'role': 'user', 'text': '正解！'})
                history.append({'role': 'gpt', 'text': 'おめでとうございます！正解です！'})
                session['akinator_gameover'] = True
                session['akinator_history'] = history
                return render_template('akinator.html',
                    role=session['akinator_role'],
                    level=session['akinator_level'],
                    gameover=True,
                    word=session.get('akinator_word'),
                    meaning=session.get('akinator_meaning'),
                    history=history
                )
            # --- 「はい」で正解確認された場合の処理 ---
            if msg == 'はい':
                last_gpt = None
                for m in reversed(history[:-1]):
                    if isinstance(m, dict) and 'role' in m and m['role'] == 'gpt':
                        last_gpt = m
                        break
                if last_gpt and ('正解？' in last_gpt['text'] or ('ですか' in last_gpt['text'] and len(last_gpt['text']) < 20)):
                    history.append({'role': 'gpt', 'text': 'おめでとうございます！正解です！'})
                    session['akinator_gameover'] = True
                    session['akinator_history'] = history
                    return render_template('akinator.html',
                        role=session['akinator_role'],
                        level=session['akinator_level'],
                        gameover=True,
                        word=session.get('akinator_word'),
                        meaning=session.get('akinator_meaning'),
                        history=history
                    )
            history.append({'role': 'user', 'text': msg})
            session['akinator_history'] = history
            word = session.get('akinator_word')
            meaning = session.get('akinator_meaning')
            level = session.get('akinator_level')
            
            # ユーザーの推測判定（「？」で終わるメッセージの場合）
            if msg.endswith('？') or msg.endswith('?'):
                # 推測から「？」を除去して単語部分を抽出
                guess_word = msg.rstrip('？?').strip()
                if is_correct_answer(guess_word, word):
                    gpt_reply = "はい"
                else:
                    gpt_reply = "いいえ"
                history.append({'role': 'gpt', 'text': gpt_reply})
                session['akinator_history'] = history
                return render_template('akinator.html',
                    role=session['akinator_role'],
                    level=session['akinator_level'],
                    gameover=session.get('akinator_gameover', False),
                    word=session.get('akinator_word'),
                    meaning=session.get('akinator_meaning'),
                    history=history
                )
            
            # 降参コマンド判定
            giveup_cmds = ["/giveup", "降参", "答え", "ギブアップ", "give up", "ans", "answer"]
            if any(cmd in msg.lower() for cmd in giveup_cmds):
                answer_text = f"正解は「{word}」（{meaning}）でした！"
                history.append({'role': 'gpt', 'text': answer_text})
                session['akinator_gameover'] = True
                session['akinator_history'] = history
                return render_template('akinator.html',
                    role=session['akinator_role'],
                    level=session['akinator_level'],
                    gameover=True,
                    word=word,
                    meaning=meaning,
                    history=history
                )
            # ChatGPTは必ず四択で返す（質問しない）
            prompt = f"""
あなたは日本語語彙アキネーターの回答者です。今、JLPT {level}レベルの日本語名詞「{word}」（意味: {meaning}）を思い浮かべています。

【ルール】
- ユーザーからの質問には必ず「はい」「いいえ」「わからない」「ときどき」のいずれか1つだけで答えてください。
- 絶対に質問や説明、推測文、その他の発言はしないでください。
- JLPT{level}レベルの学習者と会話していることを意識して、質問の内容などを考慮してください。

【重要：矛盾しない回答】
- 過去の回答を必ず確認し、矛盾する回答は絶対にしないでください。
- 例：「人より大きいですか？」に「いいえ」と答えた場合、「人より小さいですか？」には必ず「はい」と答えてください。
- 例：「食べ物ですか？」に「はい」と答えた場合、「道具ですか？」には必ず「いいえ」と答えてください。
- 例：「生き物ですか？」に「いいえ」と答えた場合、「動物ですか？」には必ず「いいえ」と答えてください。
- 過去の回答と矛盾する可能性がある場合は、必ず過去の回答を優先してください。

【重要：漢字読みの統一】
- 漢字とひらがなの読み方が同じ場合は、同じ単語として扱ってください。
- 例：「事件」と「じけん」は同じ単語です。
- 例：「砂漠」と「さばく」は同じ単語です。
- 例：「お茶」と「茶」は同じ単語です。
- ユーザーが漢字で推測した場合、正解がひらがなでも「はい」と答えてください。
- ユーザーがひらがなで推測した場合、正解が漢字でも「はい」と答えてください。

【これまでのやりとり】
{chr(10).join(['ユーザー: '+m['text'] if m['role']=='user' else 'アキネーター: '+m['text'] for m in history])}
ユーザー: {msg}

上記のやりとりを必ず確認し、矛盾しない回答をしてください。漢字読みの違いも考慮してください。
"""
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": str(prompt)}],
                temperature=0.0
            )
            gpt_reply = response.choices[0].message.content
            if isinstance(gpt_reply, str):
                gpt_reply = gpt_reply.strip()
            else:
                gpt_reply = ''
            # 4択または絵文字以外は「わからない」にする
            allowed = ["はい", "いいえ", "わからない", "ときどき"]
            if gpt_reply not in allowed:
                gpt_reply = "わからない"
            
            # ユーザーが「正解？」と聞いてAIが「はい」と答えた場合の処理
            if gpt_reply == "はい":
                last_user = None
                for m in reversed(history[:-1]):
                    if isinstance(m, dict) and 'role' in m and m['role'] == 'user':
                        last_user = m
                        break
                if last_user and '正解？' in last_user['text']:
                    history.append({'role': 'gpt', 'text': gpt_reply})
                    history.append({'role': 'gpt', 'text': 'おめでとうございます！正解です！'})
                    session['akinator_gameover'] = True
                    session['akinator_history'] = history
                    return render_template('akinator.html',
                        role=session['akinator_role'],
                        level=session['akinator_level'],
                        gameover=True,
                        word=session.get('akinator_word'),
                        meaning=session.get('akinator_meaning'),
                        history=history
                    )
            
            history.append({'role': 'gpt', 'text': gpt_reply})
            session['akinator_history'] = history

    return render_template('akinator.html',
        role=session['akinator_role'],
        level=session['akinator_level'],
        gameover=session.get('akinator_gameover', False),
        word=session.get('akinator_word'),
        meaning=session.get('akinator_meaning'),
        history=session['akinator_history']
    )

# 名詞をランダムに選ぶ

def select_random_noun(level):
    df = pd.read_excel(VOCAB_XLSX, sheet_name=level)
    df = df[df['Type'] == 'noun']
    # Only use rows where 'Aki' is 1 (or equivalent)
    if 'Aki' in df.columns:
        df = df[df['Aki'].fillna(0).astype(int) == 1]
    if df.empty:
        return "（名詞なし）", "No noun found"
    row = df.sample(1).iloc[0]
    word = str(row['Word'])
    meaning = str(row['Meaning'])
    return word, meaning

# ChatGPT用プロンプト生成

def build_akinator_prompt(history, level):
    chat_log = ""
    for msg in history:
        if msg['role'] == 'user':
            chat_log += f"ユーザー: {msg['text']}\n"
        else:
            chat_log += f"アキネーター: {msg['text']}\n"
    prompt = (
        f"あなたは日本語語彙アキネーターです。ユーザーが考えているJLPT {level}レベルの日本語名詞を、はい・いいえ・わからない・ときどき だけで質問しながら当ててください。\n"
        "【ルール】\n"
        f"- JLPT{level}レベルの学習者が理解できる語彙・文法・表現・漢字で質問や推測を作成してください。\n"
        "- そのレベルの学習者が混乱しないよう、難しすぎる語彙・文法・漢字や抽象的な表現は避けてください。\n"
        "- 例：N5なら「水」「人」など基本的な漢字はOKですが、難しい漢字や語彙は使わないでください。\n"
        "- 1回ごとに「質問」または「推測（例: この単語は『○○』ですか？）」のどちらかを必ず1つだけ出力してください。\n"
        "- 質問は日本語で簡潔に。\n"
        "- 推測する場合は「この単語は『○○』ですか？」のように明確に書いてください。\n"
        "- まだ推測しない場合は、次の質問だけを出力してください。\n"
        "- 出力は質問または推測のみ。他の説明や前置きは不要です。\n"
        "【これまでのやりとり】\n"
        f"{chat_log}"
    )
    return prompt

def build_akinator_gpt_prompt(history, level):
    chat_log = ""
    for msg in history:
        if msg.get('role') == 'user':
            chat_log += f"ユーザー: {msg.get('text', '')}\n"
        else:
            chat_log += f"アキネーター: {msg.get('text', '')}\n"
    num_questions = sum(1 for m in history if m.get('role') == 'gpt')
    prompt = (
        "あなたは語彙アキネーターです。  \n"
        "ユーザーが思い浮かべている **日本語の名詞（具体的なもの）** を、「はい／いいえ／わからない／ときどき」の質問を通じて当ててください。\n"
        "\n"
        "【質問ルール】\n"
        "- 1ターンにつき1つの質問を出してください。\n"
        "- 質問は「カテゴリ」「用途」「見た目」「使う場所」「性質」などから、候補を二分できるようなものを選んでください。\n"
        "- 抽象的な語（例：食べ物、道具、感情など）は**推測の対象にしない**でください。\n"
        "- 抽象語は質問にのみ使用可能です（分類目的）。\n"
        "- カテゴリ質問（「食べ物ですか？」「道具ですか？」など）は分類目的のみに使用し、そのカテゴリ自体を推測対象にしないでください。\n"
        "- カテゴリ質問で「はい」が返ってきた場合、次は必ずそのカテゴリ内の具体的な単語を推測してください。\n"
        "\n"
        "【推測ルール】\n"
        "- 推測する語は、**具体的な単語**に限ります（例：バナナ、鉛筆、カバン、海など）。\n"
        "- 候補が明らかに絞れた場合、または10問程度経過した場合、推測してください。\n"
        "- 推測時は「〇〇ですか？」の形式で質問してください。\n"
        "\n"
        "【重要：推測対象の制限】\n"
        "- **抽象的なカテゴリや概念は絶対に推測対象にしないでください**。\n"
        "- 推測対象にできない例：「日常生活で使うもの」「食べ物」「道具」「生き物」「植物」「動物」「家具」「電子機器」「装飾品」「文房具」「服」「飲み物」など\n"
        "- 推測対象にできる例：「マグカップ」「バナナ」「鉛筆」「カバン」「海」「猫」「テーブル」「スマートフォン」「花瓶」「消しゴム」「シャツ」「コーヒー」など\n"
        "- カテゴリ質問（「〜ですか？」）は分類目的のみに使用し、そのカテゴリ自体を推測対象にしないでください。\n"
        "- 例：「それは日常生活で使うものですか？」に「はい」と答えた場合、次は「マグカップですか？」のように具体的な単語を推測してください。\n"
        "- 「日常生活で使うものですか？」自体を推測対象にすることは絶対に禁止です。\n"
        "\n"
        "【終了】\n"
        "- 40問を超えたら「私の負けです。正解は何でしたか？」と聞いて記録してコメントして終了\n"
        "\n"
        "【回答制限】\n"
        "- ユーザーから返ってくるのは「はい」「いいえ」「わからない」「ときどき」「正解！」のいずれかです。それ以外の返答が来た場合は再入力を依頼してください。\n"
        "\n"
        "【厳格な観点ローテーションルール】\n"
        "- 質問の観点は以下の8つに分類されます：\n"
        "  1. カテゴリ分類（家具、電子機器、装飾品、食べ物、道具など）\n"
        "  2. 用途・機能（何に使うか、何をするか）\n"
        "  3. 場所・環境（どこにあるか、どこで使うか）\n"
        "  4. 物理的特徴（大きさ、形、色、重さなど）\n"
        "  5. 材質・構成（何でできているか）\n"
        "  6. 動作・状態（動くか、静かか、熱いかなど）\n"
        "  7. 価値・重要性（高いか、安いか、必要かなど）\n"
        "  8. 使用頻度・時期（いつ使うか、よく使うかなど）\n"
        "\n"
        "- **同じ観点で2回以上連続して質問することは絶対に禁止**です。\n"
        "- **直前5問以内で同じ観点の質問は禁止**です。\n"
        "- 観点を必ずローテーションし、多様な質問をしてください。\n"
        "\n"
        "【質問パターンの多様化】\n"
        "- 「〜ですか？」の形式だけでなく、以下のパターンも使用してください：\n"
        "  - 「〜に使いますか？」（用途）\n"
        "  - 「〜にありますか？」（場所）\n"
        "  - 「〜できますか？」（機能）\n"
        "  - 「〜ですか？」（特徴）\n"
        "  - 「〜ですか？」（状態）\n"
        "\n"
        "【悪い例と良い例】\n"
        "- 悪い例：「家具ですか？」「電子機器ですか？」「装飾品ですか？」（カテゴリ連投）\n"
        "- 悪い例：「家にありますか？」「部屋にありますか？」「台所にありますか？」（場所連投）\n"
        "- 悪い例：「日常生活で使うものですか？」→「はい」→「日常生活で使うものですか？」（抽象カテゴリを推測対象にする）\n"
        "- 良い例：「家具ですか？」→「毎日使いますか？」→「大きいですか？」→「木でできていますか？」（観点ローテーション）\n"
        "- 良い例：「日常生活で使うものですか？」→「はい」→「マグカップですか？」（具体的な単語を推測）\n"
        "\n"
        "【追加ルール】\n"
        "- 同じカテゴリ（例：文房具、果物など）や似た単語の推測（「〜ですか？」）を連続して出さないでください。\n"
        "- 推測（「〜ですか？」）が続く場合は、必ず別の観点の質問（用途、場所、特徴など）を挟んでください。\n"
        "- 直前に推測した単語やカテゴリは、すぐに繰り返さないでください。\n"
        "- 推測と質問を交互に出すことを優先してください。\n"
        "- 過去にした質問や推測は絶対に繰り返さないでください。\n"
        "- ユーザーの過去の回答（はい・いいえ・わからない・ときどき）を必ず考慮し、矛盾する質問や推測は絶対にしないでください。\n"
        "\n"
        "【これまでのやりとり】\n"
        f"{chat_log}次に出すべき質問または推測を1つだけ出力してください。必ず観点をローテーションしてください。\n"
    )
    return prompt

def build_akinator_hint_prompt(history, level, word, meaning):
    chat_log = ""
    for msg in history:
        if msg.get('role') == 'user':
            chat_log += f"ユーザー: {msg.get('text', '')}\n"
        else:
            chat_log += f"アキネーター: {msg.get('text', '')}\n"
    word_label = '単語'
    prompt = (
        f"あなたは日本語語彙アキネーターです。ユーザーが当てるべき{word_label}は「{word}」（意味: {meaning}）です。\n"
        "【ヒント生成ルール】\n"
        f"- 「{word}」に関係するヒントを1つだけ日本語で出力してください。\n"
        f"- ヒントは答えを直接言わず、でも「{word}」の特徴や使われる場面、カテゴリなどに基づいてください。\n"
        "- 例：「飲み物の一種です」「カフェでよく見かけます」など。\n"
        "- ヒントは短く簡潔に、1文だけで出力してください。\n"
        "- 絶対に疑問文、単語名そのもの、またはそれを直接連想させる語、\"？\"や\"?\"や\"!\"や\"only output\"などは含めないでください。\n"
        "- ヒントは必ず日本語の説明文で、6文字以上の文にしてください。\n"
        "【これまでのやりとり】\n"
        f"{chat_log}次に出すべきヒントを1つだけ出力してください。\n"
    )
    return prompt 