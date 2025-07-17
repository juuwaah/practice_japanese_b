# OpenAI JLPT Practice App

A comprehensive Japanese language learning web application designed for JLPT (Japanese Language Proficiency Test) preparation. This Flask-based application provides multiple interactive learning modules powered by OpenAI's GPT models.

## 🎯 Project Overview

This application is a full-featured Japanese learning platform that combines traditional study methods with AI-powered interactive exercises. It's designed to help learners prepare for all JLPT levels (N5-N1) through various engaging learning modules.

## 🏗️ Architecture & Technology Stack

### Backend
- **Framework**: Flask 2.3.3
- **Database**: SQLAlchemy with SQLite (production-ready for PostgreSQL)
- **Authentication**: Flask-Login with multiple providers (local, Patreon OAuth)
- **AI Integration**: OpenAI GPT-4o for dynamic content generation
- **Cloud Storage**: Google Cloud Storage for audio files
- **Scheduler**: APScheduler for automated tasks

### Frontend
- **Templates**: Jinja2 with Bootstrap styling
- **CSS**: Custom responsive design
- **JavaScript**: Interactive components for flashcards and quizzes

### Key Dependencies
```
Flask==2.3.3
openai==1.14.3
flask-login==0.6.3
flask-sqlalchemy==3.1.1
pandas==2.0.3
openpyxl==3.1.2
Flask-Dance (OAuth)
google-cloud-storage
apscheduler==3.10.4
```

## 📁 Project Structure

```
OpenAI-JLPT-practice-app/
├── app.py                          # Main Flask application entry point
├── models.py                       # Database models (User, VocabMaster, FlashcardProgress)
├── forms.py                        # Flask-WTF forms for authentication
├── requirements.txt                # Python dependencies
├── .env                           # Environment variables (create from env_example.txt)
├── .render.yaml                   # Render deployment configuration
├── PRODUCTION_CHECKLIST.md        # Production deployment guide
├── 
├── routes/                        # Blueprint-based route modules
│   ├── __init__.py
│   ├── grammar.py                 # Grammar practice module
│   ├── vocab.py                   # Vocabulary quiz module
│   ├── akinator.py                # AI guessing game module
│   ├── flashcard.py               # Spaced repetition flashcards
│   ├── listening_quiz.py          # Audio-based listening tests
│   └── drive_quiz.py              # Google Drive integration
│
├── templates/                     # Jinja2 HTML templates
│   ├── base.html                  # Base template with navigation
│   ├── index.html                 # Homepage with daily onomatopoeia quiz
│   ├── login.html                 # Authentication pages
│   ├── register.html
│   ├── grammar.html               # Grammar practice interface
│   ├── vocab.html                 # Vocabulary quiz interface
│   ├── akinator.html              # Akinator game interface
│   ├── flashcard_*.html           # Flashcard system templates
│   ├── listening_quiz*.html       # Listening test templates
│   └── about.html
│
├── static/
│   └── style.css                  # Custom CSS styling
│
├── database/                      # JLPT vocabulary and grammar data
│   ├── JLPT vocabulary.xlsx       # Comprehensive vocabulary database
│   └── JLPT grammar.xlsx          # Grammar patterns database
│
├── utils/
│   └── furigana.py                # Furigana processing utilities
│
├── instance/                      # SQLite database files (auto-generated)
└── __pycache__/                   # Python cache files
```

## 🚀 Features

### 1. **Daily Onomatopoeia Quiz** (Homepage)
- AI-generated daily Japanese onomatopoeia quizzes
- Cached responses for performance
- Multiple choice format with explanations
- Example sentences in both Japanese and English

### 2. **Grammar Practice Module** (`/grammar`)
- JLPT level-specific grammar exercises (N5-N1)
- Bidirectional translation practice (English ↔ Japanese)
- AI-powered sentence generation and scoring
- Detailed feedback with model answers
- Casual Japanese variants for natural conversation

### 3. **Vocabulary Quiz Module** (`/vocab`)
- Comprehensive vocabulary database from Excel files
- Level-appropriate kanji usage
- Contextual sentence generation
- Multiple choice format with distractors
- Detailed feedback and example sentences

### 4. **Akinator-Style Word Guessing** (`/akinator`)
- Two game modes:
  - **AI Guesses**: User thinks of a word, AI asks questions
  - **User Guesses**: AI thinks of a word, user asks questions
- Natural language processing for Japanese questions
- JLPT level-specific vocabulary pools
- Hint system and answer validation

### 5. **Spaced Repetition Flashcards** (`/flashcard`)
- Scientific spaced repetition algorithm
- Progress tracking per user
- Multiple study modes (kanji → meaning, meaning → kanji)
- Forgetting curve visualization
- Review scheduling based on study history

### 6. **Listening Comprehension Tests** (`/listening_quiz`)
- Audio-based listening exercises
- Google Cloud Storage integration
- True/False question format
- Sample quizzes for non-authenticated users
- Progress tracking for authenticated users

