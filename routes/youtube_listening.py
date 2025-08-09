import os
import re
import requests
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from google_sheets_helper import load_youtube_listening_data_from_sheets
from translations import get_user_language
from models import db, QuizPlayCount
from datetime import datetime

youtube_listening_bp = Blueprint('youtube_listening', __name__, url_prefix='/listening')

# Google Sheets設定
SHEET_ID = os.getenv('LISTENING_QUIZ_SHEET_ID', '1PhLvXJIIm5yzhXucMDMFYNkBoj3Putd-TdKPEvwXLyM')
SHEET_NAME = os.getenv('LISTENING_QUIZ_SHEET_NAME', 'YouTube Listening Quiz')

def get_channel_info_from_api(channel_id):
    """YouTube Data APIを使ってチャンネル情報を取得"""
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        print(f"DEBUG: YOUTUBE_API_KEY not found for channel {channel_id}")
        return None, None
    
    try:
        url = f"https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'snippet',
            'id': channel_id,
            'key': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"DEBUG: YouTube API response for {channel_id}: {data}")
        
        if 'items' in data and len(data['items']) > 0:
            channel_info = data['items'][0]['snippet']
            channel_name = channel_info.get('title', 'YouTube Channel')
            
            # チャンネルアイコンを取得（高解像度優先）
            thumbnails = channel_info.get('thumbnails', {})
            if 'high' in thumbnails:
                channel_icon = thumbnails['high']['url']
            elif 'medium' in thumbnails:
                channel_icon = thumbnails['medium']['url']
            elif 'default' in thumbnails:
                channel_icon = thumbnails['default']['url']
            else:
                channel_icon = "https://upload.wikimedia.org/wikipedia/commons/4/42/YouTube_icon_%282013-2017%29.png"
            
            print(f"DEBUG: Successfully got channel info - Name: {channel_name}, Icon: {channel_icon}")
            return channel_name, channel_icon
        else:
            print(f"DEBUG: No channel data found for {channel_id}")
            return None, None
            
    except Exception as e:
        print(f"DEBUG: YouTube API error for {channel_id}: {e}")
        return None, None

def extract_channel_info(channel_data):
    """YouTubeチャンネル情報からチャンネル名とアイコンを取得"""
    print(f"DEBUG: extract_channel_info called with: {channel_data}")
    if not channel_data:
        return None, None
    
    channel_name = None
    channel_icon = None
    channel_id = None
    
    # Channel IDが直接渡された場合（UCで始まる）
    if isinstance(channel_data, str) and channel_data.startswith('UC') and len(channel_data) == 24:
        channel_id = channel_data
    # URLから抽出
    elif 'youtube.com' in str(channel_data):
        if '/@' in channel_data:
            # @handle format - APIでは取得できないのでそのまま使用
            channel_name = channel_data.split('/@')[-1].split('?')[0].split('/')[0]
        elif '/c/' in channel_data:
            # Custom URL format - APIでは取得できないのでそのまま使用
            channel_name = channel_data.split('/c/')[-1].split('?')[0].split('/')[0]
        elif '/channel/' in channel_data:
            # Channel ID format - IDを取得
            channel_id = channel_data.split('/channel/')[-1].split('?')[0].split('/')[0]
        else:
            # フォールバック: URLの最後の部分を使用
            parts = channel_data.rstrip('/').split('/')
            if len(parts) > 0:
                channel_name = parts[-1].split('?')[0]
    
    # Channel IDがある場合、APIから実際の情報を取得
    if channel_id:
        api_name, api_icon = get_channel_info_from_api(channel_id)
        if api_name and api_icon:
            return api_name, api_icon
        else:
            # API失敗時のフォールバック
            channel_name = f"Channel ({channel_id[-8:]})"
            channel_icon = "https://upload.wikimedia.org/wikipedia/commons/4/42/YouTube_icon_%282013-2017%29.png"
    
    # APIが使えない場合やChannel ID以外の場合のフォールバック
    if not channel_name:
        channel_name = str(channel_data)[:20] + '...' if len(str(channel_data)) > 20 else str(channel_data)
    
    if not channel_icon:
        channel_icon = "https://upload.wikimedia.org/wikipedia/commons/4/42/YouTube_icon_%282013-2017%29.png"
    
    return channel_name, channel_icon

