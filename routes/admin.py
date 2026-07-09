# routes/admin.py
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, SystemErrorLog, SystemMetrics, User, Feedback, GrammarQuizLog, FlashcardLog
from datetime import datetime, timedelta
from sqlalchemy import desc

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    """管理者権限が必要なルートのデコレータ"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('管理者権限が必要です。', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/")
@admin_required
def dashboard():
    """管理者ダッシュボード"""
    total_users = User.query.count()
    total_feedback = Feedback.query.count()
    unread_feedback = Feedback.query.filter_by(status='unread').count()
    recent_feedback = Feedback.query.order_by(Feedback.created_at.desc()).limit(10).all()

    # ユーザー登録数の推移（最近7日間）
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= seven_days_ago).count()

    return render_template('admin_dashboard.html',
                         total_users=total_users,
                         total_feedback=total_feedback,
                         unread_feedback=unread_feedback,
                         recent_feedback=recent_feedback,
                         recent_users=recent_users)

@admin_bp.route("/users")
@admin_required
def users():
    """ユーザー管理"""
    page = request.args.get('page', 1, type=int)
    users_list = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin_users.html', users_list=users_list)

@admin_bp.route('/user/<int:user_id>')
@admin_required
def user_detail(user_id):
    """個別ユーザーの詳細とログ表示"""
    user = User.query.get_or_404(user_id)
    grammar_logs = GrammarQuizLog.query.filter_by(user_id=user_id)\
                                       .order_by(GrammarQuizLog.created_at.desc()).limit(50).all()
    flashcard_logs = FlashcardLog.query.filter_by(user_id=user_id)\
                                       .order_by(FlashcardLog.created_at.desc()).limit(50).all()
    return render_template('admin_user_detail.html',
                         user=user,
                         grammar_logs=grammar_logs,
                         flashcard_logs=flashcard_logs)

@admin_bp.route("/feedback")
@admin_required
def feedback():
    """フィードバック管理"""
    page = request.args.get('page', 1, type=int)
    feedback_list = Feedback.query.order_by(Feedback.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin_feedback.html', feedback_list=feedback_list)

@admin_bp.route("/feedback/<int:feedback_id>/mark_read", methods=["POST"])
@admin_required
def mark_feedback_read(feedback_id):
    """フィードバックを既読にマーク"""
    feedback_entry = Feedback.query.get_or_404(feedback_id)
    feedback_entry.status = 'read'
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route("/errors")
@admin_required
def error_logs():
    """エラーログ一覧"""
    page = request.args.get('page', 1, type=int)

    # フィルタ
    error_type = request.args.get('error_type', '')
    feature = request.args.get('feature', '')
    resolved = request.args.get('resolved', '')

    query = SystemErrorLog.query
    if error_type:
        query = query.filter(SystemErrorLog.error_type == error_type)
    if feature:
        query = query.filter(SystemErrorLog.feature == feature)
    if resolved == 'true':
        query = query.filter(SystemErrorLog.resolved == True)
    elif resolved == 'false':
        query = query.filter(SystemErrorLog.resolved == False)

    logs = query.order_by(desc(SystemErrorLog.created_at)).paginate(
        page=page, per_page=50, error_out=False
    )

    # フィルタオプション用のデータ
    error_types = [et[0] for et in db.session.query(SystemErrorLog.error_type).distinct().all() if et[0]]
    features = [f[0] for f in db.session.query(SystemErrorLog.feature).distinct().all() if f[0]]

    return render_template('admin/error_logs.html',
                         logs=logs,
                         error_types=error_types,
                         features=features,
                         current_error_type=error_type,
                         current_feature=feature,
                         current_resolved=resolved)

@admin_bp.route("/errors/<int:error_id>/resolve", methods=['POST'])
@admin_required
def resolve_error(error_id):
    """エラーを解決済みにマーク"""
    error_log = SystemErrorLog.query.get_or_404(error_id)
    error_log.resolved = True
    db.session.commit()
    flash('エラーを解決済みにマークしました。', 'success')
    return redirect(url_for('admin.error_logs'))

@admin_bp.route("/errors/<int:error_id>/unresolve", methods=['POST'])
@admin_required
def unresolve_error(error_id):
    """エラーを未解決にマーク"""
    error_log = SystemErrorLog.query.get_or_404(error_id)
    error_log.resolved = False
    db.session.commit()
    flash('エラーを未解決にマークしました。', 'info')
    return redirect(url_for('admin.error_logs'))

@admin_bp.route("/system-metrics")
@admin_required
def system_metrics():
    """システムメトリクス表示"""
    last_week = datetime.utcnow() - timedelta(days=7)
    metrics = SystemMetrics.query.filter(
        SystemMetrics.created_at >= last_week
    ).order_by(desc(SystemMetrics.created_at)).all()

    # メトリクス種別でグループ化
    metrics_by_type = {}
    for metric in metrics:
        metrics_by_type.setdefault(metric.metric_type, []).append(metric)

    return render_template('admin/system_metrics.html',
                         metrics_by_type=metrics_by_type)

@admin_bp.route("/grammar-logs")
@admin_required
def grammar_logs():
    """Grammar Quiz ログ管理"""
    page = request.args.get('page', 1, type=int)

    # フィルタ
    user_id = request.args.get('user_id', '', type=str)
    jlpt_level = request.args.get('jlpt_level', '')
    direction = request.args.get('direction', '')

    query = GrammarQuizLog.query
    if user_id.isdigit():
        query = query.filter(GrammarQuizLog.user_id == int(user_id))
    if jlpt_level:
        query = query.filter(GrammarQuizLog.jlpt_level == jlpt_level)
    if direction:
        query = query.filter(GrammarQuizLog.direction == direction)

    logs = query.order_by(desc(GrammarQuizLog.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )

    # ログのmodel_answerをJSONからリストに変換
    for log in logs.items:
        try:
            log.parsed_model_answer = json.loads(log.model_answer) if log.model_answer else []
        except (json.JSONDecodeError, TypeError):
            log.parsed_model_answer = []

    jlpt_levels = ['N5', 'N4', 'N3', 'N2', 'N1']
    directions = [('en_to_ja', 'English → Japanese'), ('ja_to_en', 'Japanese → English')]

    return render_template('admin/grammar_logs.html',
                         logs=logs,
                         jlpt_levels=jlpt_levels,
                         directions=directions,
                         current_user_id=user_id,
                         current_jlpt_level=jlpt_level,
                         current_direction=direction)