### 7. **User Authentication System**
- Local username/password registration
- Patreon OAuth integration
- Session management with Flask-Login
- User progress tracking
- Automatic cleanup of inactive users

## 🔧 Setup Instructions

### Prerequisites
- Python 3.8+
- OpenAI API key
- Google Cloud Storage (for listening quizzes)
- Patreon Developer account (for OAuth)

### 1. Clone and Install
```bash
git clone <repository-url>
cd OpenAI-JLPT-practice-app
pip install -r requirements.txt
```

### 2. Environment Configuration
```bash
cp env_example.txt .env
```

Edit `.env` with your credentials:
```env
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Google Cloud Storage
GCS_BUCKET_NAME=your_bucket_name
GOOGLE_DRIVE_API_KEY=your_google_api_key

# Patreon OAuth (optional)
PATREON_CLIENT_ID=your_patreon_client_id
PATREON_CLIENT_SECRET=your_patreon_client_secret

# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///instance/app.db
```

### 3. Database Initialization
```bash
python app.py
```
The database will be automatically created on first run.

### 4. Development Server
```bash
python app.py
```
Access at `http://localhost:5000`

## 🗄️ Database Schema

### User Model
```python
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    auth_provider = db.Column(db.String(32), default='local')
    is_patreon = db.Column(db.Boolean, default=False)
```

### Vocabulary Master
```python
class VocabMaster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kanji = db.Column(db.String(100), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    meaning = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    jlpt_level = db.Column(db.String(10), nullable=False)
```

### Flashcard Progress
```python
class FlashcardProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    word_id = db.Column(db.Integer, db.ForeignKey('vocab_master.id'))
    jlpt_level = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default='pending')
    study_count = db.Column(db.Integer, default=0)
    next_review = db.Column(db.DateTime, default=datetime.utcnow)
```

## 🔄 API Integration Points

### OpenAI GPT Integration
- **Daily Quiz Generation**: Creates onomatopoeia quizzes
- **Grammar Exercises**: Generates example sentences and provides feedback
- **Vocabulary Context**: Creates contextual sentences for vocabulary practice
- **Akinator Logic**: Powers the word guessing game

### Google Cloud Storage
- **Audio Files**: Stores listening comprehension audio
- **Signed URLs**: Generates temporary access URLs for audio playback

### Patreon OAuth
- **Authentication**: Allows users to login with Patreon accounts
- **User Management**: Tracks Patreon-specific user attributes

## 🚀 Deployment

### Render.com Deployment
The project includes `.render.yaml` for easy deployment on Render:

```yaml
services:
  - type: web
    name: jlpt-app
    env: python
    buildCommand: ""
    startCommand: gunicorn app:app
    envVars:
      - key: FLASK_ENV
        value: production
      - key: DATABASE_URL
        value: sqlite:///instance/app.db
```

### Production Checklist
See `PRODUCTION_CHECKLIST.md` for detailed production deployment steps including:
- Patreon OAuth configuration
- HTTPS setup
- Environment variable management
- Database migration procedures

## 🔍 Key Algorithms

### Spaced Repetition Algorithm
```python
def get_next_review_date(study_count):
    if study_count == 0: return datetime.utcnow() + timedelta(days=1)
    elif study_count == 1: return datetime.utcnow() + timedelta(days=3)
    elif study_count == 2: return datetime.utcnow() + timedelta(days=7)
    elif study_count == 3: return datetime.utcnow() + timedelta(days=14)
    else: return datetime.utcnow() + timedelta(days=30)
```

### Quiz Generation Logic
- **Vocabulary**: Random selection with level-appropriate kanji
- **Grammar**: Template-based sentence generation with GPT enhancement
- **Akinator**: Decision tree logic with natural language processing

## 🛠️ Development Guidelines

### Adding New Features
1. Create new blueprint in `routes/` directory
2. Add corresponding templates in `templates/`
3. Update navigation in `base.html`
4. Register blueprint in `app.py`

### Database Changes
1. Modify models in `models.py`
2. Run database migrations
3. Update any related queries in route files

### AI Integration
- Use consistent prompt engineering patterns
- Implement proper error handling for API failures
- Cache responses where appropriate for performance

## 🔒 Security Considerations

- CSRF protection enabled
- Secure password hashing with Werkzeug
- OAuth2 implementation for third-party authentication
- Environment variable management for sensitive data
- Automatic cleanup of inactive users

## 📊 Performance Optimizations

- Daily quiz caching to reduce API calls
- Database indexing on frequently queried fields
- Lazy loading of vocabulary data
- Optimized database queries with relationships

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Follow existing code patterns
4. Test thoroughly with different JLPT levels
5. Update documentation as needed

## 📄 License & Privacy

### Privacy Policy
This app does not collect or share personal information except for authentication purposes. User data is only used for login and app functionality. No data is sold or shared with third parties.

### Terms of Service
By using this app, you agree to use it for personal study purposes only. The app is provided as-is, without any warranty. The developer is not responsible for any damages or data loss.

---

**Note**: This application is designed for educational purposes and should be used in compliance with OpenAI's usage policies and Patreon's developer terms of service. 