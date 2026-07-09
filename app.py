from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from routes.grammar import grammar_bp
from routes.vocab import vocab_bp
from routes.akinator import akinator_bp
from routes.flashcard import flashcard_bp
from routes.youtube_listening import youtube_listening_bp
from routes.blog import blog_bp
from routes.admin import admin_bp
from models import db, User, Feedback, OAuth
from forms import LoginForm, RegistrationForm
from translations import get_text, get_user_language, get_user_font
import datetime as dt
import random
import json
import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin, SQLAlchemyStorage
from flask_dance.consumer import oauth_authorized

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
google_bp.redirect_url = "https://japanese-b.com/auth/google/authorized"

app.register_blueprint(google_bp, url_prefix="/auth")

# Database configuration - Railway compatible
database_url = os.getenv('DATABASE_URL')
if database_url:
    # Use Railway PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Railway SQLite fallback - use current directory which is persistent
    db_dir = os.path.join(os.getcwd(), 'data')
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_dir}/app.db'
    
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
        # Set Patreon status for existing Google users
        if not hasattr(oauth.user, 'is_patreon') or oauth.user.is_patreon is None:
            oauth.user.is_patreon = True  # Enable Flashcard for Google users
        # Update last login time
        oauth.user.last_login = datetime.utcnow()
        db.session.commit()
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
                is_admin=(email == os.getenv('ADMIN_EMAIL')),
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
        
        # Update last login time after linking/creating
        user.last_login = datetime.utcnow()
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

@app.template_global()
def get_latest_blog_posts():
    """Get latest blog posts for sidebar"""
    try:
        from google_drive_helper import get_blog_documents
        blog_posts = get_blog_documents()
        if not blog_posts:
            return []
        # Return latest 5 posts
        return blog_posts[:5]
    except Exception as e:
        print(f"Error getting latest blog posts: {e}")
        return []

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
    
    # Step 3: スプレッドシートから例文データを取得
    examples = []
    examples_en = []
    examples_furigana = []
    
    # デバッグ: selected_onomatopeの内容を出力
    
    # selected_onomatopeから例文データを取得
    if "example1" in selected_onomatope and selected_onomatope["example1"]:
        examples.append(selected_onomatope["example1"])
        
        # furigana_example1も取得
        furigana1 = selected_onomatope.get("furigana_example1", "").strip()
        examples_furigana.append(furigana1)
        if furigana1:
            pass
    else:
        pass
    
    if "example2" in selected_onomatope and selected_onomatope["example2"]:
        examples.append(selected_onomatope["example2"])
        
        # furigana_example2も取得
        furigana2 = selected_onomatope.get("furigana_example2", "").strip()
        examples_furigana.append(furigana2)
        if furigana2:
            pass
    else:
        pass
    
    # 英語翻訳の例文を取得
    if "translation_example1" in selected_onomatope and selected_onomatope["translation_example1"]:
        examples_en.append(selected_onomatope["translation_example1"])
    else:
        pass
        
    if "translation_example2" in selected_onomatope and selected_onomatope["translation_example2"]:
        examples_en.append(selected_onomatope["translation_example2"])
    else:
        pass
    
    # 例文はスプレッドシートのデータのみを使用（自動生成しない）
    # examples, examples_en, examples_furiganaはスプレッドシートから取得したデータのみ
        
    # ふりがなリストの長さを例文リストに合わせる
    while len(examples_furigana) < len(examples):
        examples_furigana.append("")
    
    # クイズデータを直接作成（OpenAI APIを使用しない）
    quiz = {
        "onomatope": onomatope_word,
        "correct_meaning_en": onomatope_meaning,
        "distractors_en": distractors,
        "examples": examples,
        "examples_en": examples_en,
        "examples_furigana": examples_furigana
    }
    
    # デバッグ: 最終的な例文データを出力
    
    # 最終チェック：正解が確実にデータベースの値と一致するように
    if quiz.get("correct_meaning_en") != onomatope_meaning:
        quiz["correct_meaning_en"] = onomatope_meaning
    
    # ref_linkをクイズデータに追加
    if onomatope_ref_link:
        quiz["ref_link"] = onomatope_ref_link
        # ブログ記事のタイトルを取得
        blog_title = get_blog_article_title(onomatope_ref_link)
        if blog_title:
            quiz["blog_title"] = blog_title
    
    # 画像URLを追加（image列が存在する場合）
    onomatope_image = selected_onomatope.get("image", "")
    if onomatope_image:
        # スラッシュで区切られた複数の画像に対応
        image_files = [img.strip() for img in onomatope_image.split('/') if img.strip()]
        image_urls = []
        
        for image_file in image_files:
            database_image_path = f"database/images/{image_file}"
            if os.path.exists(database_image_path):
                image_urls.append(f"/database-image/{image_file}")
            else:
                print(f"画像が見つかりません: {image_file} (パス: {database_image_path})")
        
        if image_urls:
            quiz["image_urls"] = image_urls
    
    # Save to cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today_str, "quiz": quiz}, f, ensure_ascii=False)
    return quiz

# Domain redirect middleware
@app.before_request
def redirect_to_custom_domain():
    # Redirect Railway domain to main domain
    if request.host == 'web-production-65363.up.railway.app':
        return redirect(f'https://japanese-b.com{request.full_path}', code=301)
    # Redirect www subdomain to main domain
    elif request.host == 'www.japanese-b.com':
        return redirect(f'https://japanese-b.com{request.full_path}', code=301)

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
    return render_template('index.html',
        quiz=quiz,
        onomatope=quiz['onomatope'],
        options=options,
        answered=answered,
        correct=correct,
        examples=quiz['examples'],
        examples_hiragana=quiz.get('examples_furigana', []),
        examples_en=quiz.get('examples_en', []),
        example_pairs=list(zip(quiz['examples'], quiz.get('examples_furigana', []), quiz.get('examples_en', []))),
        blog_link=quiz.get('ref_link'),
        blog_title=quiz.get('blog_title')
    )