def get_quiz_data():
    """リスニングクイズデータを取得"""
    data = load_youtube_listening_data_from_sheets(SHEET_ID, SHEET_NAME)
    return data or []

def get_user_play_counts(user_id):
    """ユーザーのプレイ回数を取得"""
    if not user_id:
        return {}
    
    play_counts = QuizPlayCount.query.filter_by(user_id=user_id).all()
    return {pc.quiz_id: pc.play_count for pc in play_counts}

def record_quiz_play(user_id, quiz_id):
    """クイズプレイ記録を更新"""
    if not user_id or not quiz_id:
        return
    
    try:
        play_count = QuizPlayCount.query.filter_by(user_id=user_id, quiz_id=str(quiz_id)).first()
        
        if play_count:
            play_count.play_count += 1
            play_count.last_played = datetime.utcnow()
        else:
            play_count = QuizPlayCount(
                user_id=user_id,
                quiz_id=str(quiz_id),
                play_count=1,
                last_played=datetime.utcnow()
            )
            db.session.add(play_count)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error recording quiz play: {e}")

@youtube_listening_bp.route('/')
def listening_levels():
    """YouTubeリスニングクイズ一覧ページ（全レベル統合）"""
    quiz_data = get_quiz_data()
    
    # レベルフィルタ
    selected_level = request.args.get('level', 'all')
    
    # プレイ回数を取得（ログイン時のみ）
    user_play_counts = get_user_play_counts(current_user.id if current_user and current_user.is_authenticated else None)
    
    # 同じIDのクイズデータをグループ化して総再生時間を計算
    quiz_groups = {}
    for quiz in quiz_data:
        quiz_id = str(quiz.get('id'))
        if quiz_id not in quiz_groups:
            quiz_groups[quiz_id] = []
        quiz_groups[quiz_id].append(quiz)
    
    # 各クイズの総再生時間とプレイ回数を計算
    unique_quizzes = []
    for quiz_id, quizzes in quiz_groups.items():
        # 最初のクイズを代表として使用
        representative_quiz = quizzes[0]
        
        # 総再生時間を計算（同じvideo_idの全セクション）
        total_duration = 0
        for quiz in quizzes:
            try:
                start = int(quiz.get('start', 0) or 0)
                end = int(quiz.get('end', 0) or 0)
                duration = max(0, end - start)
                total_duration += duration
            except (ValueError, TypeError):
                pass
        
        # チャンネル情報を取得
        channel_data = representative_quiz.get('channel_link')
        print(f"DEBUG: Processing quiz {quiz_id} with channel_data: {channel_data}")
        channel_name, channel_icon = extract_channel_info(channel_data)
        
        representative_quiz['total_duration'] = total_duration
        representative_quiz['play_count'] = user_play_counts.get(quiz_id, 0)
        representative_quiz['channel_name'] = channel_name
        representative_quiz['channel_icon'] = channel_icon
        unique_quizzes.append(representative_quiz)
    
    # レベルフィルタ適用
    if selected_level != 'all':
        filtered_quizzes = [quiz for quiz in unique_quizzes if quiz.get('level') == selected_level]
    else:
        filtered_quizzes = unique_quizzes
    
    # ソート処理
    sort_by = request.args.get('sort', 'id')
    reverse = request.args.get('order') == 'desc'
    
    if sort_by == 'length':
        filtered_quizzes.sort(key=lambda q: q.get('total_duration', 0), reverse=reverse)
    elif sort_by == 'title':
        filtered_quizzes.sort(key=lambda q: q.get('title', ''), reverse=reverse)
    elif sort_by == 'level':
        level_order = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5, 'N0': 6}
        filtered_quizzes.sort(key=lambda q: level_order.get(q.get('level', 'N5'), 1), reverse=reverse)
    elif sort_by == 'channel':
        filtered_quizzes.sort(key=lambda q: q.get('channel_name', '') or '', reverse=reverse)
    elif sort_by == 'played':
        filtered_quizzes.sort(key=lambda q: q.get('play_count', 0), reverse=reverse)
    else:  # id
        filtered_quizzes.sort(key=lambda q: str(q.get('id', '')), reverse=reverse)
    
    # 動画の長さはすでにtotal_durationで設定済み
    for quiz in filtered_quizzes:
        quiz['duration'] = quiz.get('total_duration', 0)
    
    # レベル統計を計算
    level_counts = {}
    for quiz in unique_quizzes:
        level = quiz.get('level', 'N5')
        level_counts[level] = level_counts.get(level, 0) + 1
    
    # 言語判定（URLパラメータがあれば優先、なければセッション/ユーザー設定）
    language = request.args.get('lang') or get_user_language()
    
    template_name = 'youtube_listening_unified.html' if language == 'ja' else 'youtube_listening_unified_en.html'
    
    return render_template(template_name, 
                         quizzes=filtered_quizzes,
                         selected_level=selected_level,
                         current_sort=sort_by,
                         current_order='desc' if reverse else 'asc',
                         level_counts=level_counts,
                         language=language)

