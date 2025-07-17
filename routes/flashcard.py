from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, VocabMaster, FlashcardProgress
import pandas as pd
import os
from datetime import datetime, timedelta
import random

flashcard_bp = Blueprint('flashcard', __name__, url_prefix='/flashcard')

def load_vocab_data():
    """Excelファイルから語彙データを読み込んでデータベースに保存"""
    excel_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'JLPT vocabulary.xlsx')
    
    if not os.path.exists(excel_path):
        return False
    
    # 既にデータが存在するかチェック
    if VocabMaster.query.first():
        return True
    
    try:
        # 各JLPTレベルのシートを読み込み
        levels = ['N5', 'N4', 'N3', 'N2', 'N1']
        for level in levels:
            try:
                df = pd.read_excel(excel_path, sheet_name=level)
                for _, row in df.iterrows():
                    kanji = str(row.get('Kanji', '')).strip()
                    word = str(row.get('Word', '')).strip()
                    
                    # 漢字が空またはnanの場合は空文字列にする
                    if kanji == 'nan' or kanji == '' or kanji.lower() == 'nan':
                        kanji = ''
                    
                    # Wordがnanの場合は空文字列にする
                    if word == 'nan' or word.lower() == 'nan':
                        word = ''
                    
                    vocab = VocabMaster(
                        kanji=kanji,
                        word=word,
                        meaning=str(row.get('Meaning', '')),
                        type=str(row.get('Type', '')),
                        jlpt_level=level
                    )
                    db.session.add(vocab)
            except Exception as e:
                print(f"Error loading {level}: {e}")
                continue
        
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error loading vocab data: {e}")
        return False

def get_next_review_date(study_count):
    """忘却曲線に基づいて次回復習日を計算"""
    if study_count == 0:
        return datetime.utcnow() + timedelta(days=1)
    elif study_count == 1:
        return datetime.utcnow() + timedelta(days=3)
    elif study_count == 2:
        return datetime.utcnow() + timedelta(days=7)
    elif study_count == 3:
        return datetime.utcnow() + timedelta(days=14)
    else:
        return datetime.utcnow() + timedelta(days=30)

@flashcard_bp.route('/')
@login_required
def flashcard_index():
    """フラッシュカード設定画面"""
    # 初回アクセス時にデータを読み込み
    load_vocab_data()
    
    # 復習対象の単語数を取得
    review_count = FlashcardProgress.query.filter(
        FlashcardProgress.user_id == current_user.id,
        FlashcardProgress.next_review <= datetime.utcnow()
    ).count()
    
    return render_template('flashcard_setup.html', review_count=review_count)

@flashcard_bp.route('/study', methods=['GET', 'POST'])
@login_required
def study():
    """フラッシュカード学習画面"""
    if request.method == 'GET':
        # 設定パラメータを取得
        jlpt_level = request.args.get('level', 'N5')
        card_count = int(request.args.get('count', 10))
        front_mode = request.args.get('front_mode', 'kanji')  # 'kanji' or 'meaning'
        
        # 復習対象の単語を優先的に取得
        review_progress = FlashcardProgress.query.filter(
            FlashcardProgress.user_id == current_user.id,
            FlashcardProgress.next_review <= datetime.utcnow(),
            FlashcardProgress.jlpt_level == jlpt_level
        ).limit(card_count).all()
        
        # 復習対象の単語IDを取得
        review_word_ids = [p.word_id for p in review_progress]
        review_words = VocabMaster.query.filter(VocabMaster.id.in_(review_word_ids)).all() if review_word_ids else []
        
        # 復習対象が不足する場合は未学習単語を追加
        remaining_count = card_count - len(review_words)
        if remaining_count > 0:
            # 既に学習済みの単語IDを取得
            learned_word_ids = [p.word_id for p in FlashcardProgress.query.filter(
                FlashcardProgress.user_id == current_user.id,
                FlashcardProgress.status == 'learned'
            ).all()]
            
            # 未学習の単語を取得（学習済みでない単語）
            new_words = VocabMaster.query.filter(
                VocabMaster.jlpt_level == jlpt_level,
                ~VocabMaster.id.in_(learned_word_ids)
            ).limit(remaining_count).all()
            
            # 復習対象と新規単語を組み合わせ
            all_words = review_words + new_words
        else:
            all_words = review_words
        
        # セッションに学習情報を保存
        session['study_info'] = {
            'jlpt_level': jlpt_level,
            'front_mode': front_mode,
            'word_ids': [w.id for w in all_words],
            'current_index': 0,
            'total_count': len(all_words)
        }
        session.modified = True  # セッションの変更を明示的に保存
        
        return render_template('flashcard_study.html', 
                             word=all_words[0] if all_words else None,
                             front_mode=front_mode,
                             current_index=0,
                             total_count=len(all_words))
    
    else:
        # POST: カードの回答処理
        word_id = request.form.get('word_id')
        action = request.form.get('action')  # 'learned' or 'not_learned'
        
        # 進捗を更新または作成
        progress = FlashcardProgress.query.filter_by(
            user_id=current_user.id,
            word_id=word_id
        ).first()
        
        if not progress:
            vocab = db.session.get(VocabMaster, word_id)
            progress = FlashcardProgress(
                user_id=current_user.id,
                word_id=word_id,
                jlpt_level=vocab.jlpt_level,
                status='pending'
            )
            db.session.add(progress)
        
        if action == 'learned':
            progress.study_count = (progress.study_count or 0) + 1
            progress.status = 'learned'
            progress.next_review = get_next_review_date(progress.study_count)
        else:
            progress.study_count = (progress.study_count or 0) + 1
            progress.status = 'pending'
            progress.next_review = get_next_review_date(progress.study_count)
        
        progress.updated_at = datetime.utcnow()
        db.session.commit()
        
        # 次のカードに進む
        study_info = session.get('study_info', {})
        
        if not study_info:
            return redirect(url_for('flashcard.flashcard_index'))
        
        current_index = study_info.get('current_index', 0) + 1
        
        if current_index >= study_info.get('total_count', 0):
            # 学習完了
            return redirect(url_for('flashcard.complete'))
        
        # 次のカードを取得
        next_word_id = study_info['word_ids'][current_index]
        next_word = db.session.get(VocabMaster, next_word_id)
        
        # セッションを更新（完全に新しい辞書を作成）
        updated_study_info = {
            'jlpt_level': study_info['jlpt_level'],
            'front_mode': study_info['front_mode'],
            'word_ids': study_info['word_ids'],
            'current_index': current_index,
            'total_count': study_info['total_count']
        }
        session['study_info'] = updated_study_info
        session.modified = True  # セッションの変更を明示的に保存
        
        return render_template('flashcard_study.html',
                             word=next_word,
                             front_mode=study_info['front_mode'],
                             current_index=current_index,
                             total_count=study_info['total_count'])

