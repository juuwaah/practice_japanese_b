from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from routes.grammar import grammar_bp
from routes.vocab import vocab_bp
from routes.akinator import akinator_bp
from routes.flashcard import flashcard_bp
from routes.youtube_listening import youtube_listening_bp
from models import db, User, Feedback, OAuth
from forms import LoginForm, RegistrationForm
from translations import get_text, get_user_language, get_user_font
import datetime as dt
import random
import json
import os
import openai
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from google.cloud import storage
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin, SQLAlchemyStorage
from flask_dance.consumer import oauth_authorized, OAuth2ConsumerBlueprint
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Google Drive API key loaded from environment

CACHE_FILE = ".onomatope_cache.json"

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback-key-for-development-only')

# Fix Railway reverse proxy for HTTPS
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Force HTTPS for OAuth in production
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['SERVER_NAME'] = 'web-production-65363.up.railway.app'

# CSRF protection completely disabled
app.config['WTF_CSRF_ENABLED'] = False

# Google OAuth configuration
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

# Create Google OAuth blueprint with forced HTTPS
google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
    scope=["https://www.googleapis.com/auth/userinfo.email", 
           "https://www.googleapis.com/auth/userinfo.profile", 
           "openid"],
    storage=SQLAlchemyStorage(OAuthConsumerMixin, db.session, user=lambda: current_user)
)

# Override redirect URL after blueprint creation
@google_bp.record
def record_auth(setup_state):
    setup_state.app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
    setup_state.app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
    
# Force HTTPS redirect manually
google_bp.redirect_url = "https://web-production-65363.up.railway.app/auth/google/authorized"

# Debug: Print actual redirect URL being used
print(f"DEBUG: Google BP redirect_url = {google_bp.redirect_url}")
print(f"DEBUG: Flask app config = {app.config.get('PREFERRED_URL_SCHEME')}")
print(f"DEBUG: Flask app SERVER_NAME = {app.config.get('SERVER_NAME')}")
app.register_blueprint(google_bp, url_prefix="/auth")

# Database configuration - Railway compatible
database_url = os.getenv('DATABASE_URL')
if database_url:
    # Use Railway PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Local SQLite fallback - use temp directory
    import tempfile
    temp_dir = tempfile.gettempdir()
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(temp_dir, "app.db")}'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id))

# Google OAuth callback
@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        flash('Failed to log in with Google.', 'error')
        return False

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        msg = "Failed to fetch user info from Google."
        flash(msg, category="error")
        return False

    google_info = resp.json()
    google_user_id = str(google_info["id"])
    email = google_info["email"]
    name = google_info.get("name", email.split('@')[0])

    # Check if this Google account is already connected
    query = OAuth.query.filter_by(
        provider=blueprint.name,
        provider_user_id=google_user_id,
    )
    oauth = query.first()

    if oauth:
        # User already exists, log them in
        oauth.user.last_login = datetime.utcnow()
        login_user(oauth.user, remember=True)
        flash(f'Successfully signed in with Google!', 'success')
    else:
        # Check if a user with this email already exists
        user = User.query.filter_by(email=email).first()
        if user:
            # Link the Google account to existing user
            user.auth_type = 'google'
            user.google_id = google_user_id
            user.last_login = datetime.utcnow()
            if not user.username:
                user.username = name
        else:
            # Create new user
            user = User(
                email=email,
                username=name,
                auth_type='google',
                google_id=google_user_id,
                is_admin=(email == 'suhdudebac@gmail.com'),
                last_login=datetime.utcnow()
            )
            db.session.add(user)

        # Create OAuth record
        oauth = OAuth(
            provider=blueprint.name,
            provider_user_id=google_user_id,
            user=user,
            token=token,
        )
        db.session.add(oauth)
        db.session.commit()

        login_user(user, remember=True)
        flash(f'Successfully signed in with Google!', 'success')

    return False  # Don't redirect automatically

# Template global functions for translations
@app.template_global()
def _(key):
    """Template function for translations"""
    return get_text(key, get_user_language())

@app.template_global()
def get_current_language():
    """Get current user language"""
    return get_user_language()

@app.template_global()
def get_current_font():
    """Get current user font"""
    return get_user_font()

def get_template(base_name):
    """Always return base template name since retro is now the only design"""
    return f"{base_name}.html"

# Initialize scheduler for automatic user cleanup
scheduler = BackgroundScheduler()

