from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    # 追加: 認証プロバイダ（'local', 'google', 'patreon'など）
    auth_provider = db.Column(db.String(32), default='local')
    # 追加: Patreonユーザーかどうか
    is_patreon = db.Column(db.Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

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