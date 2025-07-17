import os
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from google.cloud import storage

listening_quiz_bp = Blueprint('listening_quiz', __name__, url_prefix='/listening_quiz')

# GCSバケット名（環境変数から取得、なければ直接指定）
BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'listening_quiz_bucket')

# クイズ一覧を取得（quiz1, quiz2, ...）
def list_quiz_ids(bucket_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    quiz_ids = set()
    for blob in bucket.list_blobs():
        if '/' in blob.name:
            quiz_id = blob.name.split('/')[0]
            quiz_ids.add(quiz_id)
    return sorted(list(quiz_ids))

# クイズデータ（questions.txt, audio.wav）を取得
def get_quiz_data(bucket_name, quiz_id):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    # questions.txt
    questions_blob = bucket.blob(f"{quiz_id}/questions.txt")
    if not questions_blob.exists():
        return None, None
    questions_txt = questions_blob.download_as_text()
    # audio.wav
    audio_blob = bucket.blob(f"{quiz_id}/audio.wav")
    audio_url = None
    if audio_blob.exists():
        # 署名付きURL（1時間有効）
        audio_url = audio_blob.generate_signed_url(version="v4", expiration=3600)
    return questions_txt, audio_url

# .txtファイルをパースして問題リスト生成
def parse_txt_questions(txt):
    questions = []
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        if lines[i][0].isdigit() and '.' in lines[i]:
            q_text = lines[i].split('.', 1)[1].strip()
            i += 1
            choices = []
            while i < len(lines) and (lines[i].startswith('T)') or lines[i].startswith('F)')):
                choices.append({'label': lines[i][2:], 'value': lines[i]})
                i += 1
            questions.append({'text': q_text, 'choices': choices})
        else:
            i += 1
    return questions

@listening_quiz_bp.route('/', methods=['GET'])
@login_required
def listening_quiz_list():
    quiz_ids = list_quiz_ids(BUCKET_NAME)
    return render_template('listening_quiz_list.html', quiz_ids=quiz_ids)

@listening_quiz_bp.route('/<quiz_id>', methods=['GET', 'POST'])
@login_required
def listening_quiz(quiz_id):
    questions_txt, audio_url = get_quiz_data(BUCKET_NAME, quiz_id)
    if not questions_txt:
        return f"クイズデータが見つかりません: {quiz_id}", 404
    questions = parse_txt_questions(questions_txt)
    results = None
    if request.method == 'POST':
        user_answers = []
        correct_count = 0
        for idx, q in enumerate(questions):
            ans = request.form.get(f'answer_{idx}')
            user_answers.append(ans)
            correct = next((c['value'] for c in q['choices'] if c['value'].startswith('T)')), None)
            if ans == correct:
                correct_count += 1
        results = {
            'user_answers': user_answers,
            'correct_count': correct_count,
            'total': len(questions),
            'is_submitted': True
        }
    return render_template('listening_quiz.html', questions=questions, results=results, audio_url=audio_url, quiz_id=quiz_id)

@listening_quiz_bp.route('/sample/<quiz_id>', methods=['GET', 'POST'])
def listening_quiz_sample_quiz(quiz_id):
    if quiz_id not in ['quiz1', 'quiz2']:
        return redirect(url_for('listening_quiz.listening_quiz_sample'))
    questions_txt, audio_url = get_quiz_data(BUCKET_NAME, quiz_id)
    if not questions_txt:
        return f"クイズデータが見つかりません: {quiz_id}", 404
    questions = parse_txt_questions(questions_txt)
    results = None
    if request.method == 'POST':
        user_answers = []
        correct_count = 0
        for idx, q in enumerate(questions):
            ans = request.form.get(f'answer_{idx}')
            user_answers.append(ans)
            correct = next((c['value'] for c in q['choices'] if c['value'].startswith('T)')), None)
            if ans == correct:
                correct_count += 1
        results = {
            'user_answers': user_answers,
            'correct_count': correct_count,
            'total': len(questions),
            'is_submitted': True
        }
    return render_template('listening_quiz.html', questions=questions, results=results, audio_url=audio_url, quiz_id=quiz_id, is_sample=True)

@listening_quiz_bp.route('/sample', methods=['GET'])
def listening_quiz_sample():
    sample_quiz_ids = ['quiz1', 'quiz2']
    return render_template('listening_quiz_sample_list.html', quiz_ids=sample_quiz_ids) 