# 旧レベル別ページは統合されました - リダイレクト用
@youtube_listening_bp.route('/<level>')
def listening_quiz_list(level):
    """レベル別ページから統合ページへリダイレクト"""
    return redirect(url_for('youtube_listening.listening_levels', level=level))

@youtube_listening_bp.route('/quiz/<quiz_id>', methods=['GET', 'POST'])
@youtube_listening_bp.route('/quiz/<quiz_id>/<int:quiz_num>', methods=['GET', 'POST'])
def listening_quiz(quiz_id, quiz_num=None):
    """個別クイズページ"""
    quiz_data = get_quiz_data()
    
    # 同じIDの全ての問題を取得
    same_id_quizzes = [q for q in quiz_data if str(q.get('id')) == str(quiz_id)]
    
    if not same_id_quizzes:
        return f"クイズが見つかりません: {quiz_id}", 404
    
    # quiz_numが指定されていない場合は全ての問題を表示
    if quiz_num is None:
        # 全問題を一度に表示
        base_quiz = same_id_quizzes[0]  # 最初の問題から動画情報を取得
        
        # 動画情報を各問題に継承（個別の時間設定がある場合は保持）
        for quiz in same_id_quizzes:
            if not quiz.get('video_id'):
                quiz['video_id'] = base_quiz.get('video_id')
            if not quiz.get('title'):
                quiz['title'] = base_quiz.get('title')
            # start/endは個別設定があれば保持、なければ継承
            if not quiz.get('start') and not quiz.get('end'):
                quiz['start'] = base_quiz.get('start')
                quiz['end'] = base_quiz.get('end')
            elif not quiz.get('start'):
                quiz['start'] = base_quiz.get('start')
            elif not quiz.get('end'):
                quiz['end'] = base_quiz.get('end')
            # チャンネル情報の継承
            if not quiz.get('channel_link'):
                quiz['channel_link'] = base_quiz.get('channel_link')
        
        # チャンネル情報を取得
        channel_data = base_quiz.get('channel_link')
        channel_name, channel_icon = extract_channel_info(channel_data)
        base_quiz['channel_name'] = channel_name
        base_quiz['channel_icon'] = channel_icon
        
        # チャンネルURLを正しい形式に変換
        if channel_data and channel_data.startswith('UC') and len(channel_data) == 24:
            # Channel IDの場合、フルURLに変換
            base_quiz['youtube_channel_page'] = f"https://www.youtube.com/channel/{channel_data}"
        else:
            base_quiz['youtube_channel_page'] = channel_data
        
        # POST処理（複数問題の回答送信）
        results = None
        show_answers = False
        if request.method == 'POST':
            # プレイ回数を記録（ログイン時のみ）
            if current_user and current_user.is_authenticated:
                record_quiz_play(current_user.id, quiz_id)
            
            results = []
            total_correct = 0
            
            for quiz in same_id_quizzes:
                quiz_num_key = int(quiz.get('quiz_num', 1))
                user_answer = request.form.get(f'answer_{quiz_num_key}')
                correct_answer = str(quiz.get('correct', '1'))
                
                is_correct = user_answer == correct_answer
                if is_correct:
                    total_correct += 1
                
                results.append({
                    'quiz_num': quiz_num_key,
                    'question': quiz.get('question'),
                    'user_answer': user_answer,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct,
                    'explanation': quiz.get('explanation', ''),
                    'explanation_time': quiz.get('explanation_time', '')
                })
            
            show_answers = True
        
        # 言語判定（URLパラメータがあれば優先、なければセッション/ユーザー設定）
        language = request.args.get('lang') or get_user_language()
        template_name = 'youtube_listening_multi_quiz.html' if language == 'ja' else 'youtube_listening_multi_quiz_en.html'
        
        return render_template(template_name, 
                             quizzes=same_id_quizzes,
                             base_quiz=base_quiz,
                             results=results,
                             show_answers=show_answers,
                             total_correct=total_correct if results else 0,
                             total_questions=len(same_id_quizzes),
                             language=language)
    
    # 特定のquiz_numが指定された場合
    quiz = next((q for q in same_id_quizzes if int(q.get('quiz_num', 1)) == quiz_num), None)
    
    if not quiz:
        return f"クイズが見つかりません: {quiz_id}/{quiz_num}", 404
    
    # 動画情報が空の場合、同じIDのquiz_num=1から取得
    if not quiz.get('video_id') or not quiz.get('title'):
        base_quiz = next((q for q in same_id_quizzes if int(q.get('quiz_num', 1)) == 1), None)
        if base_quiz:
            quiz['video_id'] = quiz.get('video_id') or base_quiz.get('video_id')
            quiz['title'] = quiz.get('title') or base_quiz.get('title')
            quiz['start'] = quiz.get('start') or base_quiz.get('start')
            quiz['end'] = quiz.get('end') or base_quiz.get('end')
            quiz['channel_link'] = quiz.get('channel_link') or base_quiz.get('channel_link')
    
    # チャンネル情報を取得
    channel_data = quiz.get('channel_link')
    channel_name, channel_icon = extract_channel_info(channel_data)
    quiz['channel_name'] = channel_name
    quiz['channel_icon'] = channel_icon
    
    # チャンネルURLを正しい形式に変換
    if channel_data and channel_data.startswith('UC') and len(channel_data) == 24:
        # Channel IDの場合、フルURLに変換
        quiz['youtube_channel_page'] = f"https://www.youtube.com/channel/{channel_data}"
    else:
        quiz['youtube_channel_page'] = channel_data
    
    # 選択肢を整理
    choices = []
    for i in range(1, 5):
        opt = quiz.get(f'opt{i}', '').strip()
        if opt:
            choices.append({'number': i, 'text': opt})
    
    # POST処理（回答送信）
    result = None
    show_answer = False
    if request.method == 'POST':
        # プレイ回数を記録（ログイン時のみ）
        if current_user and current_user.is_authenticated:
            record_quiz_play(current_user.id, quiz_id)
        
        user_answer = request.form.get('answer')
        correct_answer = str(quiz.get('correct', '1'))
        
        result = {
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': user_answer == correct_answer,
            'explanation': quiz.get('explanation', ''),
            'explanation_time': quiz.get('explanation_time', '')
        }
        show_answer = True
    
    # 言語判定（URLパラメータがあれば優先、なければセッション/ユーザー設定）
    language = request.args.get('lang') or get_user_language()
    template_name = 'youtube_listening_quiz.html' if language == 'ja' else 'youtube_listening_quiz_en.html'
    
    return render_template(template_name, 
                         quiz=quiz, 
                         choices=choices,
                         result=result,
                         show_answer=show_answer,
                         quiz_data=quiz_data,
                         language=language)