from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from routes.grammar import grammar_bp
from routes.vocab import vocab_bp
from routes.akinator import akinator_bp
from routes.flashcard import flashcard_bp
from routes.listening_quiz import listening_quiz_bp
from models import db, User
from forms import LoginForm, RegistrationForm
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
from flask_dance.consumer import OAuth2ConsumerBlueprint
from flask_dance.consumer import oauth_authorized
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask_dance.consumer import oauth_error

print('GOOGLE_DRIVE_API_KEY:', os.getenv('GOOGLE_DRIVE_API_KEY'))

CACHE_FILE = ".onomatope_cache.json"

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# CSRF protection
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = 'your_csrf_secret_key'

# Database configuration - use absolute path
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "app.db")}')
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
    # If not cached, generate new quiz via ChatGPT
    prompt = (
        """
あなたは日本語教師です。今日の日本語オノマトペクイズを作ってください。
- 1つの日本語オノマトペ（例：ワクワク、ドキドキ、ゴロゴロなど）をランダムに選び、
- その英語の意味（簡潔に）を1つ正解として出力
- 間違い選択肢（英語の意味）を2つ作る（正解と紛らわしいもの）
- そのオノマトペを使った日本語の例文を2つ作り、それぞれに対応する自然な英語訳も作る
- 出力はJSON形式で：
{
  "onomatope": "...",
  "correct_meaning_en": "...",
  "distractors_en": ["...", "..."],
  "examples": ["...", "..."],
  "examples_en": ["...", "..."]
}
"""
    )
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8
    )
    # Extract JSON from response
    import re
    content = response.choices[0].message.content
    if content:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            quiz = json.loads(match.group(0))
        else:
            # fallback: dummy quiz
            quiz = {
                "onomatope": "ワクワク",
                "correct_meaning_en": "the feeling of excitement or anticipation",
                "distractors_en": [
                    "the sound of something crashing",
                    "the feeling of being sleepy"
                ],
                "examples": [
                    "明日の旅行が楽しみでワクワクしている。",
                    "新しいゲームを始めるときはいつもワクワクする。"
                ],
                "examples_en": [
                    "I'm excited for tomorrow's trip.",
                    "I always get excited when I start a new game."
                ]
            }
    else:
        # fallback: dummy quiz
        quiz = {
            "onomatope": "ワクワク",
            "correct_meaning_en": "the feeling of excitement or anticipation",
            "distractors_en": [
                "the sound of something crashing",
                "the feeling of being sleepy"
            ],
            "examples": [
                "明日の旅行が楽しみでワクワクしている。",
                "新しいゲームを始めるときはいつもワクワクする。"
            ],
            "examples_en": [
                "I'm excited for tomorrow's trip.",
                "I always get excited when I start a new game."
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
    return render_template('index.html',
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
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('home')
        return redirect(next_page)
    
    return render_template('login.html', title='Sign In', form=form)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    
    return render_template('register.html', title='Register', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/about")
def about():
    return render_template("about.html")

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

@app.route('/listening_quiz')
@login_required
def listening_quiz_list():
    quiz_ids = list_quiz_ids(BUCKET_NAME)
    return render_template('listening_quiz_list.html', quiz_ids=quiz_ids)

# Blueprint 登録
app.register_blueprint(grammar_bp)
app.register_blueprint(vocab_bp)
app.register_blueprint(akinator_bp)
app.register_blueprint(flashcard_bp)
app.register_blueprint(listening_quiz_bp)

# --- Patreon OAuth2 Blueprintのセットアップ ---
patreon_blueprint = OAuth2ConsumerBlueprint(
    "patreon", __name__,
    client_id=os.getenv("PATREON_CLIENT_ID"),
    client_secret=os.getenv("PATREON_CLIENT_SECRET"),
    base_url="https://www.patreon.com/api/oauth2/api/",
    token_url="https://www.patreon.com/api/oauth2/token",
    authorization_url="https://www.patreon.com/oauth2/authorize",
    redirect_url="/patreon_login/patreon/authorized",
    scope=["identity"]
)
app.register_blueprint(patreon_blueprint, url_prefix="/patreon_login")

@app.route('/patreon_login/patreon/authorized')
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
        user = User(username=username, auth_provider='patreon', is_patreon=True)
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
    app.run(debug=False)