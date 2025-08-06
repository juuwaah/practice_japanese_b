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

class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = 'oauth'
    
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship("User")