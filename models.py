from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=True)  # Allow null for OAuth users
    email = db.Column(db.String(120), unique=True, nullable=False)  # Primary identifier
    password_hash = db.Column(db.String(128), nullable=True)  # Null for OAuth users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    
    # OAuth fields
    auth_type = db.Column(db.String(32), default='guest')  # 'guest', 'google', 'patreon'
    google_id = db.Column(db.String(100), nullable=True)  # Google user ID
    patreon_id = db.Column(db.String(100), nullable=True)  # Patreon user ID
    
    # User status
    is_patreon = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(10), default='en')
    font_family = db.Column(db.String(20), default='dotgothic')  # 'dotgothic' or 'klee'
    
    def set_password(self, password):
        if password:
            self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False
    
    @property
    def display_name(self):
        return self.username or self.email.split('@')[0]
    
    def __repr__(self):
        return f'<User {self.email} ({self.auth_type})>'

class VocabMaster(db.Model):
    __tablename__ = 'vocab_master'
    
    id = db.Column(db.Integer, primary_key=True)
    kanji = db.Column(db.String(100), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    meaning = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    jlpt_level = db.Column(db.String(10), nullable=False)  # N5, N4, N3, N2, N1
    
    def __repr__(self):
        return f'<VocabMaster {self.kanji} ({self.jlpt_level})>'

class FlashcardProgress(db.Model):
    __tablename__ = 'flashcard_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('vocab_master.id'), nullable=False)
    jlpt_level = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'learned' or 'pending'
    study_count = db.Column(db.Integer, default=0)  # 学習回数
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    next_review = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', backref='flashcard_progress')
    vocab = db.relationship('VocabMaster', backref='flashcard_progress')
    
    def __repr__(self):
        return f'<FlashcardProgress {self.user_id}:{self.word_id} ({self.status})>'

class Feedback(db.Model):
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # ログインユーザーの場合
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='unread')  # unread, read, replied
    user_agent = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    
    # リレーションシップ
    user = db.relationship('User', backref='feedback')
    
    def __repr__(self):
        return f'<Feedback {self.name}: {self.message[:50]}...>'

class QuizPlayCount(db.Model):
    __tablename__ = 'quiz_play_count'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.String(50), nullable=False)  # YouTube quiz ID
    play_count = db.Column(db.Integer, default=0)
    last_played = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', backref='quiz_plays')
    
    # ユニーク制約（同じユーザーが同じクイズを複数回記録しないため）
    __table_args__ = (db.UniqueConstraint('user_id', 'quiz_id', name='user_quiz_unique'),)
    
    def __repr__(self):
        return f'<QuizPlayCount {self.user_id}:{self.quiz_id} ({self.play_count})>'

class GrammarQuizLog(db.Model):
    __tablename__ = 'grammar_quiz_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_sentence = db.Column(db.Text, nullable=False)  # 生成された元の文
    user_translation = db.Column(db.Text, nullable=False)   # ユーザーの翻訳
    jlpt_level = db.Column(db.String(10), nullable=False)   # N5, N4, N3, N2, N1
    direction = db.Column(db.String(10), nullable=False)    # ja_to_en または en_to_ja
    score = db.Column(db.Float, nullable=True)              # 採点結果（0-100）
    feedback = db.Column(db.Text, nullable=True)            # AIからのフィードバック
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', backref='grammar_quiz_logs')
    
    def __repr__(self):
        return f'<GrammarQuizLog {self.user_id}:{self.jlpt_level} ({self.score})>'

class FlashcardLog(db.Model):
    __tablename__ = 'flashcard_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('vocab_master.id'), nullable=False)
    jlpt_level = db.Column(db.String(10), nullable=False)
    result = db.Column(db.String(20), nullable=False)       # 'learned' or 'not_learned'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', backref='flashcard_logs')
    vocab = db.relationship('VocabMaster', backref='flashcard_logs')
    
    def __repr__(self):
        return f'<FlashcardLog {self.user_id}:{self.word_id} ({self.result})>'

class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = 'oauth'
    
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship("User")

class BlogComment(db.Model):
    __tablename__ = 'blog_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.String(100), nullable=False)  # Google Docs document ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 返信関連
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('blog_comments.id'), nullable=True)
    is_admin_reply = db.Column(db.Boolean, default=False)  # 管理者の返信かどうか
    
    # 状態管理
    is_deleted = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=True)  # デフォルトで承認済み
    
    # リレーションシップ
    user = db.relationship('User', backref='blog_comments')
    parent_comment = db.relationship('BlogComment', remote_side=[id], backref='replies')
    
    @property
    def anonymized_username(self):
        """ユーザー名を匿名化（頭2文字 + 記号）"""
        if not self.user:
            return "Anonymous"
        
        display_name = self.user.display_name
        if len(display_name) <= 2:
            return display_name + "***"
        else:
            return display_name[:2] + "*" * (len(display_name) - 2)
    
    def __repr__(self):
        return f'<BlogComment {self.document_id}:{self.user_id}>'

class BlogFavorite(db.Model):
    __tablename__ = 'blog_favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    document_id = db.Column(db.String(100), nullable=False)  # Google Docs document ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    user = db.relationship('User', backref='blog_favorites')
    
    # ユニーク制約（同じユーザーが同じ記事を複数回お気に入りしないため）
    __table_args__ = (db.UniqueConstraint('user_id', 'document_id', name='user_document_favorite_unique'),)
    
    def __repr__(self):
        return f'<BlogFavorite {self.user_id}:{self.document_id}>'

class SystemErrorLog(db.Model):
    __tablename__ = 'system_error_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    error_type = db.Column(db.String(50), nullable=False)  # 'rate_limit', 'api_error', 'database_error', etc.
    error_message = db.Column(db.Text, nullable=True)
    feature = db.Column(db.String(50), nullable=True)  # 'grammar', 'vocab', 'akinator', 'speech_to_text'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_ip = db.Column(db.String(45), nullable=True)  # IPv6 support
    user_agent = db.Column(db.String(255), nullable=True)
    request_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
    
    # リレーション
    user = db.relationship('User', backref='error_logs', lazy=True)
    
    def __repr__(self):
        return f'<SystemErrorLog {self.error_type}:{self.feature} ({self.created_at})>'

class SystemMetrics(db.Model):
    __tablename__ = 'system_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    metric_type = db.Column(db.String(50), nullable=False)  # 'api_requests', 'active_users', 'error_rate'
    metric_value = db.Column(db.Float, nullable=False)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemMetrics {self.metric_type}:{self.metric_value} ({self.created_at})>'