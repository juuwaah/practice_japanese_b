from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from routes.grammar import grammar_bp
from routes.vocab import vocab_bp
from routes.akinator import akinator_bp
from routes.flashcard import flashcard_bp
from routes.youtube_listening import youtube_listening_bp
from routes.blog import blog_bp
from routes.admin import admin_bp
from models import db, User, Feedback, OAuth, GrammarQuizLog, FlashcardLog, BlogComment, BlogFavorite
from forms import LoginForm, RegistrationForm
from translations import get_text, get_user_language, get_user_font
from error_handler import safe_openai_request, format_error_response, get_localized_error_message
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

def get_blog_article_title(ref_link):
    """ブログ記事のリンクからタイトルを取得"""
    if not ref_link:
        return None
        
    try:
        # /blog/post/document_id の形式からdocument_idを抽出
        if '/blog/post/' in ref_link:
            document_id = ref_link.split('/blog/post/')[-1]
            # google_drive_helperから記事の内容を取得
            from google_drive_helper import get_document_content
            document_content = get_document_content(document_id)
            if document_content:
                return document_content['title']
    except Exception as e:
        print(f"Blog title fetch error: {e}")
    
    return None

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback-key-for-development-only')

# Fix Railway reverse proxy for HTTPS
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Force HTTPS for OAuth in production
app.config['PREFERRED_URL_SCHEME'] = 'https'
# app.config['SERVER_NAME'] = 'web-production-65363.up.railway.app'  # Comment out for local testing

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
google_bp.redirect_url = "https://www.japanese-b.com/auth/google/authorized"

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
    print(f"DEBUG: Using PostgreSQL: {database_url[:50]}...")
