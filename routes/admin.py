# routes/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from models import db, SystemErrorLog, SystemMetrics, User, Feedback, GrammarQuizLog
from datetime import datetime, timedelta
from sqlalchemy import func, desc

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    """管理者権限が必要なルートのデコレータ"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('管理者権限が必要です。', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route("/")
@admin_required
def dashboard():
    """管理者ダッシュボード"""
    # 基本統計
    total_users = User.query.count()
    total_errors = SystemErrorLog.query.count()
    unresolved_errors = SystemErrorLog.query.filter_by(resolved=False).count()
    
    # 直近24時間のエラー
    last_24h = datetime.utcnow() - timedelta(hours=24)
    recent_errors = SystemErrorLog.query.filter(
        SystemErrorLog.created_at >= last_24h
    ).count()
    
    # エラー種別の統計
    error_stats = db.session.query(
        SystemErrorLog.error_type,
        func.count(SystemErrorLog.id).label('count')
    ).group_by(SystemErrorLog.error_type).order_by(desc('count')).limit(5).all()
    
    # 機能別エラー統計
    feature_stats = db.session.query(
        SystemErrorLog.feature,
        func.count(SystemErrorLog.id).label('count')
    ).filter(SystemErrorLog.feature.isnot(None)).group_by(
        SystemErrorLog.feature
    ).order_by(desc('count')).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_errors=total_errors,
                         unresolved_errors=unresolved_errors,
                         recent_errors=recent_errors,
                         error_stats=error_stats,
                         feature_stats=feature_stats)

@admin_bp.route("/errors")
@admin_required
def error_logs():
    """エラーログ一覧"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
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
        page=page, per_page=per_page, error_out=False
    )
    
    # フィルタオプション用のデータ
    error_types = db.session.query(SystemErrorLog.error_type).distinct().all()
    error_types = [et[0] for et in error_types if et[0]]
    
    features = db.session.query(SystemErrorLog.feature).distinct().all()
    features = [f[0] for f in features if f[0]]
    
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
    # 直近7日間のメトリクス
    last_week = datetime.utcnow() - timedelta(days=7)
    
    metrics = SystemMetrics.query.filter(
        SystemMetrics.created_at >= last_week
    ).order_by(desc(SystemMetrics.created_at)).all()
    
    # メトリクス種別でグループ化
    metrics_by_type = {}
    for metric in metrics:
        if metric.metric_type not in metrics_by_type:
            metrics_by_type[metric.metric_type] = []
        metrics_by_type[metric.metric_type].append(metric)
    
    return render_template('admin/system_metrics.html',
                         metrics_by_type=metrics_by_type)

@admin_bp.route("/users")
@admin_required
def users():
    """ユーザー管理"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    users = User.query.order_by(desc(User.last_login), desc(User.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users)

@admin_bp.route("/feedback")
@admin_required
def feedback():
    """フィードバック管理"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    status = request.args.get('status', '')
    query = Feedback.query
    
    if status:
        query = query.filter(Feedback.status == status)
    
    feedback_items = query.order_by(desc(Feedback.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/feedback.html',
                         feedback_items=feedback_items,
                         current_status=status)

@admin_bp.route("/grammar-logs")
@admin_required
def grammar_logs():
    """Grammar Quiz ログ管理"""
    try:
        import json
        print("DEBUG: Admin grammar_logs route accessed")
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # フィルタ
        user_id = request.args.get('user_id', '', type=str)
        jlpt_level = request.args.get('jlpt_level', '')
        direction = request.args.get('direction', '')
        
        print(f"DEBUG: Filters - user_id: {user_id}, jlpt_level: {jlpt_level}, direction: {direction}")
        
        query = GrammarQuizLog.query
        
        if user_id:
            query = query.filter(GrammarQuizLog.user_id == int(user_id) if user_id.isdigit() else 0)
        if jlpt_level:
            query = query.filter(GrammarQuizLog.jlpt_level == jlpt_level)
        if direction:
            query = query.filter(GrammarQuizLog.direction == direction)
        
        print("DEBUG: About to execute query...")
        logs = query.order_by(desc(GrammarQuizLog.created_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        print(f"DEBUG: Query executed, found {len(logs.items)} logs")
        
        # ログのmodel_answerをJSONからリストに変換
        for log in logs.items:
            try:
                if hasattr(log, 'model_answer') and log.model_answer:
                    log.parsed_model_answer = json.loads(log.model_answer)
                else:
                    log.parsed_model_answer = []
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"DEBUG: Error parsing model_answer for log {log.id}: {e}")
                log.parsed_model_answer = []
        
        # フィルタオプション用のデータ
        jlpt_levels = ['N5', 'N4', 'N3', 'N2', 'N1']
        directions = [('en_to_ja', 'English → Japanese'), ('ja_to_en', 'Japanese → English')]
        
        print("DEBUG: About to render template...")
        return render_template('admin/grammar_logs.html',
                             logs=logs,
                             jlpt_levels=jlpt_levels,
                             directions=directions,
                             current_user_id=user_id,
                             current_jlpt_level=jlpt_level,
                             current_direction=direction)
    except Exception as e:
        print(f"ERROR: Admin grammar_logs route error: {e}")
        import traceback
        traceback.print_exc()
        return f"Grammar logs error: {str(e)}", 500