def cleanup_inactive_users():
    """Delete users who haven't logged in for 30 days"""
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    inactive_users = User.query.filter(User.last_login < cutoff_date).all()
    for user in inactive_users:
        db.session.delete(user)
    db.session.commit()
    print(f"Cleaned up {len(inactive_users)} inactive users")

# Schedule cleanup job to run daily at 3:00 AM
scheduler.add_job(cleanup_inactive_users, 'cron', hour=3)
scheduler.start()

# Helper to get or generate today's quiz
def get_today_quiz():
    today_str = dt.datetime.now().date().isoformat()
    # Try to load cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                cache = json.load(f)
                cached_date = cache.get("date")
                # 日付が有効で、今日の日付と一致する場合のみキャッシュを使用
                if cached_date and cached_date == today_str:
                    return cache["quiz"]
                else:
                    # 無効な日付の場合はキャッシュファイルを削除
                    os.remove(CACHE_FILE)
            except Exception:
                # エラーが発生した場合もキャッシュファイルを削除
                if os.path.exists(CACHE_FILE):
                    os.remove(CACHE_FILE)
    
    # Generate new quiz with true random selection
    from onomatopoeia_data import get_random_onomatopoeia
    
    # Step 1: ランダムにオノマトペを選択
    selected_onomatope = get_random_onomatopoeia()
    onomatope_word = selected_onomatope["word"]
    onomatope_meaning = selected_onomatope["meaning"]
    onomatope_category = selected_onomatope["category"]
    
    # Step 2: AIで例文と間違い選択肢を生成
    prompt = f"""
あなたは日本語教師です。以下の日本語オノマトペを使ったクイズを作ってください。

指定されたオノマトペ: {onomatope_word}
正解の英語意味: {onomatope_meaning}
カテゴリ: {onomatope_category}

以下を作成してください：
1. 間違い選択肢（英語の意味）を2つ作る（正解と紛らわしく、同じカテゴリの他のオノマトペの意味など）
2. このオノマトペ「{onomatope_word}」を使った自然な日本語の例文を2つ作る
3. 各例文に対応する自然な英語訳を作る

出力はJSON形式で：
{{
  "onomatope": "{onomatope_word}",
  "correct_meaning_en": "{onomatope_meaning}",
  "distractors_en": ["...", "..."],
  "examples": ["...", "..."],
  "examples_en": ["...", "..."]
}}
"""
    
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        # Extract JSON from response
        import re
        content = response.choices[0].message.content
        if content:
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                quiz = json.loads(match.group(0))
            else:
                # fallback: use selected onomatope with default examples
                quiz = {
                    "onomatope": onomatope_word,
                    "correct_meaning_en": onomatope_meaning,
                    "distractors_en": [
                        "the sound of something crashing",
                        "the feeling of being sleepy"
                    ],
                    "examples": [
                        f"この{onomatope_word}という音が好きです。",
                        f"{onomatope_word}とした気持ちになりました。"
                    ],
                    "examples_en": [
                        f"I like this {onomatope_word} sound.",
                        f"I felt {onomatope_meaning}."
                    ]
                }
        else:
            # fallback: use selected onomatope with default examples
            quiz = {
                "onomatope": onomatope_word,
                "correct_meaning_en": onomatope_meaning,
                "distractors_en": [
                    "the sound of something crashing", 
                    "the feeling of being sleepy"
                ],
                "examples": [
                    f"この{onomatope_word}という音が好きです。",
                    f"{onomatope_word}とした気持ちになりました。"
                ],
                "examples_en": [
                    f"I like this {onomatope_word} sound.",
                    f"I felt {onomatope_meaning}."
                ]
            }
    except Exception as e:
        print(f"AI generation failed: {e}")
        # Complete fallback: use selected onomatope with basic examples
        quiz = {
            "onomatope": onomatope_word,
            "correct_meaning_en": onomatope_meaning,
            "distractors_en": [
                "the sound of something crashing",
                "the feeling of being sleepy"
            ],
            "examples": [
                f"この{onomatope_word}という音が好きです。",
                f"{onomatope_word}とした気持ちになりました。"
            ],
            "examples_en": [
                f"I like this {onomatope_word} sound.",
                f"I felt {onomatope_meaning}."
            ]
        }
    # Save to cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today_str, "quiz": quiz}, f, ensure_ascii=False)
    return quiz