@app.route("/database-image/<filename>")
def database_image(filename):
    """database/imagesフォルダの画像を配信"""
    from flask import send_from_directory
    return send_from_directory('database/images', filename)

@app.route("/clear-cache")
def clear_onomatopoeia_cache_route():
    """オノマトペキャッシュをクリア（デバッグ用）"""
    try:
        from onomatopoeia_data import clear_onomatopoeia_cache
        clear_onomatopoeia_cache()
        return "Cache cleared successfully", 200
    except Exception as e:
        return f"Error clearing cache: {e}", 500

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
        
        # 管理者アカウントの特別処理（環境変数 ADMIN_USERNAME / ADMIN_PASSWORD で設定）
        admin_username = os.getenv('ADMIN_USERNAME')
        admin_password = os.getenv('ADMIN_PASSWORD')
        if admin_username and admin_password and username == admin_username and password == admin_password:
            admin_email = os.getenv('ADMIN_EMAIL') or f"{admin_username}@admin.local"
            admin_user = User.query.filter_by(username=admin_username).first() \
                or User.query.filter_by(email=admin_email).first()
            if not admin_user:
                # 管理者アカウント作成（emailはNOT NULLなのでADMIN_EMAILを使用）
                admin_user = User(username=admin_username, email=admin_email,
                                  is_admin=True, is_patreon=True)
                admin_user.set_password(admin_password)
                db.session.add(admin_user)
            else:
                # 既存ユーザーに管理者権限とPatreon権限付与
                admin_user.is_admin = True
                admin_user.is_patreon = True
            admin_user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(admin_user, remember=form.remember_me.data)
            return redirect(url_for('admin.dashboard'))
        
        # 通常ユーザーの認証
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=form.remember_me.data)
        
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

@app.route("/robots.txt")
def robots_txt():
    """robots.txtを返す"""
    return app.send_static_file('robots.txt'), 200, {'Content-Type': 'text/plain'}

@app.route("/sitemap.xml")
def sitemap_xml():
    """サイトマップXMLを生成"""
    from datetime import datetime
    from flask import Response
    
    # 基本的なURL一覧
    urls = [
        {'url': url_for('home', _external=True), 'priority': '1.0', 'changefreq': 'daily'},
        {'url': url_for('about', _external=True), 'priority': '0.8', 'changefreq': 'monthly'},
        {'url': url_for('donation', _external=True), 'priority': '0.6', 'changefreq': 'monthly'},
        {'url': url_for('grammar.grammar_index', _external=True), 'priority': '0.9', 'changefreq': 'weekly'},
        {'url': url_for('vocab.vocab_index', _external=True), 'priority': '0.9', 'changefreq': 'weekly'},
        {'url': url_for('flashcard.flashcard_index', _external=True), 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': url_for('youtube_listening.listening_levels', _external=True), 'priority': '0.9', 'changefreq': 'weekly'},
        {'url': url_for('akinator.akinator_index', role='user', _external=True), 'priority': '0.7', 'changefreq': 'monthly'},
        {'url': url_for('akinator.akinator_index', role='gpt', _external=True), 'priority': '0.7', 'changefreq': 'monthly'},
        {'url': url_for('blog.blog_index', _external=True), 'priority': '0.8', 'changefreq': 'daily'},
    ]
    
    # XMLを生成
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'''
    
    for url_info in urls:
        xml_content += f'''
    <url>
        <loc>{url_info['url']}</loc>
        <changefreq>{url_info['changefreq']}</changefreq>
        <priority>{url_info['priority']}</priority>
        <lastmod>{datetime.utcnow().strftime('%Y-%m-%d')}</lastmod>
    </url>'''
    
    xml_content += '\n</urlset>'
    
    return Response(xml_content, mimetype='application/xml')

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
                {"name": "Admin Dashboard", "url": url_for('admin.dashboard'), "description": "Site management panel"},
                {"name": "Feedback Management", "url": url_for('admin.feedback'), "description": "User feedback review"},
                {"name": "User Management", "url": url_for('admin.users'), "description": "User information management"}
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
        
        db.create_all()
        
        # GrammarQuizLogテーブルにmodel_answer列を安全に追加
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            
            # テーブルが存在するかチェック
            if inspector.has_table('grammar_quiz_log'):
                columns = [col['name'] for col in inspector.get_columns('grammar_quiz_log')]
                
                if 'model_answer' not in columns:
                    pass
                    
                    # PostgreSQLとSQLiteの両方に対応
                    try:
                        with db.engine.connect() as conn:
                            # PostgreSQL/SQLiteで動作するSQL
                            conn.execute(text('ALTER TABLE grammar_quiz_log ADD COLUMN model_answer TEXT'))
                            conn.commit()
                    except Exception as sql_error:
                        print(f"DEBUG: SQL execution error: {sql_error}")
                        # 手動でcreate_allを再実行してテーブル構造を更新
                        db.create_all()
                else:
                    pass
            else:
                pass
        except Exception as migration_error:
            print(f"DEBUG: Database migration error (non-fatal): {migration_error}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"DEBUG: Database table creation error: {e}")
    import traceback
    traceback.print_exc()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, port=port, host='0.0.0.0')