else:
    # Railway SQLite fallback - use current directory which is persistent
    import tempfile
    db_dir = os.path.join(os.getcwd(), 'data')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_dir}/app.db'
    print(f"DEBUG: Using SQLite: {db_dir}/app.db")
    
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
        # Set Patreon status for existing Google users
        if not hasattr(oauth.user, 'is_patreon') or oauth.user.is_patreon is None:
            oauth.user.is_patreon = True  # Enable Flashcard for Google users
        login_user(oauth.user, remember=True)
    else:
        # Check if a user with this email already exists
        user = User.query.filter_by(email=email).first()
        if user:
            # Link the Google account to existing user
            user.auth_type = 'google'
            user.google_id = google_user_id
            user.last_login = datetime.utcnow()
            user.is_patreon = True  # Enable Flashcard for Google users
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
                is_patreon=True,  # Enable Flashcard for Google users
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

    # Return redirect to home instead of False
    return redirect(url_for('home'))

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
    
    # Generate new quiz with date-based deterministic selection
    from onomatopoeia_data import get_random_onomatopoeia
    
    # Step 1: 日付ベースでオノマトペを選択（同じ日は同じオノマトペ）
    import hashlib
    date_hash = int(hashlib.md5(today_str.encode()).hexdigest(), 16)
    random.seed(date_hash)  # 日付ベースのシード設定
    selected_onomatope = get_random_onomatopoeia()
    onomatope_word = selected_onomatope["word"]
    onomatope_meaning = selected_onomatope["meaning"]
    onomatope_category = selected_onomatope["category"]
    onomatope_ref_link = selected_onomatope.get("ref_link", "")
    
    # Step 2: スプレッドシートから間違い選択肢を取得
    from onomatopoeia_data import get_onomatopoeia_list
    all_onomatopoeia = get_onomatopoeia_list()
    
    # 正解以外の選択肢をランダムに2つ選択
    other_meanings = [item["meaning"] for item in all_onomatopoeia if item["word"] != onomatope_word]
    random.shuffle(other_meanings)
    distractors = other_meanings[:2]
    
    # Step 3: AIで例文のみ生成
    prompt = f"""
あなたは日本語教師です。以下の日本語オノマトペを使ったクイズを作ってください。

指定されたオノマトペ: {onomatope_word}
正解の英語意味: {onomatope_meaning}
カテゴリ: {onomatope_category}

【重要】正解の英語意味は必ず「{onomatope_meaning}」を使用してください。変更しないでください。

以下を作成してください：
1. このオノマトペ「{onomatope_word}」を使った自然な日本語の例文を2つ作る
2. 各例文のひらがな読み（漢字にひらがなをつけて読みやすくしたもの）を作る
3. 各例文に対応する自然な英語訳を作る

出力はJSON形式で：
{{
  "onomatope": "{onomatope_word}",
  "correct_meaning_en": "{onomatope_meaning}",
  "distractors_en": {distractors},
  "examples": ["...", "..."],
  "examples_hiragana": ["...", "..."],
  "examples_en": ["...", "..."]
}}
"""
    
    def make_quiz_request():
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
                return json.loads(match.group(0))
        
        # fallback: use selected onomatope with default examples
        return {
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
    
    try:
        # エラーハンドリング付きでAPI呼び出し
        quiz = safe_openai_request(make_quiz_request)
        
        # APIエラーの場合はフォールバック
        if isinstance(quiz, dict) and "error" in quiz:
            print(f"Daily quiz generation failed: {quiz['error']}")
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
    
    # 最終チェック：正解が確実にデータベースの値と一致するように
    if quiz.get("correct_meaning_en") != onomatope_meaning:
        print(f"Final check: correcting answer from '{quiz.get('correct_meaning_en')}' to '{onomatope_meaning}'")
        quiz["correct_meaning_en"] = onomatope_meaning
    
    # ref_linkをクイズデータに追加
    if onomatope_ref_link:
        quiz["ref_link"] = onomatope_ref_link
        # ブログ記事のタイトルを取得
        blog_title = get_blog_article_title(onomatope_ref_link)
        if blog_title:
            quiz["blog_title"] = blog_title
    
    # Save to cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today_str, "quiz": quiz}, f, ensure_ascii=False)
    return quiz

# Domain redirect middleware
@app.before_request
def redirect_to_custom_domain():
    if request.host == 'web-production-65363.up.railway.app':
        return redirect(f'https://www.japanese-b.com{request.full_path}', code=301)

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
        examples_hiragana=quiz.get('examples_hiragana', []),
        examples_en=quiz.get('examples_en', []),
        example_pairs=list(zip(quiz['examples'], quiz.get('examples_hiragana', []), quiz.get('examples_en', []))),
        blog_link=quiz.get('ref_link'),
        blog_title=quiz.get('blog_title')
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

@app.route("/donation")
def donation():
    return render_template(get_template("donation"))

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

@app.route("/youtube_report", methods=["POST"])
def youtube_report():
    """YouTube動画の申立て処理"""
    try:
        video_id = request.form.get('video_id', '')
        quiz_title = request.form.get('quiz_title', '')
        quiz_id = request.form.get('quiz_id', '')
        report_type = request.form.get('report_type', '')
        message = request.form.get('message', '')
        
        # 必須フィールドの検証
        if not all([video_id, report_type, message]):
            return jsonify({'success': False, 'error': '必要な情報が不足しています'})
        
        # フィードバックと同じ形式で保存
        feedback = Feedback(
            user_id=current_user.id if current_user.is_authenticated else None,
            message=f"""YouTube動画申立て:
動画ID: {video_id}
クイズタイトル: {quiz_title}
クイズID: {quiz_id}
申立て種類: {report_type}

詳細:
{message}"""
        )
        
        db.session.add(feedback)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '申立てを受け付けました'})
        
    except Exception as e:
        print(f"YouTube report error: {e}")
        return jsonify({'success': False, 'error': '処理中にエラーが発生しました'})

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
        font_family = request.json.get('font_family', 'notosans')
        if font_family not in ['notosans', 'dotgothic', 'klee']:
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
        
        message = request.form.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'メッセージを入力してください'})
        
        # データベースに保存（ログインユーザーのみ、名前とメールはユーザー情報から取得）
        feedback_entry = Feedback(
            name=current_user.username or current_user.email.split('@')[0],
            email=current_user.email,
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
    
    # ブログコメント統計
    total_comments = BlogComment.query.filter_by(is_deleted=False).count()
    recent_comments = BlogComment.query.filter_by(is_deleted=False)\
                                      .order_by(BlogComment.created_at.desc()).limit(5).all()
    
    # お気に入り統計
    total_favorites = BlogFavorite.query.count()
    
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
                         recent_users=recent_users,
                         total_comments=total_comments,
                         recent_comments=recent_comments,
                         total_favorites=total_favorites)

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