# ルート設定
@app.route("/", methods=["GET", "POST"])
def home():
    quiz = get_today_quiz()
    options = [quiz['correct_meaning_en']] + quiz['distractors_en']
    random.shuffle(options)
    answered = False
    correct = False
    if request.method == 'POST':
        selected = request.form.get('selected')
        answered = True
        correct = (selected == quiz['correct_meaning_en'])
    template = 'index.html'
    
    return render_template(template,
        onomatope=quiz['onomatope'],
        options=options,
        answered=answered,
        correct=correct,
        examples=quiz['examples'],
        examples_en=quiz.get('examples_en', []),
        example_pairs=list(zip(quiz['examples'], quiz.get('examples_en', [])))
    )

@app.route("/login", methods=['GET', 'POST'])
def login():
    # フラッシュメッセージにPatreon関連のメッセージがある場合は、ログインページを表示
    messages = session.get('_flashes', [])
    has_patreon_message = any('Patreon' in str(message) for _, message in messages)
    
    if current_user.is_authenticated and not has_patreon_message:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        # 管理者アカウントの特別処理
        if username == 'gotobakuho' and password == '8030xDPv1UMd':
            admin_user = User.query.filter_by(username='gotobakuho').first()
            if not admin_user:
                # 管理者アカウント作成
                admin_user = User(username='gotobakuho', is_admin=True, is_patreon=True)
                admin_user.set_password('8030xDPv1UMd')
                db.session.add(admin_user)
                db.session.commit()
            else:
                # 既存ユーザーに管理者権限とPatreon権限付与
                admin_user.is_admin = True
                admin_user.is_patreon = True
                db.session.commit()
            login_user(admin_user, remember=form.remember_me.data)
            admin_user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        
        # 通常ユーザーの認証
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('home')
        return redirect(next_page)
    
    return render_template(get_template('login'), title='Sign In', form=form)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User()
        user.username = form.username.data
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    
    return render_template(get_template('register'), title='Register', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/about")
def about():
    return render_template(get_template("about"))

@app.route("/sitemap_data")
def sitemap_data():
    """サイトマップ用のデータ取得"""
    sitemap = {
        "Main": [
            {"name": "Home", "url": url_for('home'), "description": "Japanese learning app main page"},
            {"name": "About", "url": url_for('about'), "description": "App details and information"}
        ],
        "Study": [
            {"name": "Grammar Quiz", "url": url_for('grammar.grammar_index'), "description": "JLPT grammar practice"},
            {"name": "Vocabulary Quiz", "url": url_for('vocab.vocab_index'), "description": "JLPT vocabulary practice"},
            {"name": "Flashcards", "url": url_for('flashcard.flashcard_index'), "description": "Word memorization cards"}
        ],
        "Games": [
            {"name": "You are Akinator", "url": url_for('akinator.akinator_index', role='user'), "description": "You ask the questions"},
            {"name": "AI is Akinator", "url": url_for('akinator.akinator_index', role='gpt'), "description": "AI asks the questions"}
        ],
        "Audio": [
            {"name": "YouTube Listening", "url": url_for('youtube_listening.listening_levels'), "description": "YouTube-based listening quiz practice"}
        ],
        "Auth": []
    }
    
    # 認証状態に応じてメニュー追加
    if current_user.is_authenticated:
        sitemap["Auth"].append({"name": "Logout", "url": url_for('logout'), "description": "Sign out of account"})
        
        # 管理者の場合
        if current_user.is_admin:
            sitemap["Admin"] = [
                {"name": "Admin Dashboard", "url": url_for('admin_dashboard'), "description": "Site management panel"},
                {"name": "Feedback Management", "url": url_for('admin_feedback'), "description": "User feedback review"},
                {"name": "User Management", "url": url_for('admin_users'), "description": "User information management"}
            ]
    else:
        sitemap["Auth"].extend([
            {"name": "Login", "url": url_for('login'), "description": "Sign in to account"},
            {"name": "Register", "url": url_for('register'), "description": "Create new account"}
        ])
    
    return jsonify(sitemap)

@app.route("/language", methods=["POST"])
def set_language():
    """言語設定変更"""
    try:
        language = request.json.get('language', 'en')
        if language not in ['en', 'ja', 'es', 'eo', 'iu']:
            return jsonify({'success': False, 'error': 'Invalid language'})
        
        if current_user.is_authenticated:
            current_user.language = language
            db.session.commit()
        else:
            # 未ログインユーザーはセッションに保存
            session['language'] = language
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route("/font", methods=["POST"])
def set_font():
    """フォント設定変更"""
    try:
        font_family = request.json.get('font_family', 'dotgothic')
        if font_family not in ['dotgothic', 'klee']:
            return jsonify({'success': False, 'error': 'Invalid font family'})
        
        if current_user.is_authenticated:
            current_user.font_family = font_family
            db.session.commit()
        else:
            # 未ログインユーザーはセッションに保存
            session['font_family'] = font_family
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route("/feedback", methods=["POST"])
def feedback():
    """フィードバック送信機能"""
    try:
        # ログインしているかチェック
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'フィードバック、感想を送るにはログインしてください'})
        
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()
        
        if not name or not email or not message:
            return jsonify({'success': False, 'error': '全ての項目を入力してください'})
        
        # データベースに保存（ログインユーザーのみ）
        feedback_entry = Feedback(
            name=name,
            email=email,
            message=message,
            user_id=current_user.id,
            user_agent=request.headers.get('User-Agent', ''),
            ip_address=request.remote_addr
        )
        db.session.add(feedback_entry)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Feedback error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Admin機能