@flashcard_bp.route('/complete')
@login_required
def complete():
    """学習完了画面"""
    # 今回の学習セッションの結果を取得
    study_info = session.get('study_info', {})
    if not study_info:
        return redirect(url_for('flashcard.flashcard_index'))
    
    # 学習した単語の詳細情報を取得
    word_ids = study_info.get('word_ids', [])
    learned_words = []
    not_learned_words = []
    
    for word_id in word_ids:
        progress = FlashcardProgress.query.filter_by(
            user_id=current_user.id,
            word_id=word_id
        ).first()
        
        vocab = db.session.get(VocabMaster, word_id)
        if vocab:
            word_info = {
                'id': vocab.id,
                'kanji': vocab.kanji,
                'word': vocab.word,
                'meaning': vocab.meaning,
                'type': vocab.type,
                'study_count': progress.study_count if progress else 0,
                'next_review': progress.next_review if progress else None
            }
            
            if progress and progress.status == 'learned':
                learned_words.append(word_info)
            else:
                not_learned_words.append(word_info)
    
    # 忘却曲線データを生成
    forgetting_curve_data = generate_forgetting_curve_data(current_user.id, study_info['jlpt_level'])
    
    # セッションをクリア
    session.pop('study_info', None)
    
    return render_template('flashcard_complete.html',
                         learned_words=learned_words,
                         not_learned_words=not_learned_words,
                         total_learned=len(learned_words),
                         total_not_learned=len(not_learned_words),
                         forgetting_curve_data=forgetting_curve_data)

def generate_forgetting_curve_data(user_id, jlpt_level):
    """忘却曲線のデータを生成"""
    # ユーザーの学習進捗を取得
    progress_data = FlashcardProgress.query.filter_by(
        user_id=user_id,
        jlpt_level=jlpt_level
    ).all()
    
    # 学習回数別の統計
    study_counts = {}
    for progress in progress_data:
        count = progress.study_count or 0
        if count not in study_counts:
            study_counts[count] = 0
        study_counts[count] += 1
    
    # 忘却曲線の理論値（学習回数に対する記憶保持率）
    theoretical_retention = {
        0: 100,  # 初回学習直後
        1: 85,   # 1回目の復習後
        2: 70,   # 2回目の復習後
        3: 60,   # 3回目の復習後
        4: 50,   # 4回目の復習後
        5: 45    # 5回目以降
    }
    
    return {
        'study_counts': study_counts,
        'theoretical_retention': theoretical_retention,
        'total_words': len(progress_data),
        'jlpt_level': jlpt_level
    }

@flashcard_bp.route('/api/flip')
@login_required
def flip_card():
    """カードをめくるAPI"""
    return jsonify({'success': True}) 