@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    """個別ユーザーの詳細とログ表示"""
    if not current_user.is_admin:
        flash('アクセス権限がありません', 'error')
        return redirect(url_for('home'))
    
    # ユーザー情報を取得
    user = User.query.get_or_404(user_id)
    
    # 文法クイズログを取得
    grammar_logs = GrammarQuizLog.query.filter_by(user_id=user_id).order_by(GrammarQuizLog.created_at.desc()).limit(50).all()
    
    # フラッシュカードログを取得
    flashcard_logs = FlashcardLog.query.filter_by(user_id=user_id).order_by(FlashcardLog.created_at.desc()).limit(50).all()
    
    return render_template('admin_user_detail.html', 
                         user=user, 
                         grammar_logs=grammar_logs, 
                         flashcard_logs=flashcard_logs)

@app.route("/admin/comments")
@admin_required
def admin_comments():
    """ブログコメント管理"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    comments_query = BlogComment.query.filter_by(is_deleted=False)\
                                     .order_by(BlogComment.created_at.desc())
    comments_list = comments_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin_comments.html', comments_list=comments_list)

@app.route("/admin/comment/<int:comment_id>/reply", methods=["POST"])
@admin_required
def admin_reply_comment(comment_id):
    """管理者がコメントに返信"""
    parent_comment = BlogComment.query.get_or_404(comment_id)
    reply_content = request.form.get('reply_content', '').strip()
    
    if not reply_content:
        flash('返信内容を入力してください', 'error')
        return redirect(url_for('admin_comments'))
    
    reply = BlogComment(
        document_id=parent_comment.document_id,
        user_id=current_user.id,
        content=reply_content,
        parent_comment_id=comment_id,
        is_admin_reply=True
    )
    
    db.session.add(reply)
    db.session.commit()
    
    flash('返信を投稿しました', 'success')
    return redirect(url_for('admin_comments'))

@app.route("/admin/comment/<int:comment_id>/delete", methods=["POST"])
@admin_required
def admin_delete_comment(comment_id):
    """コメントを削除（論理削除）"""
    comment = BlogComment.query.get_or_404(comment_id)
    comment.is_deleted = True
    db.session.commit()
    
    flash('コメントを削除しました', 'success')
    return redirect(url_for('admin_comments'))

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
app.register_blueprint(blog_bp)
app.register_blueprint(admin_bp)

# Patreon OAuth removed - using Google login only

# Initialize database tables (works with both Flask dev server and gunicorn)
try:
    with app.app_context():
        # Ensure database directory exists for SQLite
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if 'sqlite' in db_uri and not os.getenv('DATABASE_URL'):
            db_path = db_uri.replace('sqlite:///', '')
            db_dir = os.path.dirname(db_path)
            os.makedirs(db_dir, exist_ok=True)
            print(f"DEBUG: SQLite directory ensured: {db_dir}")
        
        db.create_all()
        print("DEBUG: Database tables created successfully")
except Exception as e:
    print(f"DEBUG: Database table creation error: {e}")
    import traceback
    traceback.print_exc()

# Speech recognition API endpoint
@app.route("/api/speech-to-text", methods=["POST"])
def speech_to_text():
    """音声をテキストに変換 (OpenAI Whisper API使用)"""
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': '音声ファイルがありません'}), 400
        
        audio_file = request.files['audio']
        language = request.form.get('language', 'ja')  # デフォルトは日本語
        
        if audio_file.filename == '':
            return jsonify({'success': False, 'error': '音声ファイルが選択されていません'}), 400
        
        # OpenAI Whisper APIで音声認識
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        def make_whisper_request():
            # 音声ファイルを一時的に保存
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp_file:
                audio_file.save(tmp_file.name)
                
                # Whisper APIを呼び出し
                with open(tmp_file.name, 'rb') as audio:
                    response = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        language=language if language != 'auto' else None,
                        response_format="text"
                    )
                
                # 一時ファイルを削除
                os.unlink(tmp_file.name)
                return response
        
        # エラーハンドリング付きでAPI呼び出し
        result = safe_openai_request(make_whisper_request)
        
        if isinstance(result, dict) and "error" in result:
            return jsonify({'success': False, 'error': result["error"]}), 500
        
        return jsonify({
            'success': True,
            'text': result.strip(),
            'language': language
        })
        
    except Exception as e:
        print(f"Speech recognition error: {e}")
        return jsonify({
            'success': False,
            'error': f'音声認識エラー: {str(e)}'
        }), 500

# Patreon OAuth callback removed - using Google login only

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, port=port, host='0.0.0.0')