def admin_required(f):
    """管理者権限チェックデコレータ"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('管理者権限が必要です')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin")
@admin_required
def admin_dashboard():
    """管理者ダッシュボード"""
    # 統計情報
    total_users = User.query.count()
    total_feedback = Feedback.query.count()
    unread_feedback = Feedback.query.filter_by(status='unread').count()
    
    # 最近のフィードバック
    recent_feedback = Feedback.query.order_by(Feedback.created_at.desc()).limit(10).all()
    
    # ユーザー登録数の推移（最近7日間）
    from datetime import datetime, timedelta
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= seven_days_ago).count()
    
    return render_template('admin_dashboard.html', 
                         total_users=total_users,
                         total_feedback=total_feedback,
                         unread_feedback=unread_feedback,
                         recent_feedback=recent_feedback,
                         recent_users=recent_users)

@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    """フィードバック管理"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    feedback_query = Feedback.query.order_by(Feedback.created_at.desc())
    feedback_list = feedback_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin_feedback.html', feedback_list=feedback_list)

@app.route("/admin/feedback/<int:feedback_id>/mark_read", methods=["POST"])
@admin_required
def mark_feedback_read(feedback_id):
    """フィードバックを既読にマーク"""
    feedback = Feedback.query.get_or_404(feedback_id)
    feedback.status = 'read'
    db.session.commit()
    return jsonify({'success': True})

@app.route("/admin/users")
@admin_required
def admin_users():
    """ユーザー管理"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    users_query = User.query.order_by(User.created_at.desc())
    users_list = users_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin_users.html', users_list=users_list)



# GCSバケット名（環境変数から取得、なければ直接指定）
BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'your-bucket-name')

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


# Blueprint 登録
app.register_blueprint(grammar_bp)
app.register_blueprint(vocab_bp)
app.register_blueprint(akinator_bp)
app.register_blueprint(flashcard_bp)
app.register_blueprint(youtube_listening_bp)

# --- Patreon OAuth2 Blueprintのセットアップ ---
patreon_blueprint = OAuth2ConsumerBlueprint(
    "patreon", __name__,
    client_id=os.getenv("PATREON_CLIENT_ID"),
    client_secret=os.getenv("PATREON_CLIENT_SECRET"),
    base_url="https://www.patreon.com/api/oauth2/api/",
    token_url="https://www.patreon.com/api/oauth2/token",
    authorization_url="https://www.patreon.com/oauth2/authorize",
    redirect_url="https://web-production-65363.up.railway.app/auth/patreon/authorized",
    scope=["identity"]
)

app.register_blueprint(patreon_blueprint, url_prefix="/auth")


@app.route('/auth/patreon/authorized')
def patreon_login_authorized():
    resp = patreon_blueprint.session.get("identity")
    print("Patreon API response:", resp.text)
    if not resp.ok:
        flash("Patreon認証に失敗しました。", "error")
        return redirect(url_for("login"))
    patreon_info = resp.json()
    print("Patreon info:", patreon_info)
    patreon_id = patreon_info["data"]["id"]
    username = f"patreon_{patreon_id}"
    # 既存ユーザー確認
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User()
        user.username = username
        user.auth_provider = 'patreon'
        user.is_patreon = True
        # Patreonユーザーはパスワード不要
        user.password_hash = ''
        db.session.add(user)
        db.session.commit()
    else:
        user.is_patreon = True
        user.auth_provider = 'patreon'
        db.session.commit()
    login_user(user)
    flash("Patreonでログインしました。", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, port=port, host='0.0.0.0')